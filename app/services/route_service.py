# app/services/route_service.py
"""
Route optimization service using Google Maps API
Optimizes the order of student pickups for a bus route
"""

import logging
from typing import List, Dict, Optional, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import googlemaps
from datetime import datetime

from ..database.models.bus import Bus as BusModel
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..database.models.student import Student as StudentModel
from ..database.models.bus_location import BusLocation as BusLocationModel
from ..database.models.school import School as SchoolModel
from ..database.schemas.route import RouteResponse, RouteStop, OptimizedRouteResponse, RoutePoint
from ..core.config import settings
from ..core.redis import redis_manager
from .route_progress_service import RouteProgressService

logger = logging.getLogger(__name__)


class RouteService:
    """Service for calculating and optimizing bus routes"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gmaps_client = None
        self._initialize_gmaps_client()
        self._progress = RouteProgressService()
    
    def _initialize_gmaps_client(self) -> None:
        """Initialize Google Maps client"""
        if not settings.GOOGLE_MAPS_API_KEY:
            logger.warning("Google Maps API key not configured")
            return
        
        try:
            self.gmaps_client = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
            logger.info("Google Maps client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps client: {str(e)}")
    
    async def get_optimized_route(
        self,
        bus_id: str,
        origin: Optional[Tuple[float, float]] = None,
        exclude_student_ids: Optional[List[str]] = None,
        include_all: bool = False,
        trip_type: str = "to_school",
    ) -> OptimizedRouteResponse:
        """
        Get optimized route for a bus with all assigned students
        
        Args:
            bus_id: UUID of the bus
            
        Returns:
            OptimizedRouteResponse with optimized stops and total distance/duration
        """
        # Check cache first
        # Compose cache key based on origin and trip_type to avoid stale routes
        if origin is not None:
            o_lat = round(origin[0], 4)
            o_lng = round(origin[1], 4)
            cache_key = f"route:{bus_id}:{o_lat}:{o_lng}:{trip_type}:{'all' if include_all else 'filtered'}"
        else:
            cache_key = f"route:{bus_id}:no_origin:{trip_type}:{'all' if include_all else 'filtered'}"
        cached_route = await redis_manager.get(cache_key)
        if cached_route:
            logger.info(f"Route cache hit for bus {bus_id}")
            import json
            return OptimizedRouteResponse(**json.loads(cached_route))
        
        # Get bus with assigned students
        bus = await self._get_bus_with_students(bus_id)
        if not bus:
            raise ValueError(f"Bus not found: {bus_id}")
        
        # Get student addresses with coordinates
        stops = await self._get_student_stops(bus_id)

        # Exclude visited or ignored students unless include_all=true
        if not include_all:
            server_visited = await self._progress.get_visited(bus_id)
            combined_excludes: Set[str] = set(server_visited)
            if exclude_student_ids:
                combined_excludes.update(exclude_student_ids)
            if combined_excludes:
                before = len(stops)
                stops = [s for s in stops if s.student_id not in combined_excludes]
                logger.info(
                    f"Route: excluding visited/ignored {len(combined_excludes)} IDs; stops {before} -> {len(stops)} for bus {bus_id}"
                )
        else:
            logger.info("Route: include_all flag enabled; no excludes applied")
        
        if not stops:
            logger.warning(f"No students assigned to bus {bus_id}")
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=[],
                total_distance_meters=0,
                total_duration_seconds=0,
                generated_at=datetime.utcnow()
            )
        
        # Get school coordinates (needed for both trip types)
        school_coords = await self._get_school_coordinates(bus_id)

        # Determine origin and destination based on trip_type
        if trip_type == "to_school":
            # TO SCHOOL: origin=driver location, destination=school
            if origin is None:
                latest_loc = await self._get_latest_bus_location(bus_id)
                if latest_loc is not None:
                    origin = latest_loc
            destination = school_coords
            logger.info(f"Route (to_school): origin={origin}, destination=school {destination}")
        else:
            # FROM SCHOOL: origin=school, destination=farthest student from school
            origin = school_coords
            # Destination will be determined after optimization (farthest student)
            # For now, use the last student in stops as placeholder
            destination = None
            if stops:
                # Find the student farthest from school (will be last drop-off)
                destination = await self._get_farthest_student_coords(stops, school_coords)
            logger.info(f"Route (from_school): origin=school {origin}, destination=farthest student {destination}")

        # Optimize route using Google Maps
        if self.gmaps_client and len(stops) > 0 and origin is not None and destination is not None:
            optimized_route = await self._optimize_with_google_maps(
                bus_id, stops, origin, destination
            )
        else:
            optimized_route = OptimizedRouteResponse(
                bus_id=bus_id,
                stops=stops,
                origin=(RoutePoint(latitude=origin[0], longitude=origin[1]) if origin else None),
                destination=(RoutePoint(latitude=destination[0], longitude=destination[1]) if destination else None),
                total_distance_meters=0,
                total_duration_seconds=0,
                generated_at=datetime.utcnow()
            )
        
        # Cache the route for 30 minutes (1800 seconds)
        try:
            import json
            route_dict = {
                "bus_id": optimized_route.bus_id,
                "stops": [stop.dict() for stop in optimized_route.stops],
                "origin": (optimized_route.origin.dict() if optimized_route.origin else None),
                "destination": (optimized_route.destination.dict() if optimized_route.destination else None),
                "total_distance_meters": optimized_route.total_distance_meters,
                "total_duration_seconds": optimized_route.total_duration_seconds,
                "generated_at": optimized_route.generated_at.isoformat(),
                "overview_polyline": getattr(optimized_route, "overview_polyline", None),
            }
            await redis_manager.set(cache_key, json.dumps(route_dict), ex=1800)
        except Exception as e:
            logger.error(f"Failed to cache route: {str(e)}")
        
        return optimized_route
    
    async def _get_bus_with_students(self, bus_id: str) -> Optional[BusModel]:
        """Get bus with related students"""
        query = select(BusModel).where(BusModel.id == bus_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_student_stops(self, bus_id: str) -> List[RouteStop]:
        """Get list of students assigned to bus with their coordinates"""
        # Eager-load related student to avoid async lazy-load (greenlet) issues
        query = (
            select(StudentBusAssignment)
            .options(selectinload(StudentBusAssignment.student))
            .where(StudentBusAssignment.bus_id == bus_id)
        )
        result = await self.db.execute(query)
        assignments = result.scalars().all()
        logger.info(f"Route: fetched {len(assignments)} assignments for bus {bus_id}")
        
        stops = []
        for assignment in assignments:
            student = assignment.student
            
            # Skip students without coordinates
            if student.latitude is None or student.longitude is None:
                logger.warning(
                    f"Student {student.id} ({student.full_name}) "
                    f"has no coordinates, skipping from route"
                )
                continue
            
            stop = RouteStop(
                student_id=student.id,
                full_name=student.full_name,
                student_number=student.student_number,
                address=student.address or "",
                latitude=student.latitude,
                longitude=student.longitude,
                sequence_order=len(stops) + 1  # Will be updated after optimization
            )
            stops.append(stop)
            logger.info(
                f"Route Stop: student_id={stop.student_id}, name={stop.full_name}, lat={stop.latitude}, lng={stop.longitude}"
            )

        logger.info(f"Route: {len(stops)} stops with coordinates remain for bus {bus_id}")
        return stops
    
    async def _get_latest_bus_location(self, bus_id: str) -> Optional[Tuple[float, float]]:
        """Fetch latest reported bus location as (lat, lng)."""
        query = (
            select(BusLocationModel)
            .where(BusLocationModel.bus_id == bus_id)
            .order_by(BusLocationModel.timestamp.desc())
        )
        result = await self.db.execute(query)
        latest = result.scalars().first()
        if latest is None:
            return None
        try:
            # BusLocation uses DECIMAL; cast to float
            return (float(latest.latitude), float(latest.longitude))
        except Exception:
            return None

    async def _get_school_coordinates(self, bus_id: str) -> Optional[Tuple[float, float]]:
        """Resolve school's coordinates for the bus via DB → cache → geocode."""
        # Find bus and its school
        bus_query = select(BusModel).where(BusModel.id == bus_id)
        bus_result = await self.db.execute(bus_query)
        bus = bus_result.scalar_one_or_none()
        if bus is None:
            return None

        school_query = select(SchoolModel).where(SchoolModel.id == bus.school_id)
        school_result = await self.db.execute(school_query)
        school = school_result.scalar_one_or_none()
        if school is None:
            return None

        # 1. First check if coordinates are stored in database
        if school.latitude is not None and school.longitude is not None:
            logger.info(f"Using stored school coordinates for {school.id}: ({school.latitude}, {school.longitude})")
            return (float(school.latitude), float(school.longitude))

        # 2. Fallback: Try redis cache
        if not getattr(school, "school_address", None):
            return None
            
        cache_key = f"school_coord:{school.id}"
        try:
            cached = await redis_manager.get(cache_key)
        except Exception:
            cached = None
        if cached:
            try:
                import json
                obj = json.loads(cached)
                logger.info(f"Using cached school coordinates for {school.id}")
                return (obj.get("lat"), obj.get("lng"))
            except Exception:
                pass

        # 3. Last resort: Geocode via Google Maps if client available
        if not self.gmaps_client:
            return None
        try:
            geocode = self.gmaps_client.geocode(school.school_address)
            if geocode and len(geocode) > 0:
                loc = geocode[0]["geometry"]["location"]
                lat, lng = loc["lat"], loc["lng"]
                logger.info(f"Geocoded school address '{school.school_address}' -> ({lat}, {lng})")
                # Cache long-lived (30 days)
                try:
                    import json
                    await redis_manager.set(cache_key, json.dumps({"lat": lat, "lng": lng}), ex=60*60*24*30)
                except Exception:
                    pass
                return (lat, lng)
        except Exception as e:
            logger.error(f"Failed to geocode school address: {str(e)}")
        return None

    async def _get_farthest_student_coords(
        self,
        stops: List[RouteStop],
        school_coords: Optional[Tuple[float, float]]
    ) -> Optional[Tuple[float, float]]:
        """
        Find the student farthest from school (straight-line distance).
        This student will be the last drop-off in from_school mode.
        """
        if not stops:
            return None
        if school_coords is None:
            # If no school coords, just use the last stop
            return (stops[-1].latitude, stops[-1].longitude)
        
        import math
        
        def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
            """Calculate haversine distance in meters"""
            R = 6371000  # Earth radius in meters
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            delta_phi = math.radians(lat2 - lat1)
            delta_lambda = math.radians(lng2 - lng1)
            a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c
        
        school_lat, school_lng = school_coords
        farthest_stop = None
        max_distance = -1
        
        for stop in stops:
            dist = haversine_distance(school_lat, school_lng, stop.latitude, stop.longitude)
            if dist > max_distance:
                max_distance = dist
                farthest_stop = stop
        
        if farthest_stop:
            logger.info(
                f"Farthest student from school: {farthest_stop.full_name} "
                f"at ({farthest_stop.latitude}, {farthest_stop.longitude}), distance: {max_distance:.0f}m"
            )
            return (farthest_stop.latitude, farthest_stop.longitude)
        return None

    async def _optimize_with_google_maps(
        self,
        bus_id: str,
        stops: List[RouteStop],
        origin: Tuple[float, float],
        destination: Tuple[float, float],
    ) -> OptimizedRouteResponse:
        """
        Optimize route using Google Maps Directions API
        Uses waypoint optimization to find the best order
        
        Args:
            bus_id: The bus ID for the response
            stops: List of route stops with coordinates
            
        Returns:
            Optimized route response
        """
        if len(stops) < 1:
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=stops,
                total_distance_meters=0,
                total_duration_seconds=0,
                generated_at=datetime.utcnow()
            )
        
        try:
            # Prepare coordinates for Google Maps API
            waypoints = [(stop.latitude, stop.longitude) for stop in stops]
            logger.info(
                f"Route: optimizing with origin={origin}, destination={destination}, waypoints={len(waypoints)}"
            )
            
            # Call Google Maps Directions API with waypoint optimization
            result = self.gmaps_client.directions(
                origin=origin,
                destination=destination,
                waypoints=waypoints,
                optimize_waypoints=True,
                mode="driving",
            )
            
            if not result or len(result) == 0:
                logger.warning("Google Maps returned empty result")
                return OptimizedRouteResponse(
                    bus_id=bus_id,
                    stops=stops,
                    total_distance_meters=0,
                    total_duration_seconds=0,
                    generated_at=datetime.utcnow()
                )
            
            # Extract optimization information
            optimized_route_info = result[0]
            
            # Get the optimized waypoint order
            waypoint_order = optimized_route_info.get("waypoint_order", [])
            logger.info(f"Route: waypoint_order={waypoint_order}")
            
            # Reorder stops based on optimization
            optimized_stops = []

            for waypoint_idx in waypoint_order:
                if 0 <= waypoint_idx < len(stops):
                    optimized_stops.append(stops[waypoint_idx])
                    s = stops[waypoint_idx]
                    logger.info(
                        f"Optimized Stop: student_id={s.student_id}, name={s.full_name}, lat={s.latitude}, lng={s.longitude}"
                    )
            
            # Update sequence order
            for idx, stop in enumerate(optimized_stops, 1):
                stop.sequence_order = idx
            
            # Calculate total distance and duration
            total_distance = 0
            total_duration = 0
            
            legs = optimized_route_info.get("legs", [])
            for leg in legs:
                total_distance += leg.get("distance", {}).get("value", 0)
                total_duration += leg.get("duration", {}).get("value", 0)
            
            logger.info(
                f"Route optimized for bus {bus_id}: {len(optimized_stops)} stops, "
                f"distance: {total_distance}m, duration: {total_duration}s"
            )
            
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=optimized_stops,
                origin=RoutePoint(latitude=origin[0], longitude=origin[1]),
                destination=RoutePoint(latitude=destination[0], longitude=destination[1]),
                total_distance_meters=total_distance,
                total_duration_seconds=total_duration,
                generated_at=datetime.utcnow(),
                overview_polyline=optimized_route_info.get("overview_polyline", {}).get("points")
            )
            
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps API error: {str(e)}")
            logger.warning(
                "Directions API may not be enabled in Google Cloud Console. "
                "Enable it at: https://console.cloud.google.com/apis/library/directions-backend.googleapis.com"
            )
            # Return unoptimized route with fallback polyline on API error
            # Generate simple polyline from origin -> stops -> destination
            import polyline
            fallback_coords = []
            if origin:
                fallback_coords.append((origin[0], origin[1]))
            for stop in stops:
                fallback_coords.append((stop.latitude, stop.longitude))
            if destination:
                fallback_coords.append((destination[0], destination[1]))
            fallback_polyline = polyline.encode(fallback_coords) if fallback_coords else None
            
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=stops,
                origin=RoutePoint(latitude=origin[0], longitude=origin[1]) if origin else None,
                destination=RoutePoint(latitude=destination[0], longitude=destination[1]) if destination else None,
                total_distance_meters=0,
                total_duration_seconds=0,
                generated_at=datetime.utcnow(),
                overview_polyline=fallback_polyline
            )
        except Exception as e:
            logger.error(f"Unexpected error optimizing route: {str(e)}")
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=stops,
                origin=RoutePoint(latitude=origin[0], longitude=origin[1]) if origin else None,
                destination=RoutePoint(latitude=destination[0], longitude=destination[1]) if destination else None,
                total_distance_meters=0,
                total_duration_seconds=0,
                generated_at=datetime.utcnow()
            )
    
    async def invalidate_route_cache(self, bus_id: str) -> None:
        """Invalidate cached route for a bus"""
        try:
            cache_key = f"route:{bus_id}"
            await redis_manager.delete(cache_key)
            logger.info(f"Route cache invalidated for bus {bus_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate cache for bus {bus_id}: {str(e)}")
    
    async def invalidate_all_routes_cache(self) -> None:
        """Invalidate all cached routes"""
        try:
            pattern = "route:*"
            await redis_manager.delete_pattern(pattern)
            logger.info("All route caches invalidated")
        except Exception as e:
            logger.error(f"Failed to invalidate all route caches: {str(e)}")


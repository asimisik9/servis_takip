# app/services/route_service.py
"""
Route optimization service using Google Maps API
Optimizes the order of student pickups for a bus route
"""

import logging
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import googlemaps
from datetime import datetime

from ..database.models.bus import Bus as BusModel
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..database.models.student import Student as StudentModel
from ..database.schemas.route import RouteResponse, RouteStop, OptimizedRouteResponse
from ..core.config import settings
from ..core.redis import redis_manager

logger = logging.getLogger(__name__)


class RouteService:
    """Service for calculating and optimizing bus routes"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gmaps_client = None
        self._initialize_gmaps_client()
    
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
    
    async def get_optimized_route(self, bus_id: str) -> OptimizedRouteResponse:
        """
        Get optimized route for a bus with all assigned students
        
        Args:
            bus_id: UUID of the bus
            
        Returns:
            OptimizedRouteResponse with optimized stops and total distance/duration
        """
        # Check cache first
        cache_key = f"route:{bus_id}"
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
        
        if not stops:
            logger.warning(f"No students assigned to bus {bus_id}")
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=[],
                total_distance_meters=0,
                total_duration_seconds=0,
                generated_at=datetime.utcnow()
            )
        
        # Optimize route using Google Maps
        if self.gmaps_client and len(stops) > 1:
            optimized_route = await self._optimize_with_google_maps(bus_id, stops)
        else:
            optimized_route = OptimizedRouteResponse(
                bus_id=bus_id,
                stops=stops,
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
                "total_distance_meters": optimized_route.total_distance_meters,
                "total_duration_seconds": optimized_route.total_duration_seconds,
                "generated_at": optimized_route.generated_at.isoformat()
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
        query = select(StudentBusAssignment).where(
            StudentBusAssignment.bus_id == bus_id
        )
        result = await self.db.execute(query)
        assignments = result.scalars().all()
        
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
        
        return stops
    
    async def _optimize_with_google_maps(
        self, 
        bus_id: str,
        stops: List[RouteStop]
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
        if len(stops) < 2:
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=stops,
                total_distance_meters=0,
                total_duration_seconds=0,
                generated_at=datetime.utcnow()
            )
        
        try:
            # Prepare coordinates for Google Maps API
            origin = (stops[0].latitude, stops[0].longitude)
            destination = (stops[-1].latitude, stops[-1].longitude)
            waypoints = [(stop.latitude, stop.longitude) for stop in stops[1:-1]]
            
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
            
            # Reorder stops based on optimization
            optimized_stops = [stops[0]]  # Start with first stop
            
            for waypoint_idx in waypoint_order:
                if 0 <= waypoint_idx + 1 < len(stops):
                    optimized_stops.append(stops[waypoint_idx + 1])
            
            # Add last stop if not already included
            if stops[-1] not in optimized_stops:
                optimized_stops.append(stops[-1])
            
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
                total_distance_meters=total_distance,
                total_duration_seconds=total_duration,
                generated_at=datetime.utcnow()
            )
            
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps API error: {str(e)}")
            # Return unoptimized route on API error
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=stops,
                total_distance_meters=0,
                total_duration_seconds=0,
                generated_at=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Unexpected error optimizing route: {str(e)}")
            return OptimizedRouteResponse(
                bus_id=bus_id,
                stops=stops,
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


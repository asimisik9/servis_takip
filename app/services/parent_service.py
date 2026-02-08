from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from typing import List, Optional
from datetime import date, datetime
import httpx
import logging

from ..database.models.student import Student as StudentModel
from ..database.models.parent_student_relation import ParentStudentRelation
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..database.models.bus_location import BusLocation
from ..database.models.attendance_log import AttendanceLog
from ..database.models.school import School as SchoolModel
from sqlalchemy.orm import joinedload
from ..database.models.bus import Bus
from ..database.models.user import User
from ..database.schemas.dashboard import DashboardResponse
from ..database.schemas.student import StudentAddressUpdate
from .student_service import StudentService
from ..core.config import settings
from ..core.redis import redis_manager

logger = logging.getLogger(__name__)

class ParentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gmaps_api_key = settings.GOOGLE_MAPS_API_KEY
        if not self.gmaps_api_key:
            logger.warning("Google Maps API key not configured for ETA calculation")

    async def update_student_address(self, parent_id: str, student_id: str, address_update: StudentAddressUpdate):
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")

        # Use StudentService to update address
        student_service = StudentService(self.db)
        
        # We need to construct a StudentUpdate object, but StudentService.update_student expects StudentUpdate
        # Let's import StudentUpdate inside the method to avoid circular imports if any, or just use what we have.
        from ..database.schemas.student import StudentUpdate
        
        update_data = StudentUpdate(address=address_update.address)
        return await student_service.update_student(student_id, update_data)

    async def get_parent_students(self, parent_id: str) -> List[StudentModel]:
        query = select(StudentModel).options(joinedload(StudentModel.school)).join(ParentStudentRelation).where(ParentStudentRelation.parent_id == parent_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_student_bus_location(self, parent_id: str, student_id: str) -> BusLocation:
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")

        # Get assignment
        query = select(StudentBusAssignment).where(StudentBusAssignment.student_id == student_id)
        assignment = (await self.db.execute(query)).scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Student has no assigned bus")

        # Get location
        query = select(BusLocation).where(BusLocation.bus_id == assignment.bus_id).order_by(BusLocation.timestamp.desc())
        bus_location = (await self.db.execute(query)).scalars().first()
        
        if not bus_location:
            raise HTTPException(status_code=404, detail="Bus location not found")
            
        return bus_location

    async def get_student_attendance_history(self, parent_id: str, student_id: str, filter_date: Optional[date] = None) -> List[AttendanceLog]:
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")

        query = select(AttendanceLog).where(AttendanceLog.student_id == student_id)
        
        if filter_date:
            start = datetime.combine(filter_date, datetime.min.time())
            end = datetime.combine(filter_date, datetime.max.time())
            query = query.where(AttendanceLog.log_time >= start, AttendanceLog.log_time <= end)
            
        query = query.order_by(AttendanceLog.log_time.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_student_dashboard_data(self, parent_id: str, student_id: str) -> DashboardResponse:
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")

        # Get student with school info
        student_query = select(StudentModel).options(
            joinedload(StudentModel.school)
        ).where(StudentModel.id == student_id)
        student = (await self.db.execute(student_query)).scalar_one_or_none()

        # Get assignment with Bus and Driver
        query = select(StudentBusAssignment).options(
            joinedload(StudentBusAssignment.bus).joinedload(Bus.current_driver)
        ).where(StudentBusAssignment.student_id == student_id)
        
        assignment = (await self.db.execute(query)).scalar_one_or_none()
        
        if not assignment or not assignment.bus:
             return DashboardResponse(
                 tripStatus="inactive",
                 minutesLeft=None,
                 driverName=None,
                 driverPhone=None,
                 plateNumber=None
             )

        bus = assignment.bus
        driver = bus.current_driver
        
        # Get latest bus location
        query = select(BusLocation).where(BusLocation.bus_id == bus.id).order_by(BusLocation.timestamp.desc())
        location = (await self.db.execute(query)).scalars().first()
        
        trip_status = "inactive"
        minutes_left = None
        
        if location:
            # Get trip_type from Redis (set by driver app)
            # This syncs parent app with driver's manual trip selection
            cached_trip_type = await redis_manager.get(f"bus:{bus.id}:trip_type")
            
            if cached_trip_type:
                # Map driver trip_type to parent trip_status
                # to_school -> driver going to pick up students -> ETA to student home
                # from_school -> driver bringing students home -> ETA to student home
                trip_status = "to_school" if cached_trip_type == "to_school" else "to_home"
            else:
                # Fallback to time-based if driver hasn't set trip_type
                now = datetime.now()
                trip_status = "to_school" if now.hour < 12 else "to_home"
            
            # Calculate real ETA using Google Maps
            minutes_left = await self._calculate_eta(
                bus_location=location,
                student=student,
                trip_status=trip_status
            )

        return DashboardResponse(
            tripStatus=trip_status,
            minutesLeft=minutes_left,
            driverName=driver.full_name if driver else None,
            driverPhone=driver.phone_number if driver else None,
            plateNumber=bus.plate_number,
            busId=bus.id
        )

    async def _calculate_eta(
        self,
        bus_location: BusLocation,
        student: StudentModel,
        trip_status: str
    ) -> Optional[int]:
        """
        Calculate ETA from bus to destination using Google Directions API.
        
        - to_school: ETA from bus to school (student is waiting at home)
        - to_home: ETA from bus to student's home (student is on bus going home)
        
        Returns minutes left or None if calculation fails.
        """
        if not self.gmaps_api_key:
            logger.warning("Google Maps API key not available for ETA calculation")
            return None
        
        # Origin: Bus current location
        origin_lat = float(bus_location.latitude)
        origin_lng = float(bus_location.longitude)
        
        # Destination depends on trip type
        if student.latitude is None or student.longitude is None:
            logger.warning(f"Student {student.id} has no coordinates for ETA calculation")
            return None
        
        dest_lat = float(student.latitude)
        dest_lng = float(student.longitude)
        logger.info(f"ETA ({trip_status}): bus ({origin_lat}, {origin_lng}) -> student home ({dest_lat}, {dest_lng})")
        
        # Check cache first
        cache_key = f"eta:{bus_location.bus_id}:{student.id}:{trip_status}"
        try:
            import json
            cached = await redis_manager.get(cache_key)
            if cached:
                cached_data = json.loads(cached)
                logger.info(f"ETA cache hit for student {student.id}: {cached_data['minutes']} minutes")
                return cached_data['minutes']
        except Exception:
            pass
        
        # Call Google Directions API (legacy but enabled)
        try:
            url = "https://maps.googleapis.com/maps/api/directions/json"
            
            params = {
                "origin": f"{origin_lat},{origin_lng}",
                "destination": f"{dest_lat},{dest_lng}",
                "mode": "driving",
                "departure_time": "now",
                "key": self.gmaps_api_key
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                
                if response.status_code != 200:
                    logger.error(f"Directions API error: {response.status_code} - {response.text}")
                    return None
                
                result = response.json()
            
            # Check API response status
            if result.get('status') != 'OK':
                logger.error(f"Directions API returned status: {result.get('status')} - {result.get('error_message', '')}")
                return None
            
            if not result.get('routes') or len(result['routes']) == 0:
                logger.error("Directions API returned empty routes")
                return None
            
            # Get duration from the first route's first leg
            leg = result['routes'][0]['legs'][0]
            
            # Use duration_in_traffic if available (more accurate with real-time traffic)
            if 'duration_in_traffic' in leg:
                duration_seconds = leg['duration_in_traffic']['value']
            else:
                duration_seconds = leg['duration']['value']
            
            minutes = round(duration_seconds / 60)
            distance_text = leg['distance']['text']
            
            logger.info(
                f"ETA calculated for student {student.id}: {minutes} minutes "
                f"(distance: {distance_text})"
            )
            
            # Cache for 2 minutes (ETA changes frequently with traffic)
            try:
                import json
                await redis_manager.set(cache_key, json.dumps({"minutes": minutes}), ex=120)
            except Exception:
                pass
            
            return minutes
            
        except Exception as e:
            logger.error(f"Failed to calculate ETA: {str(e)}")
            return None

    async def report_absence(self, parent_id: str, student_id: str, absence_date: Optional[date] = None, reason: Optional[str] = None):
        from uuid import uuid4
        from ..database.models.absence import Absence
        
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")
        
        target_date = absence_date or date.today()
        
        # Check if already reported for this date
        from sqlalchemy import and_
        existing = await self.db.execute(
            select(Absence).where(
                and_(
                    Absence.student_id == student_id,
                    Absence.absence_date == target_date
                )
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Absence already reported for this date")
        
        absence = Absence(
            id=str(uuid4()),
            student_id=student_id,
            parent_id=parent_id,
            absence_date=target_date,
            reason=reason
        )
        self.db.add(absence)
        await self.db.commit()
        await self.db.refresh(absence)
        
        logger.info(f"Absence reported: student={student_id}, date={target_date}, parent={parent_id}")
        return absence

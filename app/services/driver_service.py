from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Optional

from ..database import models
from ..database.schemas.attendance_log import AttendanceLogCreate, AttendanceLogRequest
from ..database.schemas.bus_location import BusLocationCreate
from ..core.redis import redis_manager
from ..core.exceptions import ResourceNotFoundException, BusinessRuleException
from .route_progress_service import RouteProgressService
from .trip_session_service import TripSessionService

class DriverService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _to_db_naive_utc(value: datetime) -> datetime:
        """
        Normalize datetime values for DB columns defined as TIMESTAMP WITHOUT TIME ZONE.
        Keeps naive values as-is and converts aware values to naive UTC.
        """
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    async def get_driver_bus(self, driver_id: str) -> Optional[models.Bus]:
        query = select(models.Bus).where(models.Bus.current_driver_id == driver_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_driver_bus_id(self, driver_id: str) -> Optional[str]:
        """Get the bus ID assigned to a driver"""
        bus = await self.get_driver_bus(driver_id)
        return bus.id if bus else None

    async def get_roster(self, driver_id: str) -> List[models.Student]:
        bus = await self.get_driver_bus(driver_id)
        if not bus:
            raise ResourceNotFoundException("Driver has no assigned bus")
        
        # Eager-load relations used by Student response schema to avoid async lazy-load
        # errors during FastAPI serialization.
        query = (
            select(models.Student)
            .join(models.StudentBusAssignment)
            .where(models.StudentBusAssignment.bus_id == bus.id)
            .options(
                selectinload(models.Student.school),
                selectinload(models.Student.organization),
            )
            .order_by(models.Student.full_name.asc())
        )
        result = await self.db.execute(query)
        return result.scalars().unique().all()

    async def create_attendance_log(self, driver_id: str, attendance: AttendanceLogRequest) -> models.AttendanceLog:
        bus = await self.get_driver_bus(driver_id)
        if not bus:
            raise ResourceNotFoundException("Driver has no assigned bus")

        trip_session_service = TripSessionService(self.db)
        requested_trip_type = attendance.trip_type.value if attendance.trip_type else None
        trip_session, resolved_trip_type = await trip_session_service.resolve_session_for_attendance(
            bus_id=bus.id,
            driver_id=driver_id,
            requested_trip_type=requested_trip_type,
        )

        if attendance.idempotency_key:
            existing_by_key = await self._get_log_by_idempotency_key(attendance.idempotency_key)
            if existing_by_key:
                if (
                    existing_by_key.driver_id != driver_id
                    or existing_by_key.student_id != attendance.student_id
                    or existing_by_key.bus_id != bus.id
                ):
                    raise BusinessRuleException("Idempotency key already used for a different attendance event")
                return existing_by_key

        assignment = await self._get_student_assignment_for_bus(
            bus_id=bus.id,
            student_id=attendance.student_id,
            lock_for_update=True,
        )
        if not assignment:
            raise BusinessRuleException("Student not assigned to this bus")

        state = await trip_session_service.get_or_create_student_state(
            trip_session_id=trip_session.id,
            student_id=attendance.student_id,
        )
        requested_status = models.AttendanceStatus(attendance.status.value)
        duplicate_log = await self._maybe_return_duplicate_log(state, requested_status)
        if duplicate_log:
            return duplicate_log

        self._validate_attendance_transition(state, requested_status)

        server_now = datetime.now(timezone.utc)
        new_log = models.AttendanceLog(
            id=str(uuid4()),
            student_id=attendance.student_id,
            bus_id=bus.id, # Otobüs ID'sini şoförden alıyoruz
            driver_id=driver_id, # Driver ID'sini tokendan alıyoruz
            trip_session_id=trip_session.id,
            status=requested_status,
            latitude=attendance.latitude,
            longitude=attendance.longitude,
            log_time=self._to_db_naive_utc(attendance.log_time),
            recorded_at=server_now,
            idempotency_key=attendance.idempotency_key,
        )
        self.db.add(new_log)
        await self.db.flush()

        state.last_status = requested_status
        state.last_event_at = server_now
        state.last_log_id = new_log.id
        if trip_session_service.should_complete_route(resolved_trip_type, requested_status):
            state.route_completed_at = server_now
        trip_session.last_activity_at = server_now

        await redis_manager.set(f"bus:{bus.id}:trip_type", resolved_trip_type.value, ex=3600)
        await self.db.commit()
        await self.db.refresh(new_log)
        return new_log

    async def update_location(self, driver_id: str, location: BusLocationCreate) -> models.BusLocation:
        bus = await self.get_driver_bus(driver_id)
        if not bus:
            raise ResourceNotFoundException("Driver has no assigned bus")
            
        new_location = models.BusLocation(
            id=str(uuid4()),
            bus_id=bus.id,
            latitude=location.latitude,
            longitude=location.longitude,
            speed=location.speed,
            timestamp=self._to_db_naive_utc(datetime.now(timezone.utc))
        )
        self.db.add(new_location)
        await self.db.commit()
        await self.db.refresh(new_location)
        return new_location

    async def get_visited_students(self, driver_id: str) -> List[str]:
        bus_id = await self.get_driver_bus_id(driver_id)
        if not bus_id:
            raise ResourceNotFoundException("Driver has no assigned bus")

        trip_session_service = TripSessionService(self.db)
        trip_type = await redis_manager.get(f"bus:{bus_id}:trip_type")
        if trip_type:
            completed = await trip_session_service.get_route_completed_student_ids(
                bus_id=bus_id,
                trip_type=str(trip_type),
            )
        else:
            completed = await trip_session_service.get_today_completed_student_ids_for_bus(bus_id)
        manual = []
        if trip_type:
            try:
                from .route_progress_service import RouteProgressService

                manual = await RouteProgressService().get_visited(bus_id, str(trip_type))
            except Exception:
                manual = []

        return sorted(set(completed).union(manual))

    async def ensure_student_assigned_to_current_bus(self, driver_id: str, student_id: str) -> str:
        bus = await self.get_driver_bus(driver_id)
        if not bus:
            raise ResourceNotFoundException("Driver has no assigned bus")

        assignment = await self._get_student_assignment_for_bus(
            bus_id=bus.id,
            student_id=student_id,
            lock_for_update=False,
        )
        if not assignment:
            raise BusinessRuleException("Student not assigned to this bus")
        return bus.id

    async def reopen_student_route_progress(
        self,
        driver_id: str,
        student_id: str,
        trip_type: str,
    ) -> bool:
        bus = await self.get_driver_bus(driver_id)
        if not bus:
            raise ResourceNotFoundException("Driver has no assigned bus")

        assignment = await self._get_student_assignment_for_bus(
            bus_id=bus.id,
            student_id=student_id,
            lock_for_update=True,
        )
        if not assignment:
            raise BusinessRuleException("Student not assigned to this bus")

        progress_service = RouteProgressService()
        manual_removed = await progress_service.remove_visited(bus.id, trip_type, student_id)

        trip_session_service = TripSessionService(self.db)
        attendance_reopened = await trip_session_service.reopen_student_route(
            bus_id=bus.id,
            trip_type=trip_type,
            student_id=student_id,
            driver_id=driver_id,
        )
        if attendance_reopened:
            await self.db.commit()
        return manual_removed or attendance_reopened

    async def _get_student_assignment_for_bus(
        self,
        bus_id: str,
        student_id: str,
        *,
        lock_for_update: bool,
    ) -> models.StudentBusAssignment | None:
        query = select(models.StudentBusAssignment).where(
            models.StudentBusAssignment.bus_id == bus_id,
            models.StudentBusAssignment.student_id == student_id,
        )
        if lock_for_update:
            query = query.with_for_update()
        return (await self.db.execute(query)).scalar_one_or_none()

    async def _get_log_by_idempotency_key(self, idempotency_key: str) -> models.AttendanceLog | None:
        query = select(models.AttendanceLog).where(models.AttendanceLog.idempotency_key == idempotency_key)
        return (await self.db.execute(query)).scalar_one_or_none()

    async def _maybe_return_duplicate_log(
        self,
        state: models.TripStudentState,
        requested_status: models.AttendanceStatus,
    ) -> models.AttendanceLog | None:
        if state.last_status != requested_status or not state.last_log_id:
            return None
        if state.last_log:
            return state.last_log
        return await self.db.get(models.AttendanceLog, state.last_log_id)

    @staticmethod
    def _validate_attendance_transition(
        state: models.TripStudentState,
        requested_status: models.AttendanceStatus,
    ) -> None:
        if state.last_status is None:
            if requested_status == models.AttendanceStatus.indi:
                raise BusinessRuleException("Cannot mark 'indi' before 'bindi' for this trip")
            return

        if state.last_status == models.AttendanceStatus.indi:
            raise BusinessRuleException("Trip already completed for this student")

        if state.last_status == models.AttendanceStatus.bindi and requested_status == models.AttendanceStatus.bindi:
            raise BusinessRuleException("Duplicate 'bindi' event for this trip")

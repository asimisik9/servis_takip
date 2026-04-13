from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.exceptions import BusinessRuleException
from ..core.redis import redis_manager
from ..database import models


class TripSessionService:
    """Owns current trip/session state used by route and attendance flows."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _today() -> date:
        return date.today()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_trip_type(trip_type: str | models.TripType) -> models.TripType:
        if isinstance(trip_type, models.TripType):
            return trip_type
        try:
            return models.TripType(trip_type)
        except ValueError as exc:
            raise BusinessRuleException("trip_type must be 'to_school' or 'from_school'") from exc

    @staticmethod
    def should_complete_route(
        trip_type: str | models.TripType,
        attendance_status: str | models.AttendanceStatus,
    ) -> bool:
        normalized_trip_type = (
            trip_type.value if isinstance(trip_type, models.TripType) else str(trip_type)
        )
        normalized_status = (
            attendance_status.value
            if isinstance(attendance_status, models.AttendanceStatus)
            else str(attendance_status)
        )
        return (
            (normalized_trip_type == models.TripType.to_school.value and normalized_status == models.AttendanceStatus.bindi.value)
            or (normalized_trip_type == models.TripType.from_school.value and normalized_status == models.AttendanceStatus.indi.value)
        )

    async def get_or_create_session(
        self,
        bus_id: str,
        trip_type: str | models.TripType,
        driver_id: Optional[str] = None,
        service_date: Optional[date] = None,
    ) -> models.TripSession:
        resolved_trip_type = self._parse_trip_type(trip_type)
        resolved_date = service_date or self._today()

        query = select(models.TripSession).where(
            models.TripSession.bus_id == bus_id,
            models.TripSession.trip_type == resolved_trip_type,
            models.TripSession.service_date == resolved_date,
        )
        existing = (await self.db.execute(query)).scalar_one_or_none()
        if existing:
            existing.last_activity_at = self._now()
            if driver_id and existing.driver_id is None:
                existing.driver_id = driver_id
            await self.db.flush()
            return existing

        session = models.TripSession(
            id=str(uuid4()),
            bus_id=bus_id,
            driver_id=driver_id,
            trip_type=resolved_trip_type,
            service_date=resolved_date,
            started_at=self._now(),
            last_activity_at=self._now(),
        )
        self.db.add(session)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            session = (await self.db.execute(query)).scalar_one_or_none()
            if session:
                return session
            raise
        return session

    async def get_existing_session(
        self,
        bus_id: str,
        trip_type: str | models.TripType,
        service_date: Optional[date] = None,
        *,
        for_update: bool = False,
    ) -> models.TripSession | None:
        resolved_trip_type = self._parse_trip_type(trip_type)
        resolved_date = service_date or self._today()
        query = select(models.TripSession).where(
            models.TripSession.bus_id == bus_id,
            models.TripSession.trip_type == resolved_trip_type,
            models.TripSession.service_date == resolved_date,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.db.execute(query)).scalar_one_or_none()

    async def resolve_session_for_attendance(
        self,
        bus_id: str,
        driver_id: str,
        requested_trip_type: Optional[str] = None,
    ) -> tuple[models.TripSession, models.TripType]:
        if requested_trip_type:
            resolved_trip_type = self._parse_trip_type(requested_trip_type)
        else:
            resolved_trip_type = await self._get_trip_type_from_cache(bus_id)
            if resolved_trip_type is None:
                resolved_trip_type = await self._infer_trip_type_from_sessions(bus_id)
            if resolved_trip_type is None:
                raise BusinessRuleException(
                    "Trip type is required before logging attendance. Fetch route first or send trip_type."
                )

        session = await self.get_or_create_session(
            bus_id=bus_id,
            trip_type=resolved_trip_type,
            driver_id=driver_id,
        )
        return session, resolved_trip_type

    async def get_student_state(
        self,
        trip_session_id: str,
        student_id: str,
        *,
        for_update: bool = False,
    ) -> models.TripStudentState | None:
        query = (
            select(models.TripStudentState)
            .options(selectinload(models.TripStudentState.last_log))
            .where(
                models.TripStudentState.trip_session_id == trip_session_id,
                models.TripStudentState.student_id == student_id,
            )
        )
        if for_update:
            query = query.with_for_update()
        return (await self.db.execute(query)).scalar_one_or_none()

    async def get_or_create_student_state(
        self,
        trip_session_id: str,
        student_id: str,
    ) -> models.TripStudentState:
        state = await self.get_student_state(trip_session_id, student_id, for_update=True)
        if state:
            return state

        state = models.TripStudentState(
            id=str(uuid4()),
            trip_session_id=trip_session_id,
            student_id=student_id,
        )
        self.db.add(state)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            state = await self.get_student_state(trip_session_id, student_id, for_update=True)
            if state:
                return state
            raise
        return state

    async def get_route_completed_student_ids(
        self,
        bus_id: str,
        trip_type: str | models.TripType,
        service_date: Optional[date] = None,
    ) -> list[str]:
        resolved_trip_type = self._parse_trip_type(trip_type)
        resolved_date = service_date or self._today()
        query = (
            select(models.TripStudentState.student_id)
            .join(models.TripSession, models.TripSession.id == models.TripStudentState.trip_session_id)
            .where(
                models.TripSession.bus_id == bus_id,
                models.TripSession.trip_type == resolved_trip_type,
                models.TripSession.service_date == resolved_date,
                models.TripStudentState.route_completed_at.is_not(None),
            )
        )
        rows = (await self.db.execute(query)).all()
        return [str(student_id) for (student_id,) in rows]

    async def reopen_student_route(
        self,
        *,
        bus_id: str,
        trip_type: str | models.TripType,
        student_id: str,
        driver_id: str,
        service_date: Optional[date] = None,
    ) -> bool:
        session = await self.get_existing_session(
            bus_id=bus_id,
            trip_type=trip_type,
            service_date=service_date,
            for_update=True,
        )
        if session is None:
            return False

        state = await self.get_student_state(session.id, student_id, for_update=True)
        active_logs = await self._get_active_logs_for_student_session(
            trip_session_id=session.id,
            student_id=student_id,
            for_update=True,
        )
        if not active_logs:
            if state is None:
                return False
            changed = self._apply_state_from_logs(state, [], session.trip_type)
            if changed:
                session.last_activity_at = self._now()
                session.ended_at = None
                await self.db.flush()
            return changed

        remaining_logs, logs_to_revert = self._split_logs_for_reopen(session.trip_type, active_logs)
        if not logs_to_revert and state is not None and state.route_completed_at is None:
            return False

        now = self._now()
        changed = False
        for log in logs_to_revert:
            log.reverted_at = now
            log.reverted_by_driver_id = driver_id
            changed = True

        if state is None and remaining_logs:
            state = await self.get_or_create_student_state(session.id, student_id)
        if state is not None:
            changed = self._apply_state_from_logs(state, remaining_logs, session.trip_type) or changed

        if changed:
            session.last_activity_at = now
            session.ended_at = None
            await self.db.flush()
        return changed

    async def get_today_completed_student_ids_for_bus(
        self,
        bus_id: str,
        service_date: Optional[date] = None,
    ) -> list[str]:
        resolved_date = service_date or self._today()
        query = (
            select(models.TripStudentState.student_id)
            .join(models.TripSession, models.TripSession.id == models.TripStudentState.trip_session_id)
            .where(
                models.TripSession.bus_id == bus_id,
                models.TripSession.service_date == resolved_date,
                models.TripStudentState.route_completed_at.is_not(None),
            )
        )
        rows = (await self.db.execute(query)).all()
        return [str(student_id) for (student_id,) in rows]

    async def _get_active_logs_for_student_session(
        self,
        *,
        trip_session_id: str,
        student_id: str,
        for_update: bool = False,
    ) -> list[models.AttendanceLog]:
        query = (
            select(models.AttendanceLog)
            .where(
                models.AttendanceLog.trip_session_id == trip_session_id,
                models.AttendanceLog.student_id == student_id,
                models.AttendanceLog.reverted_at.is_(None),
            )
            .order_by(
                models.AttendanceLog.recorded_at.is_(None).asc(),
                models.AttendanceLog.recorded_at.asc(),
                models.AttendanceLog.log_time.asc(),
                models.AttendanceLog.id.asc(),
            )
        )
        if for_update:
            query = query.with_for_update()
        return (await self.db.execute(query)).scalars().all()

    def _split_logs_for_reopen(
        self,
        trip_type: str | models.TripType,
        logs: list[models.AttendanceLog],
    ) -> tuple[list[models.AttendanceLog], list[models.AttendanceLog]]:
        completion_index: int | None = None
        for idx, log in enumerate(logs):
            if self.should_complete_route(trip_type, log.status):
                completion_index = idx
        if completion_index is None:
            return list(logs), []
        return list(logs[:completion_index]), list(logs[completion_index:])

    def _apply_state_from_logs(
        self,
        state: models.TripStudentState,
        logs: list[models.AttendanceLog],
        trip_type: str | models.TripType,
    ) -> bool:
        current_snapshot = (
            state.last_status,
            state.last_log_id,
            state.last_event_at,
            state.route_completed_at,
        )
        if not logs:
            next_snapshot = (None, None, None, None)
            state.last_status = None
            state.last_log_id = None
            state.last_event_at = None
            state.route_completed_at = None
            state.last_log = None
        else:
            last_log = logs[-1]
            route_completed_at = None
            for log in logs:
                if self.should_complete_route(trip_type, log.status):
                    route_completed_at = self._event_timestamp(log)
            next_snapshot = (
                last_log.status,
                last_log.id,
                self._event_timestamp(last_log),
                route_completed_at,
            )
            state.last_status = last_log.status
            state.last_log_id = last_log.id
            state.last_event_at = self._event_timestamp(last_log)
            state.route_completed_at = route_completed_at
            state.last_log = last_log
        return current_snapshot != next_snapshot

    @staticmethod
    def _event_timestamp(log: models.AttendanceLog) -> datetime:
        if log.recorded_at is not None:
            return log.recorded_at
        if log.log_time.tzinfo is not None:
            return log.log_time
        return log.log_time.replace(tzinfo=timezone.utc)

    async def _get_trip_type_from_cache(self, bus_id: str) -> models.TripType | None:
        cached = await redis_manager.get(f"bus:{bus_id}:trip_type")
        if not cached:
            return None
        try:
            return self._parse_trip_type(str(cached))
        except BusinessRuleException:
            return None

    async def _infer_trip_type_from_sessions(self, bus_id: str) -> models.TripType | None:
        query = (
            select(models.TripSession.trip_type)
            .where(
                models.TripSession.bus_id == bus_id,
                models.TripSession.service_date == self._today(),
            )
            .order_by(models.TripSession.last_activity_at.desc())
        )
        rows = (await self.db.execute(query)).all()
        trip_types = [trip_type for (trip_type,) in rows]
        if len(trip_types) == 1:
            return trip_types[0]
        return None

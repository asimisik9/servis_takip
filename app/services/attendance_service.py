from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Tuple
from datetime import date, datetime

from ..database.models.attendance_log import AttendanceLog
from ..database.models.bus import Bus as BusModel
from ..database.models.school import School as SchoolModel

class AttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_attendance_logs(
        self, 
        start_date: Optional[date] = None, 
        end_date: Optional[date] = None, 
        bus_id: Optional[str] = None, 
        student_id: Optional[str] = None, 
        skip: int = 0, 
        limit: int = 100,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None
    ) -> Tuple[List[AttendanceLog], int]:
        """
        Get attendance logs with tenant filtering and pagination.
        Filters by bus's organization_id.
        Returns: (logs, total_count)
        """
        query = select(AttendanceLog)
        count_query = select(func.count()).select_from(AttendanceLog)
        
        # Tenant filter
        if current_user_org_id is not None:
            if current_user_org_type == "school":
                query = query.join(BusModel).join(SchoolModel).where(
                    SchoolModel.organization_id == current_user_org_id
                )
                count_query = count_query.join(BusModel).join(SchoolModel).where(
                    SchoolModel.organization_id == current_user_org_id
                )
            else:
                query = query.join(BusModel).where(BusModel.organization_id == current_user_org_id)
                count_query = count_query.join(BusModel).where(BusModel.organization_id == current_user_org_id)
        
        if start_date:
            query = query.where(AttendanceLog.log_time >= datetime.combine(start_date, datetime.min.time()))
            count_query = count_query.where(AttendanceLog.log_time >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.where(AttendanceLog.log_time <= datetime.combine(end_date, datetime.max.time()))
            count_query = count_query.where(AttendanceLog.log_time <= datetime.combine(end_date, datetime.max.time()))
        if bus_id:
            query = query.where(AttendanceLog.bus_id == bus_id)
            count_query = count_query.where(AttendanceLog.bus_id == bus_id)
        if student_id:
            query = query.where(AttendanceLog.student_id == student_id)
            count_query = count_query.where(AttendanceLog.student_id == student_id)
        
        # Get total count
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Get paginated results
        query = query.order_by(AttendanceLog.log_time.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

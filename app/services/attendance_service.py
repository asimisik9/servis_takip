from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import date, datetime

from ..database.models.attendance_log import AttendanceLog

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
        limit: int = 100
    ) -> List[AttendanceLog]:
        query = select(AttendanceLog)
        
        if start_date:
            query = query.where(AttendanceLog.timestamp >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.where(AttendanceLog.timestamp <= datetime.combine(end_date, datetime.max.time()))
        if bus_id:
            query = query.where(AttendanceLog.bus_id == bus_id)
        if student_id:
            query = query.where(AttendanceLog.student_id == student_id)
            
        query = query.order_by(AttendanceLog.timestamp.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()

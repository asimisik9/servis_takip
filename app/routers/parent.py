from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Annotated
from datetime import date
from app.database.schemas.user import User
from app.database.schemas.student import Student
from app.database.schemas.bus_location import BusLocation
from app.database.schemas.attendance_log import AttendanceLog
from app.routers.auth import get_current_parent_user

router = APIRouter(
    prefix="/parent",
    tags=["parent"]
)

# Test data (replace this with database calls in production)
from datetime import datetime

test_data = {
    "students": [
        {
            "id": "1",
            "full_name": "Test Student",
            "student_number": "12345",
            "school_id": "1",
            "created_at": datetime.now()
        }
    ],
    "bus_locations": {
        "1": {
            "id": "1",
            "bus_id": "1",
            "latitude": 41.0082,
            "longitude": 28.9784,
            "timestamp": datetime.now()
        }
    },
    "attendance_logs": {
        "1": [
            {
                "id": "1",
                "student_id": "1",
                "bus_id": "1",
                "attended": True,
                "direction": "pickup",
                "timestamp": datetime.now()
            }
        ]
    }
}

@router.get("/me/students", response_model=List[Student])
async def get_parent_students(
    current_user: Annotated[User, Depends(get_current_parent_user)]
):
    """
    Velinin öğrencilerini listeler.
    """
    return test_data["students"]

@router.get("/students/{student_id}/bus/location", response_model=BusLocation)
async def get_student_bus_location(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_parent_user)]
):
    """
    Öğrencinin servisinin anlık konumunu getirir.
    """
    # Verify that the student belongs to the parent
    if student_id not in test_data["bus_locations"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    return test_data["bus_locations"][student_id]

@router.get("/students/{student_id}/attendance/history", response_model=List[AttendanceLog])
async def get_student_attendance_history(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_parent_user)],
    date: date | None = Query(default=None, description="Belirli bir tarihteki yoklama kayıtlarını filtrelemek için kullanılır")
):
    """
    Öğrencinin geçmiş yoklama kayıtlarını listeler.
    Opsiyonel olarak tarih parametresi alır.
    """
    # Verify that the student belongs to the parent
    if student_id not in test_data["attendance_logs"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    logs = test_data["attendance_logs"][student_id]
    if date:
        # Filter logs by date if specified
        logs = [log for log in logs if log["timestamp"].date() == date]
    return logs
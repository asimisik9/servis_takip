"""
This module contains all the Pydantic models (schemas) for the application.
These schemas are used for request/response models in the API.
"""

from .school import School, SchoolCreate, SchoolUpdate, SchoolBase
from .user import User, UserCreate, UserUpdate, UserBase
from .student import Student, StudentCreate, StudentUpdate, StudentBase
from .bus import Bus, BusCreate, BusUpdate, BusBase
from .bus_location import BusLocation, BusLocationCreate, BusLocationUpdate, BusLocationBase
from .attendance_log import AttendanceLog, AttendanceLogCreate, AttendanceLogUpdate, AttendanceLogBase
from .student_bus_assignment import StudentBusAssignment, StudentBusAssignmentCreate, StudentBusAssignmentUpdate, StudentBusAssignmentBase
from .parent_student_relation import ParentStudentRelation, ParentStudentRelationCreate, ParentStudentRelationUpdate, ParentStudentRelationBase
from .notification import Notification, NotificationCreate, NotificationUpdate, NotificationBase

__all__ = [
    "School", "SchoolCreate", "SchoolUpdate", "SchoolBase",
    "User", "UserCreate", "UserUpdate", "UserBase",
    "Student", "StudentCreate", "StudentUpdate", "StudentBase",
    "Bus", "BusCreate", "BusUpdate", "BusBase",
    "BusLocation", "BusLocationCreate", "BusLocationUpdate", "BusLocationBase",
    "AttendanceLog", "AttendanceLogCreate", "AttendanceLogUpdate", "AttendanceLogBase",
    "StudentBusAssignment", "StudentBusAssignmentCreate", "StudentBusAssignmentUpdate", "StudentBusAssignmentBase",
    "ParentStudentRelation", "ParentStudentRelationCreate", "ParentStudentRelationUpdate", "ParentStudentRelationBase",
    "Notification", "NotificationCreate", "NotificationUpdate", "NotificationBase",
]
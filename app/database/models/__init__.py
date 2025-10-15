# app/models/__init__.py

# database modülünden Base'i import edin
from ..database import Base

# Her bir model dosyasını import ederek Base'in onlara erişmesini sağlayın
from .user import User, UserRole
from .school import School
from .student import Student
from .bus import Bus
from .parent_student_relation import ParentStudentRelation
from .student_bus_assignment import StudentBusAssignment
from .attendance_log import AttendanceLog, AttendanceStatus
from .bus_location import BusLocation
from .notification import Notification, NotificationStatus
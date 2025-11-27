from fastapi import APIRouter
from . import users, students, schools, buses, assignments, monitoring

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)

router.include_router(users.router)
router.include_router(students.router)
router.include_router(schools.router)
router.include_router(buses.router)
router.include_router(assignments.router)
router.include_router(monitoring.router)

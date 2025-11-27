from fastapi import APIRouter, Depends, status
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User
from ...database.schemas.student_bus_assignment import StudentBusAssignment
from ...database.schemas.parent_student_relation import ParentStudentRelation
from ...database.schemas.bus import Bus
from ...dependencies import get_db, get_current_admin_user
from ...services.assignment_service import AssignmentService

router = APIRouter(tags=["admin-assignments"])

@router.post("/students/{student_id}/assign-parent", response_model=ParentStudentRelation)
async def assign_parent_to_student(
    student_id: str,
    parent_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    return await service.assign_parent_to_student(unquote(student_id), parent_id)

@router.post("/students/{student_id}/assign-bus", response_model=StudentBusAssignment)
async def assign_bus_to_student(
    student_id: str,
    bus_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    return await service.assign_bus_to_student(unquote(student_id), bus_id)

@router.post("/buses/{bus_id}/assign-driver", response_model=Bus)
async def assign_driver_to_bus(
    bus_id: str,
    driver_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    return await service.assign_driver_to_bus(unquote(bus_id), driver_id)

@router.get("/assignments/student-bus", response_model=List[StudentBusAssignment])
async def list_student_bus_assignments(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    return await service.get_student_bus_assignments()

@router.get("/assignments/parent-student", response_model=List[ParentStudentRelation])
async def list_parent_student_relations(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    return await service.get_parent_student_relations()

@router.delete("/assignments/student-bus/{assignment_id}", status_code=status.HTTP_200_OK)
async def delete_student_bus_assignment(
    assignment_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    await service.delete_student_bus_assignment(unquote(assignment_id))
    return {"detail": "Assignment deleted successfully"}

@router.delete("/assignments/parent-student/{relation_id}", status_code=status.HTTP_200_OK)
async def delete_parent_student_relation(
    relation_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    await service.delete_parent_student_relation(unquote(relation_id))
    return {"detail": "Relation deleted successfully"}

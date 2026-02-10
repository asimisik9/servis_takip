from fastapi import APIRouter, Depends, status, Query
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User
from ...database.schemas.student_bus_assignment import StudentBusAssignment
from ...database.schemas.parent_student_relation import ParentStudentRelation
from ...database.schemas.bus import Bus
from ...database.schemas.common import PaginatedResponse
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
    org_type = current_user.organization.type.value if current_user.organization else None
    return await service.assign_parent_to_student(
        unquote(student_id), 
        parent_id,
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )

@router.post("/students/{student_id}/assign-bus", response_model=StudentBusAssignment)
async def assign_bus_to_student(
    student_id: str,
    bus_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    return await service.assign_bus_to_student(
        unquote(student_id), 
        bus_id,
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )

@router.post("/buses/{bus_id}/assign-driver", response_model=Bus)
async def assign_driver_to_bus(
    bus_id: str,
    driver_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    return await service.assign_driver_to_bus(
        unquote(bus_id), 
        driver_id,
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )

@router.get("/assignments/student-bus", response_model=PaginatedResponse[StudentBusAssignment])
async def list_student_bus_assignments(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500)
):
    service = AssignmentService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    assignments, total = await service.get_student_bus_assignments(
        skip=skip, 
        limit=limit,
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )
    return PaginatedResponse(items=assignments, total=total, skip=skip, limit=limit)

@router.get("/assignments/parent-student", response_model=PaginatedResponse[ParentStudentRelation])
async def list_parent_student_relations(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500)
):
    service = AssignmentService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    relations, total = await service.get_parent_student_relations(
        skip=skip, 
        limit=limit,
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )
    return PaginatedResponse(items=relations, total=total, skip=skip, limit=limit)

@router.delete("/assignments/student-bus/{assignment_id}", status_code=status.HTTP_200_OK)
async def delete_student_bus_assignment(
    assignment_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    await service.delete_student_bus_assignment(
        unquote(assignment_id),
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )
    return {"detail": "Assignment deleted successfully"}

@router.delete("/assignments/parent-student/{relation_id}", status_code=status.HTTP_200_OK)
async def delete_parent_student_relation(
    relation_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = AssignmentService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    await service.delete_parent_student_relation(
        unquote(relation_id),
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )
    return {"detail": "Relation deleted successfully"}

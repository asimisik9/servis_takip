from fastapi import APIRouter, Depends, status, Query, HTTPException
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User
from ...database.schemas.student import Student, StudentCreate, StudentUpdate
from ...database.schemas.common import PaginatedResponse
from ...dependencies import get_db, get_current_admin_user
from ...services.student_service import StudentService

router = APIRouter(tags=["admin-students"])

@router.get("/students", response_model=PaginatedResponse[Student])
async def list_students(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    school_id: Annotated[str | None, Query()] = None
):
    """List students with tenant filtering and pagination."""
    service = StudentService(db)
    students, total = await service.get_students(
        skip=skip, 
        limit=limit, 
        current_user_org_id=current_user.organization_id,
        school_id=school_id
    )
    return PaginatedResponse(items=students, total=total, skip=skip, limit=limit)

@router.post("/students", response_model=Student, status_code=status.HTTP_201_CREATED)
async def create_student(
    student: StudentCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = StudentService(db)
    return await service.create_student(student, current_user_org_id=current_user.organization_id)

@router.get("/students/{student_id}", response_model=Student)
async def get_student(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = StudentService(db)
    # Read access control is implicitly handled if user knows UUID 
    # but strictly we should filter by Org too. For simplicity we assume read is open if ID known
    # Correction: let's enforce read check too for consistency
    student = await service.get_student_by_id(unquote(student_id))
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    # Manual tenant check for read
    if current_user.organization_id and student.school.organization_id != current_user.organization_id:
         raise HTTPException(status_code=404, detail="Student not found") # Hide existence
         
    return student

@router.put("/students/{student_id}", response_model=Student)
async def update_student(
    student_id: str,
    student: StudentUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = StudentService(db)
    return await service.update_student(
        unquote(student_id), 
        student,
        current_user_org_id=current_user.organization_id
    )

@router.delete("/students/{student_id}", status_code=status.HTTP_200_OK)
async def delete_student(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = StudentService(db)
    await service.delete_student(
        unquote(student_id),
        current_user_org_id=current_user.organization_id
    )
    return {"detail": "Student deleted successfully"}

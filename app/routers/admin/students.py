from fastapi import APIRouter, Depends, status
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User
from ...database.schemas.student import Student, StudentCreate, StudentUpdate
from ...dependencies import get_db, get_current_admin_user
from ...services.student_service import StudentService

router = APIRouter(tags=["admin-students"])

@router.get("/students", response_model=List[Student])
async def list_students(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    service = StudentService(db)
    return await service.get_students(skip, limit)

@router.post("/students", response_model=Student, status_code=status.HTTP_201_CREATED)
async def create_student(
    student: StudentCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = StudentService(db)
    return await service.create_student(student)

@router.put("/students/{student_id}", response_model=Student)
async def update_student(
    student_id: str,
    student: StudentUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = StudentService(db)
    return await service.update_student(unquote(student_id), student)

@router.delete("/students/{student_id}", status_code=status.HTTP_200_OK)
async def delete_student(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = StudentService(db)
    await service.delete_student(unquote(student_id))
    return {"detail": "Student deleted successfully"}

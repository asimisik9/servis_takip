from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Annotated
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from argon2 import PasswordHasher
from uuid import uuid4
from ..database import models

from ..database.database import AsyncSessionLocal
ph = PasswordHasher()
from ..database.schemas.user import User, UserCreate, UserUpdate
from ..database.schemas.student import Student, StudentCreate, StudentUpdate
from ..database.schemas.bus import Bus, BusCreate, BusUpdate
from ..database.schemas.bus_location import BusLocation
from ..database.schemas.attendance_log import AttendanceLog
from ..database.schemas.student_bus_assignment import StudentBusAssignment
from ..database.schemas.parent_student_relation import ParentStudentRelation
from .auth import get_current_admin_user
from ..database.schemas.school import School, SchoolCreate, SchoolUpdate

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)

# Database session dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def get_password_hash(password: str) -> str:
    return ph.hash(password)

# User Management
@router.get("/users", response_model=List[User])
async def list_users(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Tüm kullanıcıları listeler.
    
    Returns:
        List[User]: Sistemdeki tüm kullanıcıların listesi
        
    Raises:
        HTTPException: Veritabanı hatası durumunda 500 kodu ile hata döner
    """
    try:
        # Tüm kullanıcıları seç
        query = select(models.User)
        result = await db.execute(query)
        users = result.scalars().all()
        
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving users: {str(e)}"
        )

@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """Yeni kullanıcı oluşturur.
    
    Args:
        user: Oluşturulacak kullanıcı bilgileri
        current_user: İşlemi yapan admin kullanıcı
        db: Veritabanı oturumu
        
    Returns:
        User: Oluşturulan kullanıcının bilgileri
        
    Raises:
        HTTPException: Email adresi zaten kullanımda ise 400 kodu ile hata döner
    """
    # Check if email already exists
    query = select(models.User).where(models.User.email == user.email)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if phone number already exists
    query = select(models.User).where(models.User.phone_number == user.phone_number)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # Create new user instance
    new_user = models.User(
        id=str(uuid4()),
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        password_hash=get_password_hash(user.password),
        role=user.role
    )
    
    # Add to database and commit
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user

@router.get("/users/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Belirli bir kullanıcının detaylarını getirir.
    
    Args:
        user_id: Detayları istenen kullanıcının ID'si.
        current_user: İşlemi yapan admin kullanıcı.
        db: Veritabanı oturumu.
        
    Returns:
        User: İstenen kullanıcının bilgileri.
        
    Raises:
        HTTPException:
            - 404: Kullanıcı bulunamadığında.
            - 500: Veritabanı hatası durumunda.
    """
    try:
        # URL-encoded user_id'yi decode et
        from urllib.parse import unquote
        decoded_user_id = unquote(user_id)

        # Kullanıcıyı bul
        query = select(models.User).where(models.User.id == decoded_user_id)
        result = await db.execute(query)
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        return db_user
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user: {str(e)}"
        )


@router.put("/users/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user: UserUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Kullanıcı bilgilerini günceller.
    
    Not: user_id URL'den alındığı için URL-encoded formatında olabilir.
    Bu yüzden ilk olarak decode edilmesi gerekiyor.
    
    Args:
        user_id: Güncellenecek kullanıcının ID'si
        user: Güncellenecek kullanıcı bilgileri
        current_user: İşlemi yapan admin kullanıcı
        db: Veritabanı oturumu
        
    Returns:
        User: Güncellenmiş kullanıcı bilgileri
        
    Raises:
        HTTPException: 
            - 404: Kullanıcı bulunamadığında
            - 400: Email veya telefon numarası başka bir kullanıcıya aitse
            - 500: Veritabanı hatası durumunda
    """
    try:
        # URL-encoded user_id'yi decode et
        from urllib.parse import unquote
        decoded_user_id = unquote(user_id)
        
        # Kullanıcıyı bul
        query = select(models.User).where(models.User.id == decoded_user_id)
        result = await db.execute(query)
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Email güncellenmişse benzersizlik kontrolü
        if user.email and user.email != db_user.email:
            query = select(models.User).where(models.User.email == user.email)
            result = await db.execute(query)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Telefon güncellenmişse benzersizlik kontrolü
        if user.phone_number and user.phone_number != db_user.phone_number:
            query = select(models.User).where(models.User.phone_number == user.phone_number)
            result = await db.execute(query)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number already registered"
                )
        
        # Değişiklikleri uygula
        if user.full_name is not None:
            db_user.full_name = user.full_name
        if user.email is not None:
            db_user.email = user.email
        if user.phone_number is not None:
            db_user.phone_number = user.phone_number
        if user.role is not None:
            db_user.role = user.role
        if user.password is not None:
            db_user.password_hash = get_password_hash(user.password)
        
        # Değişiklikleri kaydet
        await db.commit()
        await db.refresh(db_user)
        
        return db_user
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )

@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Bir kullanıcıyı siler.
    
    Args:
        user_id: Silinecek kullanıcının ID'si.
        current_user: İşlemi yapan admin kullanıcı.
        db: Veritabanı oturumu.
        
    Returns:
        dict: Başarı mesajı.
        
    Raises:
        HTTPException:
            - 404: Kullanıcı bulunamadığında.
            - 400: Admin kendi kendini silemez.
            - 500: Veritabanı hatası durumunda.
    """
    try:
        # URL-encoded user_id'yi decode et
        from urllib.parse import unquote
        decoded_user_id = unquote(user_id)

        # Adminin kendi kendini silmesini engelle
        if decoded_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin cannot delete themselves"
            )

        # Kullanıcıyı bul
        query = select(models.User).where(models.User.id == decoded_user_id)
        result = await db.execute(query)
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Kullanıcıyı sil
        await db.delete(db_user)
        await db.commit()
        
        return {"detail": "User deleted successfully"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user: {str(e)}"
        )

# Student Management
@router.get("/students", response_model=List[Student])
async def list_students(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Tüm öğrencileri listeler.
    """
    try:
        query = select(models.Student)
        result = await db.execute(query)
        students = result.scalars().all()
        return students
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving students: {str(e)}"
        )

@router.post("/students", response_model=Student, status_code=status.HTTP_201_CREATED)
async def create_student(
    student: StudentCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Yeni öğrenci ekler.
    
    Args:
        student: Oluşturulacak öğrenci bilgileri
        current_user: İşlemi yapan admin kullanıcı
        db: Veritabanı oturumu
    Returns:
        Student: Oluşturulan öğrenci bilgileri
    Raises:
        HTTPException: Öğrenci numarası benzersiz değilse veya DB hatası olursa
    """
    from uuid import uuid4
    from sqlalchemy import select
    try:
        # Öğrenci numarası benzersiz mi?
        query = select(models.Student).where(models.Student.student_number == student.student_number)
        result = await db.execute(query)
        existing_student = result.scalar_one_or_none()
        if existing_student:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student number already exists"
            )
        # Yeni öğrenci oluştur
        new_student = models.Student(
            id=str(uuid4()),
            full_name=student.full_name,
            student_number=student.student_number,
            school_id=student.school_id
        )
        db.add(new_student)
        await db.commit()
        await db.refresh(new_student)
        return new_student
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating student: {str(e)}"
        )

@router.put("/students/{student_id}", response_model=Student)
async def update_student(
    student_id: str,
    student: StudentUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrenci bilgilerini günceller.
    """
    from urllib.parse import unquote
    try:
        decoded_student_id = unquote(student_id)
        # Öğrenciyi bul
        query = select(models.Student).where(models.Student.id == decoded_student_id)
        result = await db.execute(query)
        db_student = result.scalar_one_or_none()
        if not db_student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        # Öğrenci numarası güncelleniyorsa benzersiz mi?
        if student.student_number and student.student_number != db_student.student_number:
            query = select(models.Student).where(models.Student.student_number == student.student_number)
            result = await db.execute(query)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Student number already exists"
                )
        # Okul güncelleniyorsa var mı?
        if student.school_id:
            query = select(models.School).where(models.School.id == student.school_id)
            result = await db.execute(query)
            if not result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="School not found"
                )
        # Alanları güncelle
        if student.full_name is not None:
            db_student.full_name = student.full_name
        if student.student_number is not None:
            db_student.student_number = student.student_number
        if student.school_id is not None:
            db_student.school_id = student.school_id
        await db.commit()
        await db.refresh(db_student)
        return db_student
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating student: {str(e)}"
        )

@router.delete("/students/{student_id}", status_code=status.HTTP_200_OK)
async def delete_student(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Bir öğrenciyi siler.
    """
    from urllib.parse import unquote
    try:
        decoded_student_id = unquote(student_id)
        query = select(models.Student).where(models.Student.id == decoded_student_id)
        result = await db.execute(query)
        db_student = result.scalar_one_or_none()
        if not db_student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        await db.delete(db_student)
        await db.commit()
        return {"detail": "Student deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting student: {str(e)}"
        )

# Bus Management
@router.get("/buses", response_model=List[Bus])
async def list_buses(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Tüm otobüsleri listeler.
    """
    try:
        query = select(models.Bus)
        result = await db.execute(query)
        buses = result.scalars().all()
        return buses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving buses: {str(e)}"
        )

@router.post("/buses", response_model=Bus, status_code=status.HTTP_201_CREATED)
async def create_bus(
    bus: BusCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Yeni otobüs ekler.
    """
    try:
        # Plaka benzersiz mi?
        query = select(models.Bus).where(models.Bus.plate_number == bus.plate_number)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Plate number already exists"
            )
        # Okul var mı?
        query = select(models.School).where(models.School.id == bus.school_id)
        result = await db.execute(query)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="School not found"
            )
        # Sürücü var mı?
        query = select(models.User).where(models.User.id == bus.current_driver_id)
        result = await db.execute(query)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Driver not found"
            )
        # Otobüs oluştur
        from uuid import uuid4
        new_bus = models.Bus(
            id=str(uuid4()),
            plate_number=bus.plate_number,
            capacity=bus.capacity,
            school_id=bus.school_id,
            current_driver_id=bus.current_driver_id
        )
        db.add(new_bus)
        await db.commit()
        await db.refresh(new_bus)
        return new_bus
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating bus: {str(e)}"
        )

@router.put("/buses/{bus_id}", response_model=Bus)
async def update_bus(
    bus_id: str,
    bus: BusUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Otobüs bilgilerini günceller.
    """
    from urllib.parse import unquote
    try:
        decoded_bus_id = unquote(bus_id)
        # Otobüsü bul
        query = select(models.Bus).where(models.Bus.id == decoded_bus_id)
        result = await db.execute(query)
        db_bus = result.scalar_one_or_none()
        if not db_bus:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bus not found"
            )
        # Plaka güncelleniyorsa benzersiz mi?
        if bus.plate_number and bus.plate_number != db_bus.plate_number:
            query = select(models.Bus).where(models.Bus.plate_number == bus.plate_number)
            result = await db.execute(query)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Plate number already exists"
                )
        # Okul güncelleniyorsa var mı?
        if bus.school_id:
            query = select(models.School).where(models.School.id == bus.school_id)
            result = await db.execute(query)
            if not result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="School not found"
                )
        # Sürücü güncelleniyorsa var mı?
        if bus.current_driver_id:
            query = select(models.User).where(models.User.id == bus.current_driver_id)
            result = await db.execute(query)
            if not result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Driver not found"
                )
        # Alanları güncelle
        if bus.plate_number is not None:
            db_bus.plate_number = bus.plate_number
        if bus.capacity is not None:
            db_bus.capacity = bus.capacity
        if bus.school_id is not None:
            db_bus.school_id = bus.school_id
        if bus.current_driver_id is not None:
            db_bus.current_driver_id = bus.current_driver_id
        await db.commit()
        await db.refresh(db_bus)
        return db_bus
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating bus: {str(e)}"
        )

@router.delete("/buses/{bus_id}", status_code=status.HTTP_200_OK)
async def delete_bus(
    bus_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Bir otobüsü siler.
    """
    from urllib.parse import unquote
    try:
        decoded_bus_id = unquote(bus_id)
        query = select(models.Bus).where(models.Bus.id == decoded_bus_id)
        result = await db.execute(query)
        db_bus = result.scalar_one_or_none()
        if not db_bus:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bus not found"
            )
        await db.delete(db_bus)
        await db.commit()
        return {"detail": "Bus deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting bus: {str(e)}"
        )

# Assignment Operations
@router.post("/students/{student_id}/assign-parent", response_model=ParentStudentRelation)
async def assign_parent_to_student(
    student_id: str,
    parent_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrenciye veli atar.
    """
    from uuid import uuid4
    from urllib.parse import unquote
    try:
        decoded_student_id = unquote(student_id)
        # Öğrenci var mı?
        query = select(models.Student).where(models.Student.id == decoded_student_id)
        result = await db.execute(query)
        db_student = result.scalar_one_or_none()
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found")
        # Veli var mı ve rolü doğru mu?
        query = select(models.User).where(models.User.id == parent_id)
        result = await db.execute(query)
        db_parent = result.scalar_one_or_none()
        if not db_parent or db_parent.role.value != "veli":
            raise HTTPException(status_code=400, detail="Parent not found or role is not veli")
        # Aynı ilişki zaten var mı?
        query = select(models.ParentStudentRelation).where(
            models.ParentStudentRelation.student_id == decoded_student_id,
            models.ParentStudentRelation.parent_id == parent_id
        )
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Relation already exists")
        # İlişkiyi oluştur
        new_relation = models.ParentStudentRelation(
            id=str(uuid4()),
            student_id=decoded_student_id,
            parent_id=parent_id
        )
        db.add(new_relation)
        await db.commit()
        await db.refresh(new_relation)
        return new_relation
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error assigning parent: {str(e)}")

@router.post("/students/{student_id}/assign-bus", response_model=StudentBusAssignment)
async def assign_bus_to_student(
    student_id: str,
    bus_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrenciye otobüs atar.
    """
    from uuid import uuid4
    from urllib.parse import unquote
    try:
        decoded_student_id = unquote(student_id)
        # Öğrenci var mı?
        query = select(models.Student).where(models.Student.id == decoded_student_id)
        result = await db.execute(query)
        db_student = result.scalar_one_or_none()
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found")
        # Otobüs var mı?
        query = select(models.Bus).where(models.Bus.id == bus_id)
        result = await db.execute(query)
        db_bus = result.scalar_one_or_none()
        if not db_bus:
            raise HTTPException(status_code=400, detail="Bus not found")
        # Aynı atama zaten var mı?
        query = select(models.StudentBusAssignment).where(
            models.StudentBusAssignment.student_id == decoded_student_id,
            models.StudentBusAssignment.bus_id == bus_id
        )
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Assignment already exists")
        # Atamayı oluştur
        new_assignment = models.StudentBusAssignment(
            id=str(uuid4()),
            student_id=decoded_student_id,
            bus_id=bus_id
        )
        db.add(new_assignment)
        await db.commit()
        await db.refresh(new_assignment)
        return new_assignment
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error assigning bus: {str(e)}")

@router.post("/buses/{bus_id}/assign-driver", response_model=Bus)
async def assign_driver_to_bus(
    bus_id: str,
    driver_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Otobüse şoför atar.
    """
    from urllib.parse import unquote
    try:
        decoded_bus_id = unquote(bus_id)
        # Otobüs var mı?
        query = select(models.Bus).where(models.Bus.id == decoded_bus_id)
        result = await db.execute(query)
        db_bus = result.scalar_one_or_none()
        if not db_bus:
            raise HTTPException(status_code=404, detail="Bus not found")
        # Sürücü var mı ve rolü doğru mu?
        query = select(models.User).where(models.User.id == driver_id)
        result = await db.execute(query)
        db_driver = result.scalar_one_or_none()
        if not db_driver or db_driver.role.value != "sofor":
            raise HTTPException(status_code=400, detail="Driver not found or role is not sofor")
        # Atamayı yap
        db_bus.current_driver_id = driver_id
        await db.commit()
        await db.refresh(db_bus)
        return db_bus
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error assigning driver: {str(e)}")

# Get Assignments
@router.get("/assignments/student-bus", response_model=List[StudentBusAssignment])
async def list_student_bus_assignments(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Tüm öğrenci-otobüs atamalarını listeler.
    """
    try:
        query = select(models.StudentBusAssignment)
        result = await db.execute(query)
        assignments = result.scalars().all()
        return assignments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving student-bus assignments: {str(e)}"
        )

@router.get("/assignments/parent-student", response_model=List[ParentStudentRelation])
async def list_parent_student_relations(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Tüm öğrenci-veli ilişkilerini listeler.
    """
    try:
        query = select(models.ParentStudentRelation)
        result = await db.execute(query)
        relations = result.scalars().all()
        return relations
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving parent-student relations: {str(e)}"
        )

@router.delete("/assignments/student-bus/{assignment_id}", status_code=status.HTTP_200_OK)
async def delete_student_bus_assignment(
    assignment_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrenci-otobüs atamasını siler.
    """
    from urllib.parse import unquote
    try:
        decoded_id = unquote(assignment_id)
        query = select(models.StudentBusAssignment).where(models.StudentBusAssignment.id == decoded_id)
        result = await db.execute(query)
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        await db.delete(assignment)
        await db.commit()
        return {"detail": "Assignment deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting assignment: {str(e)}")

@router.delete("/assignments/parent-student/{relation_id}", status_code=status.HTTP_200_OK)
async def delete_parent_student_relation(
    relation_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrenci-veli ilişkisini siler.
    """
    from urllib.parse import unquote
    try:
        decoded_id = unquote(relation_id)
        query = select(models.ParentStudentRelation).where(models.ParentStudentRelation.id == decoded_id)
        result = await db.execute(query)
        relation = result.scalar_one_or_none()
        if not relation:
            raise HTTPException(status_code=404, detail="Relation not found")
        await db.delete(relation)
        await db.commit()
        return {"detail": "Relation deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting relation: {str(e)}")

# Monitoring
@router.get("/buses/locations", response_model=List[BusLocation])
async def get_all_bus_locations(
    current_user: Annotated[User, Depends(get_current_admin_user)]
):
    """Tüm servislerin anlık konumlarını getirir."""
    # TODO: Implement bus locations retrieval logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented"
    )

@router.get("/logs/attendance", response_model=List[AttendanceLog])
async def get_attendance_logs(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    start_date: date = None,
    end_date: date = None,
    bus_id: str = None,
    student_id: str = None
):
    """
    Yoklama kayıtlarını filtreli şekilde getirir.
    Tarih aralığı, servis veya öğrenci bazında filtreleme yapılabilir.
    """
    # TODO: Implement attendance logs retrieval logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented"
    )

# School Management

@router.post("/schools", response_model=School, status_code=status.HTTP_201_CREATED)
async def create_school(
    school: SchoolCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Yeni okul ekler.
    Args:
        school: Oluşturulacak okul bilgileri
        current_user: İşlemi yapan admin kullanıcı
        db: Veritabanı oturumu
    Returns:
        School: Oluşturulan okul bilgileri
    Raises:
        HTTPException: Okul adı benzersiz değilse veya DB hatası olursa
    """
    from uuid import uuid4
    from sqlalchemy import select
    try:
        # Okul adı benzersiz mi?
        query = select(models.School).where(models.School.school_name == school.school_name)
        result = await db.execute(query)
        existing_school = result.scalar_one_or_none()
        if existing_school:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="School name already exists"
            )
        # Yeni okul oluştur
        new_school = models.School(
            id=str(uuid4()),
            school_name=school.school_name,
            school_address=school.school_address,
            contact_person_id=school.contact_person_id
        )
        db.add(new_school)
        await db.commit()
        await db.refresh(new_school)
        return new_school
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating school: {str(e)}"
        )

@router.get("/schools", response_model=List[School])
async def list_schools(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Tüm okulları listeler.
    """
    try:
        query = select(models.School)
        result = await db.execute(query)
        schools = result.scalars().all()
        return schools
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving schools: {str(e)}"
        )

@router.put("/schools/{school_id}", response_model=School)
async def update_school(
    school_id: str,
    school: SchoolUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Okul bilgilerini günceller.
    """
    from urllib.parse import unquote
    try:
        decoded_school_id = unquote(school_id)
        # Okulu bul
        query = select(models.School).where(models.School.id == decoded_school_id)
        result = await db.execute(query)
        db_school = result.scalar_one_or_none()
        if not db_school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        # Okul adı güncelleniyorsa benzersiz mi?
        if school.school_name and school.school_name != db_school.school_name:
            query = select(models.School).where(models.School.school_name == school.school_name)
            result = await db.execute(query)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="School name already exists"
                )
        # İletişim kişisi güncelleniyorsa var mı?
        if school.contact_person_id:
            query = select(models.User).where(models.User.id == school.contact_person_id)
            result = await db.execute(query)
            if not result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Contact person not found"
                )
        # Alanları güncelle
        if school.school_name is not None:
            db_school.school_name = school.school_name
        if school.school_address is not None:
            db_school.school_address = school.school_address
        if school.contact_person_id is not None:
            db_school.contact_person_id = school.contact_person_id
        await db.commit()
        await db.refresh(db_school)
        return db_school
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating school: {str(e)}"
        )

@router.delete("/schools/{school_id}", status_code=status.HTTP_200_OK)
async def delete_school(
    school_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Bir okulu siler.
    """
    from urllib.parse import unquote
    try:
        decoded_school_id = unquote(school_id)
        query = select(models.School).where(models.School.id == decoded_school_id)
        result = await db.execute(query)
        db_school = result.scalar_one_or_none()
        if not db_school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        await db.delete(db_school)
        await db.commit()
        return {"detail": "School deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting school: {str(e)}"
        )

@router.get("/schools/{school_id}", response_model=School)
async def get_school(
    school_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Belirli bir okulun detaylarını getirir.
    """
    from urllib.parse import unquote
    try:
        decoded_school_id = unquote(school_id)
        query = select(models.School).where(models.School.id == decoded_school_id)
        result = await db.execute(query)
        db_school = result.scalar_one_or_none()
        if not db_school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        return db_school
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving school: {str(e)}"
        )
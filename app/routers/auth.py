from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from ..database.schemas.user import User, UserCreate
from ..database.models.user import User as UserModel
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime
from fastapi import Body

from ..dependencies import (
    get_db, 
    get_current_user, 
    get_current_admin_user, 
    get_current_driver_user, 
    get_current_parent_user
)
from ..core.security import (
    hash_password, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    SECRET_KEY,
    ALGORITHM
)

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

# Schema for login request
class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: User

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Yeni kullanıcı kaydı oluşturur.
    """
    # Check if email already exists
    query = select(UserModel).where(UserModel.email == user_data.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if phone number already exists
    query = select(UserModel).where(UserModel.phone_number == user_data.phone_number)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = UserModel(
        id=str(uuid4()),
        full_name=user_data.full_name,
        email=user_data.email,
        phone_number=user_data.phone_number,
        password_hash=hashed_password,
        role=user_data.role,
        created_at=datetime.utcnow()
    )
    
    # Add to database
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Return the created user
    return User.from_orm(new_user)

@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
):
    """
    Kullanıcı girişi yapar ve JWT token döndürür.
    """
    print(f"Login attempt - Username: {form_data.username}, Password length: {len(form_data.password)}")
    
    # Get user from database
    query = select(UserModel).where(UserModel.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        print(f"User not found: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    print(f"User found: {user.email}, checking password...")
    if not verify_password(form_data.password, user.password_hash):
        print(f"Password verification failed for {user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token_data = {
        "sub": user.email,
        "id": user.id,
        "role": user.role.value
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=User.from_orm(user)
    )

@router.get("/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Giriş yapmış kullanıcının bilgilerini döndürür.
    """
    return current_user

@router.post("/logout")
async def logout(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Kullanıcı çıkışı yapar.
    NOT: JWT stateless olduğu için backend'de token invalidation yapılmıyor.
    Client-side'da token silinmelidir.
    """
    return {"message": "Successfully logged out"}

@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh token kullanarak yeni access token alır.
    """
    from jose import jwt, JWTError
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Get user from database
    query = select(UserModel).where(UserModel.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise credentials_exception
        
    token_data = {
        "sub": user.email,
        "id": user.id,
        "role": user.role.value
    }
    
    # Create new tokens
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=User.from_orm(user)
    )
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
from ..database.schemas.user import User, UserCreate
from ..database.models.user import UserRole, User as UserModel
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from ..database.database import AsyncSessionLocal

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

# Password hashing using argon2
ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash a password using argon2"""
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except (VerifyMismatchError, Exception) as e:
        # Hata durumunda logla ve False döndür
        print(f"Password verification error: {type(e).__name__}: {e}")
        return False

# Database dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# JWT Configuration
SECRET_KEY = "dev-key-not-secure"  # Change this in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Schema for login request
class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

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

def create_access_token(data: dict) -> str:
    from jose import jwt
    to_encode = data.copy()
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

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
        "role": user.role.value
    }
    access_token = create_access_token(token_data)
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=User.from_orm(user)
    )

# Dependency for getting the current user
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
):
    """
    JWT token'dan kullanıcı bilgilerini çıkarır.
    """
    from jose import jwt, JWTError
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    
    return User.from_orm(user)

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

# Permission dependencies
def get_current_admin_user(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Kullanıcının admin olup olmadığını kontrol eder.
    """
    if current_user.role != "admin":  # Token'da sadece string değer olduğu için enum yerine string karşılaştırması yapıyoruz
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint"
        )
    return current_user

def get_current_driver_user(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Kullanıcının şoför olup olmadığını kontrol eder.
    """
    if current_user.role != "sofor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint"
        )
    return current_user

def get_current_parent_user(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Kullanıcının veli olup olmadığını kontrol eder.
    """
    if current_user.role != "veli":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint"
        )
    return current_user
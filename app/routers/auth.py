from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
from ..database.schemas.user import User, UserCreate
from ..database.models.user import UserRole
from pydantic import BaseModel

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

# Test data (replace this with database calls in production)
from datetime import datetime
test_users = {
    "parent@test.com": {
        "email": "parent@test.com",
        "full_name": "Test Parent",
        "password": "parent123",
        "phone_number": "+905551112235",
        "role": UserRole.veli,
        "id": "1",
        "created_at": datetime.now()
    }
}

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
async def register(user_data: UserCreate):
    """
    Yeni kullanıcı kaydı oluşturur.
    """
    # Check if user already exists
    if user_data.email in test_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user entry
    new_user = {
        "email": user_data.email,
        "full_name": user_data.full_name,
        "password": user_data.password,  # In production, hash the password!
        "phone_number": user_data.phone_number,
        "role": user_data.role,
        "id": str(len(test_users) + 1),  # Simple ID generation for testing
        "created_at": datetime.now()
    }
    
    # Add to test data
    test_users[user_data.email] = new_user
    
    # Return the created user (without password)
    return User(**new_user)

def create_access_token(data: dict) -> str:
    from jose import jwt
    to_encode = data.copy()
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/login", response_model=LoginResponse)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Kullanıcı girişi yapar ve JWT token döndürür.
    """
    # For testing purposes, check against our test data
    if form_data.username not in test_users or test_users[form_data.username]["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = test_users[form_data.username]
    token_data = {
        "sub": user["email"],
        "role": user["role"]
    }
    access_token = create_access_token(token_data)
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=User(**user)
    )

# Dependency for getting the current user
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
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
    
    # For testing purposes, get user from test data
    if email not in test_users:
        raise credentials_exception
    
    return User(**test_users[email])

@router.get("/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Giriş yapmış kullanıcının bilgilerini döndürür.
    """
    return current_user

# Permission dependencies
def get_current_admin_user(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Kullanıcının admin olup olmadığını kontrol eder.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint"
        )
    return current_user

def get_current_driver_user(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Kullanıcının şoför olup olmadığını kontrol eder.
    """
    if current_user.role != UserRole.sofor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint"
        )
    return current_user

def get_current_parent_user(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Kullanıcının veli olup olmadığını kontrol eder.
    """
    if current_user.role != UserRole.veli:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint"
        )
    return current_user
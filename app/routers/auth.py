from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from ..database.schemas.user import User, UserCreate
from pydantic import BaseModel

from ..dependencies import (
    get_db, 
    get_current_user, 
    oauth2_scheme,
    get_auth_service
)
from ..services.auth_service import AuthService
from ..core.limiter import limiter
import logging

logger = logging.getLogger(__name__)

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

@router.post("/register", status_code=status.HTTP_403_FORBIDDEN)
@limiter.limit("3/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Public kayıt kapalıdır.
    """
    await auth_service.register_user(user_data)

@router.post("/login", response_model=LoginResponse)
@limiter.limit("20/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Kullanıcı girişi yapar ve JWT token döndürür.
    """
    logger.info("Login attempt received")
    
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        logger.warning("Authentication failed for a login attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token, refresh_token = await auth_service.create_tokens(user)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=User.model_validate(user)
    )

@router.get("/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Giriş yapmış kullanıcının bilgilerini döndürür.
    """
    return current_user

@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Kullanıcı çıkışı yapar ve token'ı kara listeye alır.
    """
    await auth_service.logout(token)
    return {"message": "Successfully logged out"}

@router.post("/refresh", response_model=LoginResponse)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    refresh_token: str = Body(..., embed=True),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Refresh token kullanarak yeni access token alır.
    """
    (access_token, new_refresh_token), user = await auth_service.refresh_token(refresh_token)
    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=User.model_validate(user)
    )

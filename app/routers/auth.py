from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from typing import Annotated
from ..database.schemas.user import User, UserCreate
from ..database.schemas.auth import (
    AuthActionResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from pydantic import BaseModel

from ..dependencies import (
    get_current_user, 
    oauth2_scheme,
    get_auth_service
)
from ..services.auth_service import AuthService
from ..core.limiter import limiter
from ..core.config import settings
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

    if not user.is_email_verified:
        requested_ip = request.client.host if request.client else None
        requested_user_agent = request.headers.get("user-agent")
        await auth_service.send_login_email_verification_if_needed(
            user=user,
            request_base_url=str(request.base_url),
            requested_ip=requested_ip,
            requested_user_agent=requested_user_agent,
        )
    
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


@router.post("/forgot-password", response_model=AuthActionResponse)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    requested_ip = request.client.host if request.client else None
    requested_user_agent = request.headers.get("user-agent")
    result = await auth_service.forgot_password(
        email=payload.email,
        requested_ip=requested_ip,
        requested_user_agent=requested_user_agent,
    )
    return AuthActionResponse(**result)


@router.post("/reset-password", response_model=AuthActionResponse)
@limiter.limit("10/minute")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    result = await auth_service.reset_password(
        token=payload.token,
        new_password=payload.new_password,
    )
    return AuthActionResponse(**result)


@router.post("/change-password", response_model=AuthActionResponse)
@limiter.limit("10/minute")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    auth_service: AuthService = Depends(get_auth_service),
):
    result = await auth_service.change_password(
        user_id=current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return AuthActionResponse(**result)


@router.get("/verify-email")
@limiter.limit("20/minute")
async def verify_email(
    request: Request,
    token: str = Query(..., min_length=1),
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        redirect_url = await auth_service.verify_email_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Email verification failed unexpectedly: %s", exc)
        if settings.EMAIL_VERIFY_REDIRECT_URL:
            redirect_url = auth_service._build_redirect_url_with_status(
                str(settings.EMAIL_VERIFY_REDIRECT_URL),
                "error",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Email verification failed.",
            )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post("/resend-email-verification", response_model=AuthActionResponse)
@limiter.limit("5/minute")
async def resend_email_verification(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    auth_service: AuthService = Depends(get_auth_service),
):
    requested_ip = request.client.host if request.client else None
    requested_user_agent = request.headers.get("user-agent")
    result = await auth_service.resend_email_verification(
        user_id=current_user.id,
        request_base_url=str(request.base_url),
        requested_ip=requested_ip,
        requested_user_agent=requested_user_agent,
    )
    return AuthActionResponse(**result)

from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
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


@router.get("/verify-email", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def verify_email(
    request: Request,
    token: str = Query(..., min_length=1),
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        result_status = await auth_service.verify_email_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Email verification failed unexpectedly: %s", exc)
        result_status = "error"
    return HTMLResponse(content=_build_verification_html(result_status))


def _build_verification_html(result_status: str) -> str:
    messages = {
        "success": ("Email Doğrulandı", "Email adresiniz başarıyla doğrulandı. Uygulamaya dönüp devam edebilirsiniz.", "✅", "#4CAF50"),
        "already_verified": ("Zaten Doğrulanmış", "Email adresiniz zaten doğrulanmış. Uygulamaya dönüp devam edebilirsiniz.", "✅", "#2196F3"),
        "invalid_or_expired": ("Geçersiz veya Süresi Dolmuş", "Doğrulama linki geçersiz veya süresi dolmuş. Lütfen uygulamadan yeni bir doğrulama emaili isteyin.", "❌", "#F44336"),
        "error": ("Bir Hata Oluştu", "Email doğrulama sırasında bir hata oluştu. Lütfen tekrar deneyin.", "⚠️", "#FF9800"),
    }
    title, message, icon, color = messages.get(result_status, messages["error"])

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Servis Now</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }}
        .card {{ background: white; border-radius: 16px; padding: 48px 32px; max-width: 420px; width: 100%; text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,0.1); }}
        .icon {{ font-size: 64px; margin-bottom: 24px; }}
        h1 {{ color: {color}; font-size: 22px; margin-bottom: 16px; }}
        p {{ color: #666; font-size: 16px; line-height: 1.5; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">{icon}</div>
        <h1>{title}</h1>
        <p>{message}</p>
    </div>
</body>
</html>"""


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

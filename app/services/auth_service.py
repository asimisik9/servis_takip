import asyncio
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
from jose import JWTError, jwt
import logging
import secrets
import smtplib
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import uuid4
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import HTTPException, status

from ..core.config import settings
from ..core.redis import redis_manager
from ..core.security import (
    ALGORITHM,
    REFRESH_SECRET_KEY,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    hash_password,
    is_token_stale_for_password_change,
    verify_password,
)
from ..database.models.email_verification_token import EmailVerificationToken
from ..database.models.password_reset_token import PasswordResetToken
from ..database.models.user import User as UserModel
from ..database.schemas.user import UserCreate

logger = logging.getLogger(__name__)

FORGOT_PASSWORD_GENERIC_MESSAGE = "If an account exists, a reset email has been sent."
FORGOT_PASSWORD_COOLDOWN_SECONDS = 60
EMAIL_VERIFICATION_SENT_MESSAGE = "Verification email sent."
EMAIL_VERIFICATION_COOLDOWN_SECONDS = 60


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user_data: UserCreate) -> UserModel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled. Contact your administrator.",
        )

    async def authenticate_user(self, email: str, password: str):
        query = (
            select(UserModel)
            .options(selectinload(UserModel.organization))
            .where(UserModel.email == email)
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        if hasattr(user, "is_active") and not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact an administrator.",
            )

        return user

    async def create_tokens(self, user: UserModel):
        token_data = {
            "sub": user.email,
            "id": user.id,
            "role": user.role.value,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        return access_token, refresh_token

    @staticmethod
    def _smtp_missing_fields() -> list[str]:
        missing_fields: list[str] = []
        if not settings.SMTP_HOST:
            missing_fields.append("SMTP_HOST")
        if not settings.SMTP_USERNAME:
            missing_fields.append("SMTP_USERNAME")
        if not settings.SMTP_PASSWORD:
            missing_fields.append("SMTP_PASSWORD")
        if not settings.SMTP_FROM_EMAIL:
            missing_fields.append("SMTP_FROM_EMAIL")
        return missing_fields

    def _validate_password_reset_configuration(self) -> None:
        missing_fields = self._smtp_missing_fields()
        if not settings.PASSWORD_RESET_URL_BASE:
            missing_fields.append("PASSWORD_RESET_URL_BASE")
        if not missing_fields:
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SMTP/password reset configuration is incomplete: {', '.join(missing_fields)}",
        )

    def _validate_email_verification_configuration(self) -> None:
        missing_fields = self._smtp_missing_fields()
        if not settings.EMAIL_VERIFY_REDIRECT_URL:
            missing_fields.append("EMAIL_VERIFY_REDIRECT_URL")
        if not missing_fields:
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SMTP/email verification configuration is incomplete: {', '.join(missing_fields)}",
        )

    @staticmethod
    def _hash_reset_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def _build_password_reset_link(self, raw_token: str) -> str:
        base_url = str(settings.PASSWORD_RESET_URL_BASE)
        parsed = urlparse(base_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["token"] = raw_token
        updated_query = urlencode(query)
        return urlunparse(parsed._replace(query=updated_query))

    @staticmethod
    def _build_redirect_url_with_status(base_url: str, status_value: str) -> str:
        parsed = urlparse(base_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["status"] = status_value
        updated_query = urlencode(query)
        return urlunparse(parsed._replace(query=updated_query))

    def _build_email_verification_link(self, raw_token: str, request_base_url: str) -> str:
        endpoint_url = f"{request_base_url.rstrip('/')}{settings.API_V1_STR}/auth/verify-email"
        parsed = urlparse(endpoint_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["token"] = raw_token
        updated_query = urlencode(query)
        return urlunparse(parsed._replace(query=updated_query))

    def _send_email_sync(
        self,
        recipient_email: str,
        subject: str,
        plain_body: str,
        html_body: str,
    ) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = str(settings.SMTP_FROM_EMAIL)
        message["To"] = recipient_email
        message.set_content(plain_body)
        message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)

    async def _send_password_reset_email(
        self, recipient_email: str, recipient_name: str, reset_link: str
    ) -> None:
        subject = "Servis Now - Password Reset"
        expires_minutes = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES

        plain_body = (
            f"Hello {recipient_name},\n\n"
            "We received a request to reset your password.\n"
            f"Use the following link within {expires_minutes} minutes:\n\n"
            f"{reset_link}\n\n"
            "If you did not request this, you can safely ignore this email."
        )
        html_body = (
            "<html><body>"
            f"<p>Hello {recipient_name},</p>"
            "<p>We received a request to reset your password.</p>"
            f"<p>Please use this link within <b>{expires_minutes} minutes</b>:</p>"
            f'<p><a href="{reset_link}">{reset_link}</a></p>'
            "<p>If you did not request this, you can safely ignore this email.</p>"
            "</body></html>"
        )

        try:
            await asyncio.to_thread(
                self._send_email_sync,
                recipient_email,
                subject,
                plain_body,
                html_body,
            )
        except Exception as exc:
            logger.exception("Failed to send password reset email: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password reset email could not be sent. Please try again.",
            ) from exc

    async def _send_email_verification_email(
        self, recipient_email: str, recipient_name: str, verification_link: str
    ) -> None:
        subject = "Servis Now - Verify Your Email"
        expires_hours = settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS

        plain_body = (
            f"Hello {recipient_name},\n\n"
            "Please verify your email to continue using your account.\n"
            f"Use the following link within {expires_hours} hours:\n\n"
            f"{verification_link}\n\n"
            "If you did not request this, you can safely ignore this email."
        )
        html_body = (
            "<html><body>"
            f"<p>Hello {recipient_name},</p>"
            "<p>Please verify your email to continue using your account.</p>"
            f"<p>Use this link within <b>{expires_hours} hours</b>:</p>"
            f'<p><a href="{verification_link}">{verification_link}</a></p>'
            "<p>If you did not request this, you can safely ignore this email.</p>"
            "</body></html>"
        )

        try:
            await asyncio.to_thread(
                self._send_email_sync,
                recipient_email,
                subject,
                plain_body,
                html_body,
            )
        except Exception as exc:
            logger.exception("Failed to send email verification email: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Verification email could not be sent. Please try again.",
            ) from exc

    async def forgot_password(
        self, email: str, requested_ip: str | None, requested_user_agent: str | None
    ) -> dict[str, object]:
        self._validate_password_reset_configuration()

        normalized_email = email.strip().lower()
        email_hash = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
        cooldown_key = f"auth:forgot_password:cooldown:{email_hash}"

        try:
            is_in_cooldown = await redis_manager.get(cooldown_key)
        except Exception as exc:
            logger.warning("Forgot-password cooldown check failed: %s", exc)
            is_in_cooldown = None

        if is_in_cooldown:
            return {"message": FORGOT_PASSWORD_GENERIC_MESSAGE, "success": True}

        try:
            query = (
                select(UserModel)
                .options(selectinload(UserModel.organization))
                .where(func.lower(UserModel.email) == normalized_email)
            )
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()

            if user and user.is_active:
                raw_token = secrets.token_urlsafe(48)
                token_record = PasswordResetToken(
                    id=str(uuid4()),
                    user_id=user.id,
                    token_hash=self._hash_reset_token(raw_token),
                    expires_at=datetime.now(timezone.utc)
                    + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
                    requested_ip=(requested_ip or None),
                    requested_user_agent=(requested_user_agent[:1024] if requested_user_agent else None),
                )
                self.db.add(token_record)
                await self.db.commit()

                reset_link = self._build_password_reset_link(raw_token)
                await self._send_password_reset_email(user.email, user.full_name, reset_link)
        finally:
            try:
                await redis_manager.set(cooldown_key, "1", ex=FORGOT_PASSWORD_COOLDOWN_SECONDS)
            except Exception as exc:
                logger.warning("Failed to set forgot-password cooldown key: %s", exc)

        return {"message": FORGOT_PASSWORD_GENERIC_MESSAGE, "success": True}

    async def reset_password(self, token: str, new_password: str) -> dict[str, object]:
        token_hash = self._hash_reset_token(token.strip())
        now = datetime.now(timezone.utc)

        query = (
            select(PasswordResetToken)
            .options(selectinload(PasswordResetToken.user))
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
        result = await self.db.execute(query)
        reset_token = result.scalar_one_or_none()

        if not reset_token or not reset_token.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token is invalid or expired.",
            )

        user = reset_token.user
        password_changed_at = datetime.now(timezone.utc)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = password_changed_at
        reset_token.used_at = password_changed_at

        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.id != reset_token.id,
            )
            .values(used_at=password_changed_at)
        )

        await self.db.commit()

        return {"message": "Password has been reset successfully.", "success": True}

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> dict[str, object]:
        user = await self.db.get(UserModel, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if not verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

        if verify_password(new_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password cannot be the same as current password.",
            )

        password_changed_at = datetime.now(timezone.utc)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = password_changed_at

        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=password_changed_at)
        )

        await self.db.commit()

        return {
            "message": "Password changed successfully. Please login again.",
            "success": True,
        }

    @staticmethod
    def _email_verification_cooldown_key(user_id: str) -> str:
        return f"auth:email_verification:cooldown:{user_id}"

    async def _send_email_verification_with_cooldown(
        self,
        user: UserModel,
        request_base_url: str,
        requested_ip: str | None,
        requested_user_agent: str | None,
        raise_on_error: bool,
    ) -> bool:
        if user.is_email_verified:
            return False

        try:
            self._validate_email_verification_configuration()
        except HTTPException:
            if raise_on_error:
                raise
            logger.warning(
                "Email verification configuration is missing; skipping verification mail for user=%s",
                user.id,
            )
            return False

        cooldown_key = self._email_verification_cooldown_key(user.id)
        try:
            is_in_cooldown = await redis_manager.get(cooldown_key)
        except Exception as exc:
            logger.warning("Email verification cooldown check failed: %s", exc)
            is_in_cooldown = None

        if is_in_cooldown:
            return False

        raw_token = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)

        # Invalidate previously issued, still-live verification tokens for the same user.
        await self.db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=now)
        )

        token_record = EmailVerificationToken(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=self._hash_reset_token(raw_token),
            expires_at=expires_at,
            requested_ip=(requested_ip or None),
            requested_user_agent=(requested_user_agent[:1024] if requested_user_agent else None),
        )
        self.db.add(token_record)

        verification_link = self._build_email_verification_link(raw_token, request_base_url)
        try:
            await self._send_email_verification_email(user.email, user.full_name, verification_link)
        except HTTPException:
            await self.db.rollback()
            if raise_on_error:
                raise
            logger.warning("Email verification mail send failed for user=%s", user.id)
            return False

        await self.db.commit()

        try:
            await redis_manager.set(cooldown_key, "1", ex=EMAIL_VERIFICATION_COOLDOWN_SECONDS)
        except Exception as exc:
            logger.warning("Failed to set email verification cooldown key: %s", exc)

        return True

    async def send_login_email_verification_if_needed(
        self,
        user: UserModel,
        request_base_url: str,
        requested_ip: str | None,
        requested_user_agent: str | None,
    ) -> None:
        await self._send_email_verification_with_cooldown(
            user=user,
            request_base_url=request_base_url,
            requested_ip=requested_ip,
            requested_user_agent=requested_user_agent,
            raise_on_error=False,
        )

    async def resend_email_verification(
        self,
        user_id: str,
        request_base_url: str,
        requested_ip: str | None,
        requested_user_agent: str | None,
    ) -> dict[str, object]:
        user = await self.db.get(UserModel, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        if user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already verified.",
            )

        await self._send_email_verification_with_cooldown(
            user=user,
            request_base_url=request_base_url,
            requested_ip=requested_ip,
            requested_user_agent=requested_user_agent,
            raise_on_error=True,
        )

        return {"message": EMAIL_VERIFICATION_SENT_MESSAGE, "success": True}

    async def verify_email_token(self, token: str) -> str:
        self._validate_email_verification_configuration()

        token_hash = self._hash_reset_token(token.strip())
        now = datetime.now(timezone.utc)
        redirect_base = str(settings.EMAIL_VERIFY_REDIRECT_URL)

        query = (
            select(EmailVerificationToken)
            .options(selectinload(EmailVerificationToken.user))
            .where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.expires_at > now,
            )
        )
        result = await self.db.execute(query)
        verification_token = result.scalar_one_or_none()

        if not verification_token or not verification_token.user:
            return self._build_redirect_url_with_status(redirect_base, "invalid_or_expired")

        user = verification_token.user
        if user.is_email_verified:
            verification_token.used_at = now
            await self.db.commit()
            return self._build_redirect_url_with_status(redirect_base, "already_verified")

        user.is_email_verified = True
        user.email_verified_at = now
        verification_token.used_at = now

        await self.db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.id != verification_token.id,
            )
            .values(used_at=now)
        )

        await self.db.commit()
        return self._build_redirect_url_with_status(redirect_base, "success")

    async def _blacklist_token(self, token: str, exp_timestamp: int):
        """Add token to Redis blacklist with TTL matching token expiry.
        Also persists to DB as fallback if Redis restarts."""
        now = int(datetime.now(timezone.utc).timestamp())
        ttl = max(exp_timestamp - now, 0)

        # Primary: Redis (fast, auto-expires)
        redis_ok = False
        if ttl > 0:
            try:
                await redis_manager.set(f"blacklist:{token}", "1", ex=ttl)
                redis_ok = True
            except Exception as e:
                logger.error("Failed to blacklist token in Redis: %s", e)

        # Secondary: DB persistence (survives Redis restart)
        db_ok = False
        try:
            from ..database.database import AsyncSessionLocal
            from ..database.models.token_blacklist import TokenBlacklist

            async with AsyncSessionLocal() as db:
                blacklisted = TokenBlacklist(
                    token=token,
                    expires_at=datetime.fromtimestamp(exp_timestamp, tz=timezone.utc),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(blacklisted)
                await db.commit()
                db_ok = True
        except Exception as e:
            logger.error("Failed to persist blacklisted token to DB: %s", e)
            if not redis_ok:
                logger.critical("Token blacklist failed in BOTH Redis and DB! Token remains valid.")

        if not redis_ok and not db_ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token revocation failed",
            )

    async def logout(self, token: str):
        try:
            # Try decoding as access token first, then refresh
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            except JWTError:
                payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])

            exp = payload.get("exp", 0)
            await self._blacklist_token(token, exp)
        except HTTPException:
            raise
        except JWTError:
            pass  # Token already expired or invalid — no need to blacklist
        except Exception as e:
            logger.error("Unexpected error during logout: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed. Please try again.",
            )

    async def refresh_token(self, refresh_token: str):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        # Check blacklist in Redis
        try:
            is_blacklisted = await redis_manager.get(f"blacklist:{refresh_token}")
        except Exception as e:
            logger.warning("Refresh Redis blacklist check failed: %s", e)
            is_blacklisted = None
        if is_blacklisted:
            raise credentials_exception

        # Fallback: Check DB blacklist if Redis missed (e.g. after Redis restart)
        try:
            from ..database.models.token_blacklist import TokenBlacklist

            stmt = select(TokenBlacklist).where(
                TokenBlacklist.token == refresh_token,
                TokenBlacklist.expires_at > datetime.now(timezone.utc),
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                try:
                    await redis_manager.set(f"blacklist:{refresh_token}", "1", ex=3600)
                except Exception:
                    pass
                raise credentials_exception
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Refresh DB blacklist check failed: %s", e)
            # Fail-closed: we cannot safely validate revocation state.
            raise credentials_exception

        try:
            payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            token_type: str = payload.get("type")
            if email is None:
                raise credentials_exception
            # Ensure this is actually a refresh token
            if token_type != "refresh":
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        query = (
            select(UserModel)
            .options(selectinload(UserModel.organization))
            .where(UserModel.email == email)
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise credentials_exception

        if is_token_stale_for_password_change(payload, user.password_changed_at):
            raise credentials_exception

        # Blacklist old refresh token
        await self.logout(refresh_token)

        return await self.create_tokens(user), user

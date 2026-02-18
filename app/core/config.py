from pydantic_settings import BaseSettings
from typing import List, Optional, Any
from pydantic import AnyHttpUrl, field_validator, EmailStr

class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Servis Takip API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"  # local, development, production
    
    # Security
    SECRET_KEY: str
    REFRESH_SECRET_KEY: Optional[str] = None  # Falls back to SECRET_KEY + "_refresh" if not set
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str
    POSTGRES_POOL_SIZE: int = 20
    POSTGRES_MAX_OVERFLOW: int = 10
    POSTGRES_POOL_RECYCLE: int = 1800  # Recycle connections after 30 minutes
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    
    # Google Maps
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    
    # Firebase Cloud Messaging
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None  # Path to Firebase service account JSON

    # SMTP / Password Reset
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[EmailStr] = None
    SMTP_USE_TLS: bool = True
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_RESET_URL_BASE: Optional[AnyHttpUrl] = None
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    EMAIL_VERIFY_REDIRECT_URL: Optional[AnyHttpUrl] = None

    # Initial Superuser
    FIRST_SUPERUSER: EmailStr = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str  # No default — MUST be set via env var
    
    @field_validator("FIREBASE_CREDENTIALS_PATH", mode="after")
    @classmethod
    def validate_firebase_path(cls, v: Optional[str], info) -> Optional[str]:
        """Warn if Firebase credentials not set in production"""
        import os
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production" and not v:
            import logging
            logging.getLogger(__name__).warning(
                "FIREBASE_CREDENTIALS_PATH not set in production! "
                "Push notifications will not work."
            )
        return v

    @field_validator("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def validate_password_reset_token_expire_minutes(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES must be greater than 0")
        return v

    @field_validator("EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS")
    @classmethod
    def validate_email_verification_token_expire_hours(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS must be greater than 0")
        return v
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        elif isinstance(v, list):
            return v
        return []

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def SMTP_IS_CONFIGURED(self) -> bool:
        return bool(
            self.SMTP_HOST
            and self.SMTP_USERNAME
            and self.SMTP_PASSWORD
            and self.SMTP_FROM_EMAIL
        )

    @property
    def PASSWORD_RESET_IS_CONFIGURED(self) -> bool:
        return bool(
            self.SMTP_IS_CONFIGURED
            and self.PASSWORD_RESET_URL_BASE
        )

    @property
    def EMAIL_VERIFICATION_IS_CONFIGURED(self) -> bool:
        return bool(
            self.SMTP_IS_CONFIGURED
            and self.EMAIL_VERIFY_REDIRECT_URL
        )

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

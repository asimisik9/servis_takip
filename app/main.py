# app/main.py

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import text
from contextlib import asynccontextmanager
from .database import create_tables
from .database.database import AsyncSessionLocal
from .database.seed import create_admin_if_not_exists
from .routers import auth, admin, driver, parent, location_ws, notification
from .tasks import cleanup_old_bus_locations
from jose import JWTError
from fastapi.middleware.cors import CORSMiddleware
from .middleware.audit import AuditMiddleware
from .core.config import settings
from .core.limiter import limiter
from .core.redis import redis_manager
from .core.exceptions import ResourceNotFoundException, BusinessRuleException
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import http.client
import asyncio
import logging

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Debug CORS origins
logger.info(f"Loaded BACKEND_CORS_ORIGINS: {settings.BACKEND_CORS_ORIGINS}")

CLEANUP_INTERVAL_HOURS = 6  # Her 6 saatte bir çalışır


async def _periodic_cleanup():
    """Background task: Her CLEANUP_INTERVAL_HOURS saatte bus_locations temizliği."""
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)
            logger.info("Periodic bus_locations cleanup starting...")
            deleted = await cleanup_old_bus_locations()
            logger.info(f"Periodic cleanup finished: {deleted} rows deleted.")
        except asyncio.CancelledError:
            logger.info("Periodic cleanup task cancelled.")
            break
        except Exception:
            logger.exception("Periodic cleanup failed, will retry next cycle.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama başladığında çalışan fonksiyon.
    Veritabanı bağlantısını ve tablo oluşturma işlemini test eder.
    """
    logger.info("Veritabanı bağlantısı ve startup kontrolleri başlıyor...")
    if settings.ENVIRONMENT != "production":
        await create_tables()  # Development convenience
        logger.info("Veritabanı tabloları doğrulandı/oluşturuldu.")
    else:
        logger.info("Production ortamı: create_tables atlandı (Alembic migration bekleniyor).")
    
    # Redis bağlantısı
    await redis_manager.connect()
    
    # Seed initial data
    await create_admin_if_not_exists()
    
    # Periodic cleanup task
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    logger.info("Periodic bus_locations cleanup task scheduled (every %d hours).", CLEANUP_INTERVAL_HOURS)
    
    yield
    
    # Cleanup task'ı durdur
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    # Redis bağlantısını kapat
    await redis_manager.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Okul servis araçları takip sistemi API'si",
    version=settings.VERSION,
    lifespan=lifespan
)

# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Audit Middleware - KVKK/GDPR compliance (Inner - runs after CORS)
app.add_middleware(AuditMiddleware)

# HTTPS Redirect (Production only) with health endpoint exceptions.
if settings.ENVIRONMENT == "production":
    @app.middleware("http")
    async def enforce_https(request: Request, call_next):
        if request.url.path in {"/health", "/readiness"}:
            return await call_next(request)

        if request.headers.get("x-forwarded-proto", "http") != "https":
            secure_url = str(request.url.replace(scheme="https"))
            return RedirectResponse(url=secure_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

        return await call_next(request)

# CORS middleware - Production requires explicit origins
if settings.BACKEND_CORS_ORIGINS:
    origins = settings.BACKEND_CORS_ORIGINS
else:
    if settings.ENVIRONMENT == "production":
        raise ValueError(
            "BACKEND_CORS_ORIGINS must be set in production! "
            "Add allowed origins to .env file."
        )
    # Development fallback
    origins = ["*"]
    logger.warning("CORS: Using wildcard origins in development mode")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Include routers with prefix to ensure 401 instead of 404
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(driver.router, prefix=settings.API_V1_STR)
app.include_router(parent.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(notification.router, prefix=settings.API_V1_STR)
app.include_router(location_ws.router)

# Health Checks
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy"}

@app.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness_check():
    # Check DB connection
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Readiness check failed (DB): {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not ready")

    # Check Redis connection
    try:
        await redis_manager.redis.ping()
    except Exception as e:
        logger.error(f"Readiness check failed (Redis): {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis not ready")

    return {"status": "ready"}

# Global exception handlers
@app.exception_handler(JWTError)
async def jwt_error_handler(request: Request, exc: JWTError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "success": False,
            "error": "Unauthorized",
            "message": "Could not validate credentials"
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": http.client.responses.get(exc.status_code, "Error"),
            "message": str(exc.detail)
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Simplify validation errors
    errors = []
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"]) if error["loc"] else "unknown"
        msg = error["msg"]
        errors.append({"field": field, "message": msg})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Unprocessable Entity",
            "message": "Validation error",
            "details": errors
        }
    )

@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    # Veritabanı bütünlük hatası (Unique constraint, Foreign key vb.)
    # Production'da detay gizle
    detail = "Database integrity error."
    if settings.ENVIRONMENT == "development":
        detail = str(exc.orig)

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "success": False,
            "error": "Conflict",
            "message": detail
        }
    )

@app.exception_handler(OperationalError)
async def operational_exception_handler(request: Request, exc: OperationalError):
    # Veritabanı bağlantı hatası
    logger.error(f"Database operational error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "success": False,
            "error": "Service Unavailable",
            "message": "Database connection failed. Please try again later."
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    message = "An unexpected error occurred"
    if settings.ENVIRONMENT == "development":
        message = str(exc)
        
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal Server Error",
            "message": message
        }
    )

@app.exception_handler(ResourceNotFoundException)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundException):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "success": False,
            "error": "Not Found",
            "message": exc.message
        }
    )

@app.exception_handler(BusinessRuleException)
async def business_rule_handler(request: Request, exc: BusinessRuleException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": "Bad Request",
            "message": exc.message
        }
    )

@app.get("/")
async def read_root():
    return {
        "message": "Servis Takip API çalışıyor",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "version": settings.VERSION
    }

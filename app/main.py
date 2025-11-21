# app/main.py

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, OperationalError
from contextlib import asynccontextmanager
from .database import create_tables
from .routers import auth, admin, driver, parent, location_ws
from jose import JWTError
from fastapi.middleware.cors import CORSMiddleware
from .middleware.audit import AuditMiddleware
import http.client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama başladığında çalışan fonksiyon.
    Veritabanı bağlantısını ve tablo oluşturma işlemini test eder.
    """
    print("Veritabanı bağlantısı ve tablo oluşturma testi başlıyor...")
    await create_tables()
    print("Veritabanı hazır. Tablolar başarıyla oluşturuldu/var.")
    yield

app = FastAPI(
    title="Servis Takip API",
    description="Okul servis araçları takip sistemi API'si",
    version="1.0.0",
    lifespan=lifespan
)

# Audit Middleware (Inner - runs after CORS)
app.add_middleware(AuditMiddleware)

# CORS middleware - Tüm origin'lere izin ver (geliştirme için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with prefix to ensure 401 instead of 404
app.include_router(auth.router)
app.include_router(driver.router, prefix="/api")
app.include_router(parent.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(location_ws.router)

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
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "success": False,
            "error": "Conflict",
            "message": "Database integrity error. This usually means a duplicate record or invalid reference.",
            # Güvenlik nedeniyle detayları production'da gizlemek isteyebilirsiniz
            # "details": str(exc.orig) 
        }
    )

@app.exception_handler(OperationalError)
async def operational_exception_handler(request: Request, exc: OperationalError):
    # Veritabanı bağlantı hatası
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
    print(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )

@app.get("/")
async def read_root():
    return {
        "message": "Servis Takip API çalışıyor",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
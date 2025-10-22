# app/main.py

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from .database import create_tables
from .routers import auth, admin, driver, parent, location_ws
from jose import JWTError
from fastapi.middleware.cors import CORSMiddleware

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
        content={"detail": "Could not validate credentials"}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.get("/")
async def read_root():
    return {
        "message": "Servis Takip API çalışıyor",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
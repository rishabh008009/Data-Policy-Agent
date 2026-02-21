"""FastAPI application initialization for the Data Policy Agent."""

import bcrypt
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from pydantic import BaseModel, EmailStr
from jose import jwt
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import close_db, get_db
from app.models.user import User
from app.routers import dashboard, database, monitoring, policies, rules, violations
from app.services.scheduler import get_monitoring_scheduler, reset_monitoring_scheduler

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"

SECRET_KEY = "hackathon-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

security = HTTPBearer()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Debug mode: {settings.debug}")
    scheduler = get_monitoring_scheduler()
    scheduler.start()
    print("Monitoring scheduler started")
    yield
    print("Shutting down application...")
    reset_monitoring_scheduler()
    print("Monitoring scheduler stopped")
    await close_db()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered compliance monitoring system for automated policy violation detection",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
        }

    @app.post("/api/auth/register", tags=["Auth"])
    async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
        # Check if user already exists
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(email=data.email, password_hash=hash_password(data.password))
        db.add(user)
        await db.flush()

        token = create_token(user.email)
        return {"access_token": token, "token_type": "bearer"}

    @app.post("/api/auth/login", tags=["Auth"])
    async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_token(user.email)
        return {"access_token": token, "token_type": "bearer"}

    @app.get("/api/protected")
    def protected_route(credentials: HTTPAuthorizationCredentials = Depends(security)):
        try:
            jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            return {"message": "You are authenticated"}
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    @app.get("/api", tags=["Root"])
    async def api_root() -> dict:
        return {
            "message": f"Welcome to {settings.app_name} API",
            "version": settings.app_version,
            "docs": "/api/docs",
        }

    # Register routers
    app.include_router(policies.router)
    app.include_router(rules.router)
    app.include_router(database.router)
    app.include_router(violations.router)
    app.include_router(monitoring.router)
    app.include_router(dashboard.router)

    # Serve frontend
    if FRONTEND_DIR.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_frontend(request: Request, full_path: str):
            if full_path.startswith("api/") or full_path == "health":
                return {"detail": "Not Found"}
            index_path = FRONTEND_DIR / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return {"detail": "Frontend not built"}

    return app


app = create_app()

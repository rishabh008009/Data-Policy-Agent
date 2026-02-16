"""FastAPI application initialization for the Data Policy Agent."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from pydantic import BaseModel
from jose import jwt
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


from app.config import get_settings
from app.database import close_db
from app.routers import dashboard, database, monitoring, policies, rules, violations
from app.services.scheduler import get_monitoring_scheduler, reset_monitoring_scheduler

# Path to the frontend build directory
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup: Initialize resources
    settings = get_settings()
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Debug mode: {settings.debug}")
    
    # Start the monitoring scheduler
    scheduler = get_monitoring_scheduler()
    scheduler.start()
    print("Monitoring scheduler started")
    
    yield
    
    # Shutdown: Cleanup resources
    print("Shutting down application...")
    
    # Shutdown the monitoring scheduler
    reset_monitoring_scheduler()
    print("Monitoring scheduler stopped")
    
    await close_db()
    SECRET_KEY = "hackathon-secret-key"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
class Login(BaseModel):
    email: str
    password: str
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
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

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
        }
    # Auth login endpoint
    @app.post("/api/auth/login", tags=["Auth"])
    def login(data: Login):
        # Simple hardcoded validation (hackathon only)
        if data.email != "admin@test.com" or data.password != "password":
            raise HTTPException(status_code=401, detail="Invalid credentials")
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
        "sub": data.email,
        "exp": expire
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "token_type": "bearer"
    }
    @app.get("/api/protected")
def protected_route(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return {"message": "You are authenticated"}
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    # API root endpoint
    @app.get("/api", tags=["Root"])
    async def api_root() -> dict:
        """API root endpoint with available routes."""
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

    # Serve frontend static files if the build exists
    if FRONTEND_DIR.exists():
        # Mount static assets
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
        
        # Catch-all route to serve the React app for client-side routing
        @app.get("/{full_path:path}")
        async def serve_frontend(request: Request, full_path: str):
            """Serve the React frontend for all non-API routes."""
            # Don't serve frontend for API routes
            if full_path.startswith("api/") or full_path == "health":
                return {"detail": "Not Found"}
            
            # Serve index.html for all other routes (React handles routing)
            index_path = FRONTEND_DIR / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return {"detail": "Frontend not built"}

    return app


# Create the application instance
app = create_app()

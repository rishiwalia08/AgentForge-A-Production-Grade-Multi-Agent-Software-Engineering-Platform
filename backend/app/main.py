from __future__ import annotations

import time
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logger import setup_logging
from app.core.metrics import SystemMetrics
from app.db import init_db, get_db

settings = get_settings()

# Setup logging (JSON in production, text in dev)
setup_logging(settings.environment)

# Initialize database schema only for development and tests
# In production, Alembic migrations run during deploy
if settings.environment != "production":
    init_db()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="SaaS API Layer for Multi-Agent Software Engineering Platform"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
allowed_origins = [settings.frontend_url]
if "http://localhost:3000" not in allowed_origins:
    allowed_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics Middleware to track request counts and durations
class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/metrics", "/health"):
            return await call_next(request)
            
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        SystemMetrics.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code
        )
        SystemMetrics.record_latency(
            endpoint=request.url.path,
            duration_sec=duration
        )
        return response

app.add_middleware(MetricsMiddleware)

# Import Routers
from app.api.routes.auth import router as auth_router
from app.api.routes.projects import router as projects_router
from app.api.routes.runs import router as runs_router
from app.api.routes.observability import router as observability_router

# Register routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(runs_router)
app.include_router(observability_router)

@app.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    # 1. Database Check
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1")).scalar()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # 2. Redis Check
    try:
        import redis
        client = redis.Redis.from_url(settings.redis_url, socket_timeout=1.0)
        client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    # 3. Worker Check (Check Celery active workers status)
    try:
        from app.core.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=1.0)
        pings = inspector.ping() if inspector else None
        worker_status = "alive" if pings else "offline"
    except Exception:
        worker_status = "offline"

    return {
        "api": "healthy",
        "database": db_status,
        "redis": redis_status,
        "worker": worker_status
    }

@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    return SystemMetrics.generate_prometheus_output()

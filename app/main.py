import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

import app.models  # noqa: F401 — registers all ORM models with SQLAlchemy metadata
from app.api import routes_admin, routes_metals, routes_items, routes_locations
from app.config.settings import allowed_origins
from app.db.database import Base, engine, SessionLocal
from app.utils.limiter import limiter

# ── Logging ───────────────────────────────────────────────────────────────────

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    # Quiet noisy libraries
    "loggers": {
        "uvicorn.access": {"level": "WARNING"},
        "apscheduler": {"level": "WARNING"},
    },
})

logger = logging.getLogger(__name__)


# ── Security headers ──────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    Base.metadata.create_all(bind=engine)

    from app.services import scheduler_service
    db = SessionLocal()
    try:
        scheduler_service.start(db)
    finally:
        db.close()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    scheduler_service.stop()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Gold Shop API",
    description="Jewelry inventory backend for a gold shop — supports EN/ES.",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers (applied to every response)
app.add_middleware(SecurityHeadersMiddleware)

# CORS — only the specific methods and headers this API actually uses
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(routes_items.router)
app.include_router(routes_admin.router)
app.include_router(routes_metals.router)
app.include_router(routes_locations.router)


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}

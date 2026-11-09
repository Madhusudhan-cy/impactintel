import logging
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import api_router
from app.core.config import FRONTEND_URL, CORS_ORIGINS
from app.db.session import init_db

logger = logging.getLogger(__name__)


def get_cors_origins() -> List[str]:
    """
    Build explicit list of trusted CORS origins from configuration.
    Wildcards ('*') are strictly disallowed to maintain secure credential handling.
    """
    trusted_defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    origins: List[str] = []

    def _add_origin(val: str) -> None:
        cleaned = val.strip().rstrip("/")
        if cleaned and cleaned != "*" and cleaned not in origins:
            origins.append(cleaned)

    for default in trusted_defaults:
        _add_origin(default)

    if FRONTEND_URL:
        _add_origin(FRONTEND_URL)

    if CORS_ORIGINS:
        for item in CORS_ORIGINS.split(","):
            _add_origin(item)

    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Initializing ImpactIntel backend application...")
    try:
        init_db()
    except Exception as exc:
        logger.error(f"Critical error during database startup: {exc}", exc_info=True)
        raise
    yield
    logger.info("Shutting down ImpactIntel backend application.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI backend application."""
    app = FastAPI(
        title="AI-Powered Repository Impact Intelligence API",
        version="0.2.0",
        description="Backend API for GitHub PR impact analysis, Code Knowledge Graph indexing, and webhooks.",
        lifespan=lifespan
    )

    # Enable CORS only for explicitly configured trusted origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()

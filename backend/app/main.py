"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import init_db


def create_application() -> FastAPI:
    """Initialize FastAPI application with configured routers."""
    application = FastAPI(
        title="LLM Finetune Platform",
        description="Core backend service for the llm-finetune-platform project.",
        version="0.1.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix="/api")
    return application


app = create_application()


@app.on_event("startup")
def _startup() -> None:
    """Create database tables automatically in non-production environments."""
    if settings.environment != "production":
        init_db()

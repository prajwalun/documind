"""Main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import ingestion, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: Cleanup if needed
    pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG-powered document ingestion and retrieval API",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(
    ingestion.router,
    prefix=settings.API_V1_STR,
    tags=["ingestion"]
)

app.include_router(
    chat.router,
    prefix=settings.API_V1_STR,
    tags=["chat"]
)


@app.get("/")
def read_root():
    """Root endpoint."""
    return {"message": "Welcome to DocuMind API"}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
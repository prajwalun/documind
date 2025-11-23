"""Database configuration and session management with pgvector support."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    Dependency function to get database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database: create tables, enable extensions, and set up triggers.
    
    This should be called on application startup.
    """
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Create trigger function to automatically update tsvector when content changes
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_document_chunks_tsvector()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.content_tsvector := to_tsvector('english', COALESCE(NEW.content, ''));
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Create trigger (drop if exists first to avoid errors on re-runs)
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS document_chunks_tsvector_update ON document_chunks;
        """))
        
        await conn.execute(text("""
            CREATE TRIGGER document_chunks_tsvector_update
            BEFORE INSERT OR UPDATE OF content ON document_chunks
            FOR EACH ROW
            EXECUTE FUNCTION update_document_chunks_tsvector();
        """))
        
        # Update existing rows that might not have tsvector set
        await conn.execute(text("""
            UPDATE document_chunks 
            SET content_tsvector = to_tsvector('english', content)
            WHERE content_tsvector IS NULL;
        """))

"""Database models for documents and document chunks."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
import enum

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    """Status of document processing."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """Document model representing uploaded PDF files."""
    
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    upload_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationship to chunks
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """Document chunk model with vector embeddings and full-text search."""
    
    __tablename__ = "document_chunks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    embedding: Mapped[Vector] = mapped_column(
        Vector(1536),  # OpenAI ada-002 embedding dimension
        nullable=True
    )
    # Full-text search column for hybrid search
    content_tsvector: Mapped[Optional[TSVECTOR]] = mapped_column(
        TSVECTOR,
        nullable=True
    )
    
    # Relationship to document
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    
    # Index for full-text search performance
    __table_args__ = (
        Index('ix_document_chunks_content_tsvector', 'content_tsvector', postgresql_using='gin'),
    )

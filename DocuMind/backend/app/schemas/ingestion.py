"""Pydantic schemas for ingestion API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    """Response schema for document creation."""
    
    id: int
    filename: str
    upload_date: datetime
    page_count: int = 0
    status: str
    
    class Config:
        from_attributes = True


class IngestionStatus(BaseModel):
    """Response schema for ingestion status."""
    
    document_id: int
    status: str
    page_count: int = 0
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class IngestionResponse(BaseModel):
    """Response schema for ingestion endpoint."""
    
    message: str
    document_id: int
    status: str = Field(default="pending")

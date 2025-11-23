"""Pydantic schemas for chat API."""
from typing import List
from pydantic import BaseModel, Field


class Source(BaseModel):
    """Source citation for an answer."""
    
    filename: str = Field(..., description="Name of the source document")
    page_number: int = Field(..., description="Page number in the source document")
    chunk_id: int = Field(..., description="ID of the chunk used")


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    
    query: str = Field(..., description="User's question or query", min_length=1)


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""
    
    answer: str = Field(..., description="Generated answer based on context")
    sources: List[Source] = Field(default_factory=list, description="List of source citations")

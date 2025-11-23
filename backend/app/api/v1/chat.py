"""API endpoints for chat and retrieval."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.rag_service import RagService
from app.schemas.chat import ChatRequest, ChatResponse, Source

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    """
    Chat endpoint that performs hybrid search and generates answers.
    
    This endpoint:
    1. Performs hybrid search (vector + keyword) to find relevant chunks
    2. Generates an answer using the retrieved context
    3. Returns the answer with source citations
    
    Args:
        request: Chat request with user query
        db: Database session
        
    Returns:
        ChatResponse with answer and sources
    """
    try:
        rag_service = RagService()
        
        # Step 1: Hybrid search to find relevant chunks
        context_chunks = await rag_service.hybrid_search(
            query=request.query,
            db=db,
            limit=5
        )
        
        # Step 2: Generate answer using the context
        answer, sources_data = await rag_service.generate_answer(
            query=request.query,
            context_chunks=context_chunks
        )
        
        # Convert sources data to Source objects
        sources = [
            Source(
                filename=src["filename"],
                page_number=src["page_number"],
                chunk_id=src["chunk_id"]
            )
            for src in sources_data
        ]
        
        return ChatResponse(
            answer=answer,
            sources=sources
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {str(e)}"
        )

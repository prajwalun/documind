"""API endpoints for document ingestion."""
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.services.ingestion_service import IngestionService
from app.schemas.ingestion import IngestionResponse, IngestionStatus
from app.models.document import DocumentStatus

router = APIRouter()


async def process_document_background(
    file_content: bytes,
    filename: str,
    document_id: int
) -> None:
    """
    Background task to process a document.
    
    Args:
        file_content: File content as bytes
        filename: Original filename
        document_id: ID of the created document
    """
    # Create a new database session for the background task
    async with AsyncSessionLocal() as db:
        try:
            from io import BytesIO
            background_file = UploadFile(
                filename=filename,
                file=BytesIO(file_content)
            )
            
            service = IngestionService()
            await service.process_pdf(background_file, db)
        except Exception as e:
            # Error handling is done in the service
            # The document status will be updated to FAILED
            print(f"Error processing document {document_id}: {str(e)}")


@router.post("/ingest", response_model=IngestionResponse)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
) -> IngestionResponse:
    """
    Upload and ingest a PDF document.
    
    This endpoint accepts a PDF file, creates a document record immediately,
    and processes it in the background.
    
    Args:
        background_tasks: FastAPI background tasks
        file: PDF file to upload
        db: Database session
        
    Returns:
        IngestionResponse with document_id and status
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # Create document record with PENDING status
    from app.models.document import Document
    document = Document(
        filename=file.filename,
        status=DocumentStatus.PENDING,
        page_count=0
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Read file content for background processing
    # Note: We need to read the file content first since UploadFile
    # might not be reusable after the request
    file_content = await file.read()
    
    # Add background task to process the document
    background_tasks.add_task(
        process_document_background,
        file_content,
        file.filename,
        document.id
    )
    
    return IngestionResponse(
        message="Document uploaded successfully. Processing in background.",
        document_id=document.id,
        status="pending"
    )


@router.get("/status/{document_id}", response_model=IngestionStatus)
async def get_ingestion_status(
    document_id: int,
    db: AsyncSession = Depends(get_db)
) -> IngestionStatus:
    """
    Get the status of a document ingestion.
    
    Args:
        document_id: Document ID
        db: Database session
        
    Returns:
        IngestionStatus with current status
    """
    service = IngestionService()
    document = await service.get_document_status(document_id, db)
    
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document with ID {document_id} not found"
        )
    
    return IngestionStatus(
        document_id=document.id,
        status=document.status.value,
        page_count=document.page_count,
        error_message=document.error_message
    )

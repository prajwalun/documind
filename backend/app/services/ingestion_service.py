"""Ingestion service for processing PDF documents."""
import os
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.models.document import Document, DocumentChunk, DocumentStatus


class IngestionService:
    """Service for ingesting and processing PDF documents."""
    
    def __init__(self):
        """Initialize the ingestion service with OpenAI embeddings."""
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            model="text-embedding-ada-002"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
    
    async def process_pdf(
        self,
        file: UploadFile,
        db: AsyncSession
    ) -> Document:
        """
        Process a PDF file: load, chunk, embed, and store in database.
        
        Args:
            file: Uploaded PDF file
            db: Database session
            
        Returns:
            Document: Created document record
            
        Raises:
            Exception: If processing fails
        """
        temp_file_path = None
        try:
            # Save uploaded file temporarily
            suffix = Path(file.filename).suffix if file.filename else ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                temp_file_path = tmp_file.name
            
            # Create document record
            document = Document(
                filename=file.filename or "unknown.pdf",
                status=DocumentStatus.PENDING,
                page_count=0
            )
            db.add(document)
            await db.flush()  # Get the document ID
            
            # Load PDF using LangChain
            loader = PyPDFLoader(temp_file_path)
            pages = loader.load()
            
            # Update page count
            document.page_count = len(pages)
            await db.flush()
            
            # Process each page and create chunks
            all_chunks = []
            for page_idx, page in enumerate(pages, start=1):
                # Split page content into chunks
                chunks = self.text_splitter.split_text(page.page_content)
                
                for chunk_idx, chunk_text in enumerate(chunks):
                    all_chunks.append({
                        "document_id": document.id,
                        "content": chunk_text,
                        "page_number": page_idx,
                        "chunk_index": chunk_idx
                    })
            
            # Generate embeddings for all chunks in batch
            chunk_texts = [chunk["content"] for chunk in all_chunks]
            embeddings_list = await self._generate_embeddings_async(chunk_texts)
            
            # Create DocumentChunk records with embeddings
            chunk_objects = []
            for chunk_data, embedding in zip(all_chunks, embeddings_list):
                chunk_obj = DocumentChunk(
                    document_id=chunk_data["document_id"],
                    content=chunk_data["content"],
                    page_number=chunk_data["page_number"],
                    chunk_index=chunk_data["chunk_index"],
                    embedding=embedding
                )
                chunk_objects.append(chunk_obj)
            
            # Bulk insert chunks
            db.add_all(chunk_objects)
            await db.flush()  # Flush to get IDs
            
            # Update tsvector for full-text search (PostgreSQL will handle this via trigger or we do it manually)
            # We'll use a trigger in the database, but for now we can update it manually
            from sqlalchemy import text
            await db.execute(
                text("""
                    UPDATE document_chunks 
                    SET content_tsvector = to_tsvector('english', content)
                    WHERE document_id = :doc_id
                """),
                {"doc_id": document.id}
            )
            
            # Update document status to completed
            document.status = DocumentStatus.COMPLETED
            
            # Commit all changes
            await db.commit()
            
            # Refresh to get the latest state
            await db.refresh(document)
            
            return document
            
        except Exception as e:
            # Rollback on error
            await db.rollback()
            
            # Update document status to failed if it was created
            if 'document' in locals() and document.id:
                document.status = DocumentStatus.FAILED
                document.error_message = str(e)
                await db.commit()
            
            raise e
            
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    async def _generate_embeddings_async(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts asynchronously.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        # OpenAIEmbeddings.embed_documents is synchronous, but we run it in executor
        # to avoid blocking the event loop
        import asyncio
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            self.embeddings.embed_documents,
            texts
        )
        return embeddings
    
    async def get_document_status(
        self,
        document_id: int,
        db: AsyncSession
    ) -> Optional[Document]:
        """
        Get document status by ID.
        
        Args:
            document_id: Document ID
            db: Database session
            
        Returns:
            Document if found, None otherwise
        """
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

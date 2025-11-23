"""RAG service for hybrid search and answer generation."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from sqlalchemy.orm import selectinload
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

from app.core.config import settings
from app.models.document import DocumentChunk, Document
from langchain_openai import OpenAIEmbeddings


class RagService:
    """Service for Retrieval-Augmented Generation with hybrid search."""
    
    def __init__(self):
        """Initialize the RAG service with OpenAI models."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            model="text-embedding-ada-002"
        )
    
    async def hybrid_search(
        self,
        query: str,
        db: AsyncSession,
        limit: int = 5
    ) -> List[DocumentChunk]:
        """
        Perform hybrid search combining vector similarity and full-text search.
        
        Args:
            query: Search query string
            db: Database session
            limit: Maximum number of results to return
            
        Returns:
            List of DocumentChunk objects with document relationship loaded
        """
        # Generate query embedding
        query_embedding = await self._generate_query_embedding(query)
        
        # Vector search: cosine similarity using pgvector
        vector_results = await self._vector_search(query_embedding, db, limit=3)
        
        # Keyword search: full-text search using tsvector
        keyword_results = await self._keyword_search(query, db, limit=3)
        
        # Combine and deduplicate results
        combined_results = self._merge_results(vector_results, keyword_results, limit)
        
        return combined_results
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        db: AsyncSession,
        limit: int = 3
    ) -> List[DocumentChunk]:
        """
        Perform vector similarity search using pgvector.
        
        Args:
            query_embedding: Query embedding vector
            db: Database session
            limit: Maximum number of results
            
        Returns:
            List of DocumentChunk objects
        """
        # Use cosine distance (1 - cosine similarity)
        # Lower distance = higher similarity
        result = await db.execute(
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.embedding.isnot(None))
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .options(selectinload(DocumentChunk.document))
        )
        
        chunks = [row[0] for row in result.all()]
        return chunks
    
    async def _keyword_search(
        self,
        query: str,
        db: AsyncSession,
        limit: int = 3
    ) -> List[DocumentChunk]:
        """
        Perform full-text keyword search using PostgreSQL tsvector.
        
        Args:
            query: Search query string
            db: Database session
            limit: Maximum number of results
            
        Returns:
            List of DocumentChunk objects
        """
        try:
            # Convert query to tsquery format
            # Replace spaces with & for AND matching
            # Escape special characters that might break tsquery
            query_clean = query.strip()
            # Replace multiple spaces with single space
            query_clean = " ".join(query_clean.split())
            # Replace spaces with & for AND matching
            query_terms = query_clean.replace(" ", " & ")
            
            # Use plainto_tsquery which is more forgiving than to_tsquery
            # It handles special characters better
            result = await db.execute(
                select(DocumentChunk, Document)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(
                    DocumentChunk.content_tsvector.isnot(None),
                    func.plainto_tsquery('english', query_clean).op('@@')(DocumentChunk.content_tsvector)
                )
                .order_by(
                    func.ts_rank(DocumentChunk.content_tsvector, func.plainto_tsquery('english', query_clean)).desc()
                )
                .limit(limit)
                .options(selectinload(DocumentChunk.document))
            )
            
            chunks = [row[0] for row in result.all()]
            return chunks
        except Exception as e:
            # If tsvector search fails, return empty list
            # Vector search will still work
            print(f"Keyword search error: {str(e)}")
            return []
    
    def _merge_results(
        self,
        vector_results: List[DocumentChunk],
        keyword_results: List[DocumentChunk],
        limit: int
    ) -> List[DocumentChunk]:
        """
        Merge and deduplicate search results from vector and keyword searches.
        
        Args:
            vector_results: Results from vector search
            keyword_results: Results from keyword search
            limit: Maximum number of results to return
            
        Returns:
            Deduplicated list of DocumentChunk objects
        """
        seen_ids = set()
        merged = []
        
        # Add vector results first (they're typically more semantically relevant)
        for chunk in vector_results:
            if chunk.id not in seen_ids:
                merged.append(chunk)
                seen_ids.add(chunk.id)
        
        # Add keyword results that aren't already included
        for chunk in keyword_results:
            if chunk.id not in seen_ids:
                merged.append(chunk)
                seen_ids.add(chunk.id)
        
        # Return up to limit results
        return merged[:limit]
    
    async def _generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a query string.
        
        Args:
            query: Query string
            
        Returns:
            Embedding vector
        """
        import asyncio
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            self.embeddings.embed_query,
            query
        )
        return embedding
    
    async def generate_answer(
        self,
        query: str,
        context_chunks: List[DocumentChunk]
    ) -> tuple[str, List[dict]]:
        """
        Generate an answer using the provided context chunks.
        
        Args:
            query: User's question
            context_chunks: List of relevant document chunks
            
        Returns:
            Tuple of (answer_text, sources_list)
            sources_list contains dicts with 'filename' and 'page_number'
        """
        if not context_chunks:
            return "I couldn't find any relevant information in the documents to answer your question.", []
        
        # Build context from chunks
        context_parts = []
        sources = []
        
        for idx, chunk in enumerate(context_chunks, start=1):
            filename = chunk.document.filename if chunk.document else "Unknown"
            context_parts.append(
                f"[Context {idx}] (Source: {filename}, Page {chunk.page_number})\n{chunk.content}\n"
            )
            sources.append({
                "filename": filename,
                "page_number": chunk.page_number,
                "chunk_id": chunk.id
            })
        
        context = "\n".join(context_parts)
        
        # Create prompt template
        system_template = """You are a helpful assistant that answers questions based ONLY on the provided context.

CRITICAL RULES:
1. Answer using ONLY the information provided in the context below.
2. If the context doesn't contain enough information to answer, say "I don't have enough information in the provided documents to answer this question."
3. Always cite your sources using the format: [Source: filename, Page X]
4. Be precise and factual. Do not make up information.
5. If you reference specific information, include the source citation in your answer.

Context:
{context}"""

        human_template = "Question: {query}\n\nAnswer:"

        system_message = SystemMessagePromptTemplate.from_template(system_template)
        human_message = HumanMessagePromptTemplate.from_template(human_template)
        
        chat_prompt = ChatPromptTemplate.from_messages([
            system_message,
            human_message
        ])
        
        # Generate response
        messages = chat_prompt.format_messages(context=context, query=query)
        
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.llm.invoke(messages)
        )
        
        answer = response.content
        
        return answer, sources

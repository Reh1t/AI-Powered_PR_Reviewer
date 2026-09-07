import logging
from typing import List, Optional
from fastembed import TextEmbedding
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.memory import CodeEmbedding
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

logger = logging.getLogger("rag-service")

class RAGService:
    def __init__(self):
        # Initializes the local embedding model (downloads on first run)
        self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    
    def embed_text(self, text: str) -> List[float]:
        """
        Embeds a string of text into a vector using fastembed.
        """
        # fastembed returns a generator yielding numpy arrays
        embeddings = list(self.embedding_model.embed([text]))
        return embeddings[0].tolist()

    def chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
        """Splits a large file into smaller overlapping chunks to preserve VRAM during context injection."""
        if len(text) <= chunk_size:
            return [text]
            
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    async def ingest_file(self, repo: str, file_path: str, content: str):
        """
        Ingests a file into the vector database using semantic chunking.
        """
        chunks = self.chunk_text(content)
        
        async with AsyncSessionLocal() as session:
            for i, chunk in enumerate(chunks):
                vector = self.embed_text(chunk)
                
                # Add a chunk indicator to the file path so the AI knows it's a snippet
                chunk_path = f"{file_path} (Chunk {i+1}/{len(chunks)})" if len(chunks) > 1 else file_path
                
                db_embedding = CodeEmbedding(
                    repo=repo,
                    file_path=chunk_path,
                    content_chunk=chunk,
                    embedding=vector
                )
                session.add(db_embedding)
            
            await session.commit()
            logger.info(f"Ingested {file_path} ({len(chunks)} chunks) for repo {repo}")

    async def retrieve_context(self, repo: str, pr_diff_text: str, limit: int = 5) -> str:
        """
        Embeds the PR diff and searches for the most semantically similar files 
        in the codebase to provide historical context.
        """
        vector = self.embed_text(pr_diff_text)
        
        async with AsyncSessionLocal() as session:
            # CodeEmbedding.embedding.cosine_distance(vector) -> uses pgvector <=> operator
            # Threshold: < 0.5 distance (closer to 0 is better)
            stmt = select(CodeEmbedding).filter_by(repo=repo).filter(
                CodeEmbedding.embedding.cosine_distance(vector) < 0.5
            ).order_by(
                CodeEmbedding.embedding.cosine_distance(vector)
            ).limit(limit)
            
            result = await session.execute(stmt)
            matches = result.scalars().all()
            
            if not matches:
                return "No historical context found in RAG memory."
                
            context = "### Historical RAG Context (Semantically Related Files) ###\n\n"
            for match in matches:
                context += f"--- FILE: {match.file_path} ---\n{match.content_chunk}\n\n"
                
            return context

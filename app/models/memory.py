from sqlalchemy import Column, String, Integer, Text
from pgvector.sqlalchemy import Vector
from app.models.base import Base

class CodeEmbedding(Base):
    __tablename__ = "code_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    content_chunk = Column(Text, nullable=False)
    # fastembed default model (BAAI/bge-small-en-v1.5) uses 384 dimensions
    embedding = Column(Vector(384))

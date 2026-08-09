from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.core.config import settings
from app.models.base import Base

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(Integer, ForeignKey("pages.id", ondelete="CASCADE"), nullable=True)
    chunk_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    chunk_metadata = Column("metadata", JSON, nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)
    embedding = Column(Vector(settings.embedding_dimension), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")
    page = relationship("Page", back_populates="chunks")

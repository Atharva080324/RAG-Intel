from datetime import datetime
from sqlalchemy import Column, DateTime, LargeBinary, String
from app.models.base import Base


class StoredFile(Base):
    """Raw uploaded bytes stored in PostgreSQL so both the API and worker
    (which connect to the same database) can access the file. This avoids any
    external object store or shared filesystem."""

    __tablename__ = "stored_files"

    key = Column(String(512), primary_key=True)
    content = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

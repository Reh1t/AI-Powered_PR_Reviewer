from sqlalchemy import Column, String, Integer, DateTime, JSON
from sqlalchemy.sql import func
from app.models.base import Base

class PRReview(Base):
    __tablename__ = "pr_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner = Column(String, nullable=False, index=True)
    repo = Column(String, nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    commit_sha = Column(String, nullable=False)
    status = Column(String, nullable=False)  # e.g., "COMMENT", "APPROVE", "REQUEST_CHANGES", "ERROR"
    findings_count = Column(Integer, default=0)
    findings_summary = Column(JSON, nullable=True) # Store JSON of findings for audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())

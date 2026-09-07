from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.sql import func
import enum
from app.models.base import Base

class WebhookStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    delivery_id = Column(String, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    action = Column(String, nullable=True)
    status = Column(Enum(WebhookStatus), default=WebhookStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

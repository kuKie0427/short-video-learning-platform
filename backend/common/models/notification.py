"""
消息通知模型
"""
import uuid
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

UUIDType = UUID(as_uuid=True)


class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    related_id = Column(String(100))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="notifications")
    
    __table_args__ = (
        Index('idx_notifications_user_id', 'user_id'),
        Index('idx_notifications_is_read', 'is_read'),
    )


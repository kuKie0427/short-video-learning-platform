"""
视频上传相关模型
"""
import uuid
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY as PG_ARRAY
from .base import Base

UUIDType = UUID(as_uuid=True)
ARRAY = PG_ARRAY


class UploadTask(Base):
    __tablename__ = 'upload_tasks'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    upload_id = Column(String(100), unique=True, nullable=False)
    user_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    duration = Column(Integer)
    status = Column(String(20), nullable=False, default='uploading')
    completed_chunks = Column(ARRAY(Integer))
    video_type = Column(String(20), default='short')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", backref="upload_tasks")
    
    __table_args__ = (
        Index('idx_upload_tasks_user_id', 'user_id'),
    )


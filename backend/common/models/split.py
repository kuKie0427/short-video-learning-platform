"""
视频拆分相关模型
"""
import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, func, DECIMAL, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import Base

UUIDType = UUID(as_uuid=True)
JSON = JSONB


class SplitTask(Base):
    __tablename__ = 'split_tasks'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    task_id = Column(String(100), unique=True, nullable=False)
    long_video_id = Column(UUIDType, ForeignKey('long_videos.id'), nullable=False)
    user_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    split_mode = Column(String(20), nullable=False)
    auto_config = Column(JSONB)
    organization_mode = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    progress = Column(DECIMAL(5, 2), default=0.00)
    progress_message = Column(Text, default="任务初始化中...")
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    long_video = relationship("LongVideo", backref="split_tasks")
    user = relationship("User", backref="split_tasks")
    
    __table_args__ = (
        Index('idx_split_tasks_user_id', 'user_id'),
        Index('idx_split_tasks_status', 'status'),
        Index('idx_split_tasks_long_video_id', 'long_video_id'),
    )


class SplitSegment(Base):
    __tablename__ = 'split_segments'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    task_id = Column(UUIDType, ForeignKey('split_tasks.id'), nullable=False)
    segment_index = Column(Integer, nullable=False)
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    thumbnail_url = Column(String(500))
    scene_type = Column(String(50))
    confidence = Column(DECIMAL(5, 2))
    video_id = Column(UUIDType, ForeignKey('videos.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    task = relationship("SplitTask", backref="split_segments")
    video = relationship("Video", backref="split_segments")
    
    __table_args__ = (
        Index('idx_split_segments_task_id', 'task_id'),
    )


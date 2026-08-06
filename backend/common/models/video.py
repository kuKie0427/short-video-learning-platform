"""
视频模型
"""
import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, func, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY as PG_ARRAY
from .base import Base

UUIDType = UUID(as_uuid=True)
ARRAY = PG_ARRAY


class Video(Base):
    __tablename__ = 'videos'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    author_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    tags = Column(ARRAY(String(50)))
    duration = Column(Integer, nullable=False)
    play_url = Column(String(500), nullable=False)
    cover_url = Column(String(500))
    language = Column(String(10), default='zh-CN')
    status = Column(String(20), nullable=False, default='pending')
    reject_reason = Column(Text)
    parent_video_id = Column(UUIDType, ForeignKey('long_videos.id'))
    course_id = Column(UUIDType, ForeignKey('courses.id'))
    segment_index = Column(Integer)
    video_type = Column(String(20), default='short')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    author = relationship("User", backref="videos")
    parent_long_video = relationship("LongVideo", foreign_keys=[parent_video_id])
    
    __table_args__ = (
        Index('idx_videos_author_id', 'author_id'),
        Index('idx_videos_status', 'status'),
        Index('idx_videos_video_type', 'video_type'),
    )


class LongVideo(Base):
    __tablename__ = 'long_videos'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    video_id = Column(UUIDType, ForeignKey('videos.id'), unique=True, nullable=False)
    original_duration = Column(Integer, nullable=False)
    original_file_url = Column(String(500), nullable=False)
    split_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    video = relationship("Video", backref="long_video", foreign_keys=[video_id])
    
    __table_args__ = (
        Index('idx_long_videos_video_id', 'video_id'),
    )


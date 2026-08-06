"""
课程相关模型
"""
import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, func, DECIMAL, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY as PG_ARRAY
from .base import Base

UUIDType = UUID(as_uuid=True)
ARRAY = PG_ARRAY


class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    course_id = Column(String(100), unique=True, nullable=False, default=lambda: f"course_{uuid.uuid4().hex[:12]}")
    author_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    tags = Column(ARRAY(String(50)))
    language = Column(String(10), default='zh-CN')
    cover_url = Column(String(500))
    status = Column(String(20), nullable=False, default='draft')
    reject_reason = Column(Text)
    total_videos = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    author = relationship("User", backref="courses")
    
    __table_args__ = (
        Index('idx_courses_author_id', 'author_id'),
        Index('idx_courses_status', 'status'),
    )


class CourseVideo(Base):
    __tablename__ = 'course_videos'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    course_id = Column(UUIDType, ForeignKey('courses.id'), nullable=False)
    video_id = Column(UUIDType, ForeignKey('videos.id'), nullable=False)
    segment_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    course = relationship("Course", backref="course_videos")
    video = relationship("Video", backref="course_videos")
    
    __table_args__ = (
        Index('idx_course_videos_course_id', 'course_id'),
    )


class LearnRecord(Base):
    __tablename__ = 'learn_records'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    video_id = Column(UUIDType, ForeignKey('videos.id'), nullable=False)
    last_position = Column(Integer, default=0)
    completed_ratio = Column(DECIMAL(5, 2), default=0.00)
    status = Column(String(20), default='not_started')
    last_watch_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", backref="learn_records")
    video = relationship("Video", backref="learn_records")
    
    __table_args__ = (
        Index('idx_learn_records_user_video', 'user_id', 'video_id'),
    )


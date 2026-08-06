"""
互动相关模型（评论、点赞、收藏、关注）
"""
import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

UUIDType = UUID(as_uuid=True)


class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    video_id = Column(UUIDType, ForeignKey('videos.id'), nullable=False)
    user_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    parent_id = Column(UUIDType, ForeignKey('comments.id'))
    content = Column(Text, nullable=False)
    like_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    video = relationship("Video", backref="comments")
    user = relationship("User", backref="comments")
    parent = relationship("Comment", remote_side=[id], backref="replies")
    
    __table_args__ = (
        Index('idx_comments_video_id', 'video_id'),
    )


class Like(Base):
    __tablename__ = 'likes'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    video_id = Column(UUIDType, ForeignKey('videos.id'), nullable=False)
    user_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    video = relationship("Video", backref="likes")
    user = relationship("User", backref="likes")
    
    __table_args__ = (
        Index('idx_likes_video_user', 'video_id', 'user_id'),
    )


class Favorite(Base):
    __tablename__ = 'favorites'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    video_id = Column(UUIDType, ForeignKey('videos.id'), nullable=False)
    user_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    video = relationship("Video", backref="favorites")
    user = relationship("User", backref="favorites")
    
    __table_args__ = (
        Index('idx_favorites_video_user', 'video_id', 'user_id'),
    )


class Follow(Base):
    """关注关系表"""
    __tablename__ = 'follows'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    follower_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    following_id = Column(UUIDType, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    follower = relationship("User", foreign_keys=[follower_id], backref="following_relations")
    following = relationship("User", foreign_keys=[following_id], backref="follower_relations")
    
    __table_args__ = (
        Index('idx_follows_follower_id', 'follower_id'),
        Index('idx_follows_following_id', 'following_id'),
        Index('idx_follows_follower_following', 'follower_id', 'following_id', unique=True),
    )


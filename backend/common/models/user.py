"""
用户模型
"""
import uuid
from sqlalchemy import Column, String, Text, DateTime, func, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY as PG_ARRAY
from .base import Base

UUIDType = UUID(as_uuid=True)
ARRAY = PG_ARRAY


class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False)
    nickname = Column(String(50), nullable=False)
    avatar_url = Column(String(500))
    bio = Column(Text)
    gender = Column(String(10), server_default='male')
    location = Column(String(100), nullable=True)
    school = Column(String(100), nullable=True)
    language = Column(String(10), default='zh-CN')
    roles = Column(ARRAY(String(50)), default=['learner'])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_users_phone', 'phone'),
    )


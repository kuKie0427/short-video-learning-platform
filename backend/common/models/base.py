"""
数据库模型基类
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 模型基类（SQLAlchemy 2.0 风格）"""


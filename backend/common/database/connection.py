"""
数据库连接管理
"""
import os
import logging
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import redis
from redis import Redis

from ..models.base import Base
from ..config.settings import settings

# 优先使用环境变量 DATABASE_URL（方便测试与不同部署）
DATABASE_URL = settings.DATABASE_URL
if not DATABASE_URL:
    # 从配置构建PostgreSQL连接URL（与数据库部署模块保持一致）
    # 使用 postgresql+psycopg:// 明确指定使用 psycopg 3.x（支持 Python 3.13）
    # 如果使用 psycopg2-binary，可以改为 postgresql:// 或 postgresql+psycopg2://
    if settings.DB_HOST and settings.DB_NAME:
        DATABASE_URL = f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        logging.info(f"使用PostgreSQL数据库: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    else:
        # 强制要求PostgreSQL配置
        error_msg = (
            "数据库配置缺失！请设置以下环境变量之一：\n"
            "  1. DATABASE_URL (完整连接URL)\n"
            "  2. DB_HOST, DB_NAME, DB_USER, DB_PASSWORD (PostgreSQL连接参数)\n"
            "注意：本系统仅支持PostgreSQL数据库，不支持SQLite"
        )
        logging.error(error_msg)
        raise ValueError(error_msg)

# 验证数据库URL必须是PostgreSQL（支持 postgresql://, postgresql+psycopg://, postgresql+psycopg2://）
if not (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgresql+psycopg")):
    error_msg = f"不支持的数据库类型！当前URL: {DATABASE_URL[:20]}...\n本系统仅支持PostgreSQL数据库"
    logging.error(error_msg)
    raise ValueError(error_msg)

# PostgreSQL配置
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,  # 5分钟回收连接
    pool_size=5,
    max_overflow=10,
    connect_args={
        "connect_timeout": 10,  # 连接超时10秒
        "application_name": "short_video_api"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """获取数据库会话（依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Redis连接池
_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    """获取Redis客户端（单例模式）"""
    global _redis_client
    if _redis_client is None:
        try:
            if settings.REDIS_URL:
                _redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            else:
                _redis_client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            # 测试连接
            _redis_client.ping()
            logging.info("Redis connection established successfully")
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            logging.warning("Redis connection failed, some features may not work properly")
            # 开发环境允许Redis连接失败，生产环境应该失败
            if settings.is_production:
                raise
    return _redis_client


def init_db():
    """初始化数据库，创建所有表"""
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        logging.info("Database tables created successfully")
        
        # 创建演示用户
        from ..models.user import User
        db = SessionLocal()
        try:
            # 检查demo_user是否已存在（使用固定的UUID）
            demo_user_id = "00000000-0000-0000-0000-000000000001"
            demo_user = db.query(User).filter(User.id == demo_user_id).first()
            if not demo_user:
                # 创建演示用户
                demo_user = User(
                    id=demo_user_id,
                    phone="13800138000",
                    nickname="演示用户",
                    avatar_url="",
                    bio="用于前端演示的用户",
                    roles=["admin"]
                )
                db.add(demo_user)
                db.commit()
                logging.info("Demo user created successfully")
        except Exception as e:
            logging.error(f"Failed to create demo user: {e}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        raise


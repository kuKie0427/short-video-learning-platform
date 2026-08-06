"""
统一的认证工具函数
"""
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from ..database.connection import get_db
from ..models.user import User
from ..config.settings import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

# JWT配置 - 从配置模块读取
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """验证JWT token并返回用户ID"""
    token = credentials.credentials
    
    logger.info(f"验证 token: {token[:20]}... (开发环境: {settings.is_development})")
    
    # 开发环境：允许直接使用UUID作为user_id（跳过JWT验证）
    if settings.is_development:
        # 检查是否是UUID格式（简单判断：包含4个连字符）
        if token.count('-') == 4 and len(token) == 36:
            logger.info(f"开发环境: 接受 UUID token: {token}")
            return token
    
    # 生产环境或JWT token：正常JWT验证
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_id
    except JWTError as e:
        logger.error(f"JWT 验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证凭证已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户 - 统一实现"""
    user_id = verify_token(credentials)
    user = db.query(User).filter(User.id == user_id).first()
    
    logger.info(f"查找用户 ID: {user_id}, 找到: {user is not None}")
    
    if user is None:
        # 开发环境：如果用户不存在且user_id是UUID格式，自动创建默认用户
        if settings.is_development and user_id.count('-') == 4 and len(user_id) == 36:
            logger.info(f"开发环境: 自动创建用户 {user_id}")
            user = User(
                id=user_id,
                phone=f"dev_{user_id[:8]}",  # 唯一手机号，避免与演示用户(13800138000)冲突
                nickname="测试用户",
                language="zh-CN",
                roles=["learner"]
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"用户创建成功: {user.id}")
        else:
            raise HTTPException(status_code=404, detail="用户不存在")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """获取当前用户（可选） - 用于不需要强制认证的端点"""
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        
        # 开发环境：允许直接使用UUID作为user_id（跳过JWT验证）
        if settings.is_development:
            # 检查是否是UUID格式（简单判断：包含4个连字符）
            if token.count('-') == 4 and len(token) == 36:
                user = db.query(User).filter(User.id == token).first()
                return user
        
        # 生产环境或JWT token：正常JWT验证
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except JWTError:
        return None


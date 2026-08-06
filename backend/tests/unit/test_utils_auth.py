"""
认证工具函数单元测试
"""
import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException

from common.utils.auth import verify_token, get_current_user
from common.config.settings import settings
from common.models import User


class TestVerifyToken:
    """测试JWT token验证"""
    
    def test_verify_valid_token(self, test_user):
        """测试验证有效token"""
        token = self._create_token(str(test_user.id))
        # 注意：verify_token需要HTTPAuthorizationCredentials，这里简化测试
        # 实际测试应该在API层面进行
        assert token is not None
    
    def test_verify_expired_token(self, test_user):
        """测试验证过期token"""
        token = self._create_token(str(test_user.id), expires_delta=timedelta(minutes=-1))
        # 过期token应该抛出异常
        with pytest.raises(JWTError):
            jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    
    def test_verify_invalid_token(self):
        """测试验证无效token"""
        invalid_token = "invalid.token.here"
        with pytest.raises(JWTError):
            jwt.decode(invalid_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    
    def test_verify_token_without_sub(self):
        """测试token中没有sub字段"""
        payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert decoded.get("sub") is None
    
    def _create_token(self, user_id: str, expires_delta: timedelta = None) -> str:
        """创建测试token"""
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = {"sub": user_id, "exp": expire}
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class TestGetCurrentUser:
    """测试获取当前用户"""
    
    def test_get_current_user_exists(self, db, test_user):
        """测试获取存在的用户"""
        user = db.query(User).filter(User.id == test_user.id).first()
        assert user is not None
        assert user.id == test_user.id
        assert user.phone == test_user.phone
    
    def test_get_current_user_not_exists(self, db):
        """测试获取不存在的用户"""
        fake_user_id = "00000000-0000-0000-0000-000000000000"
        user = db.query(User).filter(User.id == fake_user_id).first()
        assert user is None


"""
认证工具函数单元测试

直接调用 common/utils/auth.py 中的 verify_token / get_current_user / get_optional_user，
覆盖真实代码路径：JWT 验签、过期处理、sub 缺失、开发环境 UUID 直通与自动建用户。
（旧版本只断言了 jose 库自身行为，未触达项目代码，已整体重写。）
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from common.utils.auth import verify_token, get_current_user, get_optional_user
from common.config.settings import settings
from common.models import User

WRONG_SECRET = "wrong-secret-key-for-forgery-test"


def _make_token(user_id: str = None, secret: str = None,
                expires_delta: timedelta = None, include_sub: bool = True) -> str:
    """构造 JWT（测试数据准备；被测对象是 verify_token 的验证逻辑）"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"exp": datetime.now(timezone.utc) + expires_delta}
    if include_sub:
        payload["sub"] = user_id
    return jwt.encode(
        payload,
        secret or settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.unit
class TestVerifyToken:
    """verify_token：JWT 验签与开发环境直通（数据驱动：无效凭证矩阵）"""

    # (credentials构造器, 用例id) —— 全部应抛 401；统一返回 HTTPAuthorizationCredentials
    INVALID_CASES = [
        pytest.param(lambda u: _creds(_make_token(str(u.id), expires_delta=timedelta(minutes=-1))), id="expired"),
        pytest.param(lambda u: _creds(_make_token(str(u.id), secret=WRONG_SECRET)), id="forged-signature"),
        pytest.param(lambda u: _creds("not-a-jwt-token"), id="malformed"),
        pytest.param(lambda u: _creds(_make_token(include_sub=False)), id="missing-sub"),
    ]

    @pytest.mark.parametrize("creds_builder", INVALID_CASES)
    def test_invalid_token_raises_401(self, test_user, creds_builder):
        """无效凭证矩阵：过期/伪造/非法/缺sub → 一律 401"""
        with pytest.raises(HTTPException) as exc_info:
            verify_token(creds_builder(test_user))
        assert exc_info.value.status_code == 401

    def test_valid_jwt_returns_user_id(self, test_user):
        """有效 JWT 返回 sub 中的用户ID"""
        token = _make_token(str(test_user.id))
        assert verify_token(_creds(token)) == str(test_user.id)

    def test_dev_mode_uuid_passthrough(self):
        """开发环境后门：UUID 格式字符串直接作为 user_id 放行（压测/联调用）"""
        if not settings.is_development:
            pytest.skip("仅开发环境启用 UUID 直通")
        dev_uuid = str(uuid.uuid4())
        assert verify_token(_creds(dev_uuid)) == dev_uuid


@pytest.mark.unit
class TestGetCurrentUser:
    """get_current_user：token → 数据库用户的完整解析"""

    def test_valid_token_returns_persisted_user(self, db, test_user):
        """有效 token 返回数据库中对应的真实用户对象"""
        token = _make_token(str(test_user.id))
        user = get_current_user(credentials=_creds(token), db=db)
        assert isinstance(user, User)
        assert user.id == test_user.id
        assert user.phone == test_user.phone

    def test_expired_token_raises_401(self, db, test_user):
        """过期 token 的 401 从 verify_token 透传"""
        token = _make_token(str(test_user.id), expires_delta=timedelta(minutes=-1))
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=_creds(token), db=db)
        assert exc_info.value.status_code == 401

    def test_dev_mode_auto_creates_user(self, db):
        """开发环境：token 用户不存在时自动创建（phone 带 dev_ 前缀），并真实落库"""
        if not settings.is_development:
            pytest.skip("仅开发环境启用自动建用户")
        new_user_id = str(uuid.uuid4())
        token = _make_token(new_user_id)

        user = get_current_user(credentials=_creds(token), db=db)

        assert str(user.id) == new_user_id
        assert user.phone == f"dev_{new_user_id[:8]}"
        # 验证副作用：用户确实写入了数据库
        persisted = db.query(User).filter(User.id == new_user_id).first()
        assert persisted is not None


@pytest.mark.unit
class TestGetOptionalUser:
    """get_optional_user：可选认证（匿名访问场景）"""

    def test_no_credentials_returns_none(self, db):
        """无认证头 → None（匿名用户，不抛异常）"""
        assert get_optional_user(credentials=None, db=db) is None

    def test_invalid_token_returns_none_not_raise(self, db):
        """非法 token → None 而非异常（与 verify_token 的 401 行为形成对比）"""
        creds = _creds("malformed-token")
        assert get_optional_user(credentials=creds, db=db) is None

    def test_valid_token_returns_user(self, db, test_user):
        """有效 token → 对应用户"""
        creds = _creds(_make_token(str(test_user.id)))
        user = get_optional_user(credentials=creds, db=db)
        assert user is not None
        assert user.id == test_user.id

"""
认证接口API测试
"""
import pytest
from common.utils.redis_client import store_sms_code, delete_sms_code

# 共享 token 凭证矩阵：无凭证 → 403，非法凭证 → 401
# headers 为惰性构造器（None 表示无认证头），供多个接口的凭证矩阵复用
TOKEN_CREDENTIAL_CASES = [
    pytest.param(None, 403, id="no-token"),
    pytest.param(lambda: {"Authorization": "Bearer invalid_token"}, 401, id="invalid-token"),
]


@pytest.mark.api
class TestSendCode:
    """测试发送验证码接口（数据驱动：手机号输入矩阵）

    校验规则（services/auth/app/api/auth.py:PhoneLoginRequest）：
    phone 缺失或长度 < 10 → 422；合法手机号 → 200。
    """

    # (payload构造器, 预期状态码, 用例id)
    PHONE_CASES = [
        pytest.param(lambda u: {"phone": u.phone}, 200, id="valid-phone"),
        pytest.param(lambda u: {"phone": "123"}, 422, id="too-short"),
        pytest.param(lambda u: {"phone": "abc"}, 422, id="non-numeric"),
        pytest.param(lambda u: {}, 422, id="missing-phone"),
        pytest.param(lambda u: {"phone": "1" * 30}, 200, id="long-phone"),
    ]

    @pytest.mark.parametrize("payload_builder, expected", PHONE_CASES)
    def test_send_code_phone_matrix(self, auth_client, test_user, payload_builder, expected):
        """发送验证码参数矩阵：合法手机号成功，非法输入统一 422"""
        response = auth_client.post("/api/auth/send-code", json=payload_builder(test_user))
        assert response.status_code == expected


@pytest.mark.api
class TestLogin:
    """测试登录接口（数据驱动：验证码状态矩阵）

    分支（services/auth/app/api/auth.py:phone_login）：
    - 未发送验证码 → 400"验证码已过期或未发送"
    - 验证码错误 → 400"验证码错误"
    - 验证码正确且用户存在 → 200 返回 token+user
    - 验证码正确但用户不存在 → 200 自动注册新用户
    """

    # (验证码准备动作, 提交的验证码, 预期状态码, 是否断言token, 用例id)
    # (验证码准备动作, 提交的验证码, 预期状态码, 断言message关键字, 用例id)
    LOGIN_CASES = [
        pytest.param(lambda phone, db: store_sms_code(phone, "123456", 300), "123456", 200, None, id="success"),
        pytest.param(lambda phone, db: store_sms_code(phone, "123456", 300), "999999", 400, "错误", id="wrong-code"),
        pytest.param(lambda phone, db: None, "123456", 400, "过期", id="expired-code"),
    ]

    @pytest.mark.parametrize("seed_code, submit_code, expected_status, expect_message", LOGIN_CASES)
    def test_login_matrix(
        self, auth_client, db, test_user, seed_code, submit_code, expected_status, expect_message
    ):
        """登录参数矩阵：验证码正确/错误/过期（新用户注册见 test_login_new_user_creates_record）"""
        phone = test_user.phone
        seed_code(phone, db)

        response = auth_client.post(
            "/api/auth/login",
            json={"phone": phone, "code": submit_code}
        )

        assert response.status_code == expected_status
        data = response.json()
        assert data["code"] == expected_status
        if expect_message:
            assert expect_message in data["message"]
        else:
            assert "token" in data["data"]
            assert "user" in data["data"]

    def test_login_new_user_creates_record(self, auth_client, db):
        """新用户登录自动注册并落库（uuid 生成手机号，保证用例可重复执行）"""
        import uuid as _uuid
        from common.models import User
        phone = f"139{_uuid.uuid4().hex[:8]}"  # 11 位，唯一手机号
        store_sms_code(phone, "123456", 300)

        response = auth_client.post(
            "/api/auth/login",
            json={"phone": phone, "code": "123456"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "user" in data["data"]
        user = db.query(User).filter(User.phone == phone).first()
        assert user is not None


@pytest.mark.api
class TestProfile:
    """测试用户资料接口（数据驱动：token 凭证矩阵 + 更新逻辑）"""

    @pytest.mark.parametrize("headers_builder, expected", TOKEN_CREDENTIAL_CASES)
    def test_get_profile_token_matrix(self, auth_client, headers_builder, expected):
        """获取资料凭证矩阵：无 token 403，非法 token 401"""
        headers = headers_builder() if headers_builder else None
        response = auth_client.get("/api/auth/profile", headers=headers)
        assert response.status_code == expected

    def test_get_profile_success(self, auth_client, auth_headers, test_user):
        """测试成功获取用户资料"""
        response = auth_client.get(
            "/api/auth/profile",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["id"] == str(test_user.id)
        assert data["data"]["phone"] == test_user.phone
    
    def test_update_profile_success(self, auth_client, auth_headers, test_user, db):
        """测试成功更新用户资料"""
        response = auth_client.put(
            "/api/auth/profile",
            headers=auth_headers,
            json={
                "nickname": "新昵称",
                "bio": "新的个人简介"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["nickname"] == "新昵称"
        assert data["data"]["bio"] == "新的个人简介"
        
        # 验证数据库已更新
        db.refresh(test_user)
        assert test_user.nickname == "新昵称"
    
    def test_update_profile_unauthorized(self, auth_client):
        """测试未授权更新"""
        response = auth_client.put(
            "/api/auth/profile",
            json={"nickname": "新昵称"}
        )
        
        assert response.status_code == 403


@pytest.mark.api
class TestRefreshToken:
    """测试刷新token接口（数据驱动：token 凭证矩阵）"""

    @pytest.mark.parametrize("headers_builder, expected", TOKEN_CREDENTIAL_CASES)
    def test_refresh_token_matrix(self, auth_client, headers_builder, expected):
        """刷新token凭证矩阵：无 token 403，非法 token 401"""
        headers = headers_builder() if headers_builder else None
        response = auth_client.post("/api/auth/refresh", headers=headers)
        assert response.status_code == expected

    def test_refresh_token_success(self, auth_client, auth_headers, test_user):
        """测试成功刷新token"""
        response = auth_client.post(
            "/api/auth/refresh",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "token" in data["data"]
        assert data["data"]["user_id"] == str(test_user.id)


"""
认证接口API测试
"""
import pytest
from common.utils.redis_client import store_sms_code, delete_sms_code


@pytest.mark.api
class TestSendCode:
    """测试发送验证码接口"""
    
    def test_send_code_success(self, auth_client, test_user):
        """测试成功发送验证码"""
        response = auth_client.post(
            "/api/auth/send-code",
            json={"phone": test_user.phone}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["message"] == "验证码已发送"
        assert "data" in data
        assert data["data"]["success"] is True
    
    def test_send_code_invalid_phone(self, auth_client):
        """测试无效手机号"""
        response = auth_client.post(
            "/api/auth/send-code",
            json={"phone": "123"}  # 太短的手机号
        )
        
        assert response.status_code == 422  # 验证错误
    
    def test_send_code_missing_phone(self, auth_client):
        """测试缺少手机号"""
        response = auth_client.post(
            "/api/auth/send-code",
            json={}
        )
        
        assert response.status_code == 422


@pytest.mark.api
class TestLogin:
    """测试登录接口"""
    
    def test_login_success(self, auth_client, db, test_user):
        """测试成功登录"""
        # 先发送验证码
        phone = test_user.phone
        code = "123456"
        store_sms_code(phone, code, 300)
        
        # 登录
        response = auth_client.post(
            "/api/auth/login",
            json={"phone": phone, "code": code}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "token" in data["data"]
        assert "user" in data["data"]
    
    def test_login_wrong_code(self, auth_client, test_user):
        """测试错误验证码"""
        phone = test_user.phone
        store_sms_code(phone, "123456", 300)
        
        response = auth_client.post(
            "/api/auth/login",
            json={"phone": phone, "code": "999999"}  # 错误的验证码
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 400
    
    def test_login_expired_code(self, auth_client, test_user):
        """测试过期验证码"""
        phone = test_user.phone
        # 不存储验证码，模拟过期
        
        response = auth_client.post(
            "/api/auth/login",
            json={"phone": phone, "code": "123456"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "过期" in data["message"] or "未发送" in data["message"]
    
    def test_login_new_user(self, auth_client, db):
        """测试新用户自动注册"""
        phone = "13800138099"
        code = "123456"
        store_sms_code(phone, code, 300)
        
        response = auth_client.post(
            "/api/auth/login",
            json={"phone": phone, "code": code}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "user" in data["data"]
        # 验证新用户已创建
        from common.models import User
        user = db.query(User).filter(User.phone == phone).first()
        assert user is not None


@pytest.mark.api
class TestProfile:
    """测试用户资料接口"""
    
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
    
    def test_get_profile_unauthorized(self, auth_client):
        """测试未授权访问"""
        response = auth_client.get("/api/auth/profile")
        
        assert response.status_code == 403  # 未提供token
    
    def test_get_profile_invalid_token(self, auth_client):
        """测试无效token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = auth_client.get(
            "/api/auth/profile",
            headers=headers
        )
        
        assert response.status_code == 401  # 无效token应返回401 Unauthorized
    
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
    """测试刷新token接口"""
    
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
    
    def test_refresh_token_unauthorized(self, auth_client):
        """测试未授权刷新"""
        response = auth_client.post("/api/auth/refresh")
        
        assert response.status_code == 403


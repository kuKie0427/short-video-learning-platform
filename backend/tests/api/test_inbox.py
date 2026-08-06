"""
消息通知接口API测试
"""
import pytest


@pytest.mark.api
class TestGetMessages:
    """测试获取消息列表"""
    
    def test_get_messages_success(self, notification_client, auth_headers):
        """测试成功获取消息列表"""
        response = notification_client.get(
            "/api/inbox/messages",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert isinstance(data["data"]["items"], list)
        assert "pagination" in data["data"]
    
    def test_get_messages_unauthorized(self, notification_client):
        """测试未授权获取消息"""
        response = notification_client.get("/api/inbox/messages")
        
        assert response.status_code == 403
    
    def test_get_messages_with_pagination(self, notification_client, auth_headers):
        """测试分页获取消息"""
        response = notification_client.get(
            "/api/inbox/messages?page=1&page_size=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


@pytest.mark.api
class TestMarkRead:
    """测试标记消息已读"""
    
    def test_mark_read_success(self, notification_client, auth_headers, db, test_user):
        """测试成功标记已读"""
        # 创建一条消息
        from common.models import Notification
        notification = Notification(
            user_id=test_user.id,
            type="like",
            title="测试消息",
            content="这是一条测试消息",
            is_read=False
        )
        db.add(notification)
        db.commit()
        
        response = notification_client.post(
            "/api/inbox/read",
            headers=auth_headers,
            json={"message_ids": [str(notification.id)]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_mark_read_unauthorized(self, notification_client):
        """测试未授权标记已读"""
        response = notification_client.post(
            "/api/inbox/read",
            json={"message_ids": ["123"]}
        )
        
        assert response.status_code == 403


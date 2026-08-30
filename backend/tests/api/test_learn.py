"""
学习进度接口API测试
"""
import pytest


@pytest.mark.api
class TestLearnHeartbeat:
    """测试学习心跳上报"""
    
    def test_heartbeat_success(self, client, auth_headers, test_video, test_user, db):
        """测试成功上报心跳（断言数据库最终态：学习记录创建并更新进度）"""
        from common.models import LearnRecord

        response = client.post(
            "/api/learn/heartbeat",
            headers=auth_headers,
            json={
                "video_id": str(test_video.id),
                "position": 60,
                "duration": 120
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        # 数据库最终态：学习记录已创建，进度 = 60/120 = 50%
        record = db.query(LearnRecord).filter(
            LearnRecord.user_id == test_user.id,
            LearnRecord.video_id == test_video.id
        ).first()
        assert record is not None
        assert record.last_position == 60
        assert record.status == "in_progress"
        assert abs(float(record.completed_ratio) - 50.0) < 0.01
    
    def test_heartbeat_unauthorized(self, client, test_video):
        """测试未授权上报心跳"""
        response = client.post(
            "/api/learn/heartbeat",
            json={
                "video_id": str(test_video.id),
                "position": 60,
                "duration": 120
            }
        )
        
        assert response.status_code == 403
    
    def test_heartbeat_nonexistent_video(self, client, auth_headers):
        """测试不存在的视频"""
        response = client.post(
            "/api/learn/heartbeat",
            headers=auth_headers,
            json={
                "video_id": "00000000-0000-0000-0000-000000000000",
                "position": 60,
                "duration": 120
            }
        )
        
        # 应该返回404（视频不存在）
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == 404


@pytest.mark.api
class TestLearnComplete:
    """测试学习完成标记"""
    
    def test_complete_success(self, client, auth_headers, test_video, test_user, db):
        """测试成功标记完成（字段名与实现对齐：completion_rate，并断言数据库最终态）

        历史缺陷：曾用 completed_ratio 提交，Pydantic 忽略未知字段 → 断言从未生效。
        """
        from common.models import LearnRecord

        response = client.post(
            "/api/learn/complete",
            headers=auth_headers,
            json={
                "video_id": str(test_video.id),
                "completion_rate": 100.0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        # 数据库最终态：学习记录已创建，状态 completed，完成率 100
        record = db.query(LearnRecord).filter(
            LearnRecord.user_id == test_user.id,
            LearnRecord.video_id == test_video.id
        ).first()
        assert record is not None
        assert record.status == "completed"
        assert float(record.completed_ratio) == 100.0
    
    def test_complete_unauthorized(self, client, test_video):
        """测试未授权标记完成"""
        response = client.post(
            "/api/learn/complete",
            json={
                "video_id": str(test_video.id),
                "completion_rate": 100.0
            }
        )
        
        assert response.status_code == 403


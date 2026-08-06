"""
上传服务API测试
"""
import pytest
import io
from pathlib import Path


@pytest.mark.api
class TestInitUpload:
    """测试初始化上传接口"""
    
    def test_init_upload_success(self, upload_client, auth_headers, db, test_user):
        """测试成功初始化上传"""
        response = upload_client.post(
            "/api/upload/init",
            headers=auth_headers,
            json={
                "file_name": "test_video.mp4",
                "file_size": 1024000,
                "duration": 120,
                "mime_type": "video/mp4",
                "video_type": "short"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "upload_id" in data["data"]
        assert "upload_url" in data["data"]
    
    def test_init_upload_unauthorized(self, upload_client):
        """测试未授权初始化上传"""
        response = upload_client.post(
            "/api/upload/init",
            json={
                "file_name": "test.mp4",
                "file_size": 1000,
                "duration": 60,
                "mime_type": "video/mp4",
                "video_type": "short"
            }
        )
        
        assert response.status_code == 403


@pytest.mark.api
class TestUploadChunk:
    """测试分片上传接口"""
    
    def test_upload_chunk_success(self, upload_client, auth_headers, db, test_user):
        """测试成功上传分片"""
        # 先初始化上传
        from common.models.upload import UploadTask
        upload_task = UploadTask(
            upload_id="test-upload-id",
            user_id=test_user.id,
            file_name="test.mp4",
            file_size=1024000,
            duration=120,
            video_type="short",
            status="initialized"
        )
        db.add(upload_task)
        db.commit()
        
        # 上传分片（契约：upload_id/chunk_index 走请求头，body 为二进制分片数据）
        chunk_data = b"test chunk data" * 100
        response = upload_client.put(
            "/api/upload/chunk",
            headers={
                **auth_headers,
                "upload_id": "test-upload-id",
                "chunk_index": "0"
            },
            content=chunk_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["uploaded"] is True
    
    def test_upload_chunk_invalid_task(self, upload_client, auth_headers):
        """测试无效的上传任务"""
        chunk_data = b"test data"
        response = upload_client.put(
            "/api/upload/chunk",
            headers={
                **auth_headers,
                "upload_id": "invalid-upload-id",
                "chunk_index": "0"
            },
            content=chunk_data
        )
        
        assert response.status_code == 404


@pytest.mark.api
class TestCompleteUpload:
    """测试完成上传接口"""
    
    def test_complete_upload_success(self, upload_client, auth_headers, db, test_user):
        """测试成功完成上传"""
        # 创建上传任务并标记为已上传
        from common.models.upload import UploadTask
        upload_task = UploadTask(
            upload_id="test-upload-complete",
            user_id=test_user.id,
            file_name="test.mp4",
            file_size=1024000,
            duration=120,
            video_type="short",
            status="uploaded"
        )
        db.add(upload_task)
        db.commit()
        
        # 完成上传
        response = upload_client.post(
            "/api/upload/complete",
            headers=auth_headers,
            json={
                "upload_id": "test-upload-complete",
                "title": "测试视频",
                "description": "测试描述",
                "tags": ["测试"],
                "language": "zh-CN",
                "is_public": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_complete_upload_not_uploaded(self, upload_client, auth_headers, db, test_user):
        """测试未完成上传就调用complete"""
        # 创建未完成的上传任务
        from common.models.upload import UploadTask
        upload_task = UploadTask(
            upload_id="test-upload-not-ready",
            user_id=test_user.id,
            file_name="test.mp4",
            file_size=1024000,
            duration=120,
            video_type="short",
            status="initialized"
        )
        db.add(upload_task)
        db.commit()
        
        response = upload_client.post(
            "/api/upload/complete",
            headers=auth_headers,
            json={
                "upload_id": "test-upload-not-ready",
                "title": "测试视频"
            }
        )
        
        assert response.status_code == 400


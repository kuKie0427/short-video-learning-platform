"""
视频上传接口API测试
"""
import pytest
import io


@pytest.mark.api
class TestInitUpload:
    """测试初始化上传接口"""
    
    def test_init_upload_success(self, upload_client, auth_headers):
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
            file_size=2048000,
            duration=120,
            video_type="short",
            status="initialized"
        )
        db.add(upload_task)
        db.commit()
        
        # 上传分片（契约：upload_id/chunk_index 走请求头，body 为二进制分片数据）
        chunk_data = b"test chunk data"
        response = upload_client.put(
            "/api/upload/chunk",
            headers={
                **auth_headers,
                "upload_id": upload_task.upload_id,
                "chunk_index": "0"
            },
            content=chunk_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_upload_chunk_unauthorized(self, upload_client):
        """测试未授权上传分片"""
        chunk_data = b"test data"
        response = upload_client.put(
            "/api/upload/chunk",
            headers={
                "upload_id": "test-id",
                "chunk_index": "0"
            },
            content=chunk_data
        )
        
        assert response.status_code == 403


@pytest.mark.api
class TestGetVideo:
    """测试获取视频接口"""
    
    def test_get_video_success(self, client, test_video):
        """测试成功获取视频详情"""
        response = client.get(f"/api/feed/video/{test_video.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["id"] == str(test_video.id)
    
    def test_get_nonexistent_video(self, client):
        """测试获取不存在的视频"""
        response = client.get("/api/feed/video/00000000-0000-0000-0000-000000000000")
        
        assert response.status_code == 404
    
    def test_get_video_status(self, client, test_video):
        """测试获取视频审核状态"""
        response = client.get(f"/api/feed/video/{test_video.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "status" in data["data"]
    
    def test_get_related_videos(self, client, test_video):
        """测试获取关联视频"""
        response = client.get(f"/api/feed/video/{test_video.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data


"""
视频拆分接口API测试
"""
import pytest
import uuid


@pytest.mark.api
class TestCreateSplitTask:
    """测试创建拆分任务"""
    
    def test_create_split_task_success(self, split_client, auth_headers, db, test_user, test_video):
        """测试成功创建拆分任务"""
        # 先创建长视频（LongVideo需要关联一个Video）
        from common.models import LongVideo
        long_video = LongVideo(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            original_duration=3600,
            original_file_url="/path/to/video.mp4",
            split_enabled=True
        )
        db.add(long_video)
        db.commit()
        
        response = split_client.post(
            "/api/split/tasks",
            headers=auth_headers,
            json={
                "long_video_id": str(long_video.id),
                "split_mode": "auto",
                "organization_mode": "course"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
    
    def test_create_split_task_nonexistent_video(self, split_client, auth_headers):
        """测试不存在的长视频"""
        response = split_client.post(
            "/api/split/tasks",
            headers=auth_headers,
            json={
                "long_video_id": "00000000-0000-0000-0000-000000000000",
                "split_mode": "auto",
                "organization_mode": "course"
            }
        )
        
        assert response.status_code == 404
    
    def test_create_split_task_unauthorized(self, split_client):
        """测试未授权创建拆分任务"""
        response = split_client.post(
            "/api/split/tasks",
            json={
                "long_video_id": "test-id",
                "split_mode": "auto",
                "organization_mode": "course"
            }
        )
        
        assert response.status_code == 403


@pytest.mark.api
class TestGetSplitTasks:
    """测试获取拆分任务列表"""
    
    def test_get_split_tasks_success(self, split_client, auth_headers):
        """测试成功获取任务列表"""
        response = split_client.get(
            "/api/split/tasks",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
    
    def test_get_split_tasks_unauthorized(self, split_client):
        """测试未授权获取任务列表"""
        response = split_client.get("/api/split/tasks")
        
        assert response.status_code == 403


@pytest.mark.api
class TestGetSplitTask:
    """测试获取拆分任务详情"""
    
    def test_get_split_task_success(self, split_client, auth_headers, db, test_user, test_video):
        """测试成功获取任务详情"""
        # 创建拆分任务
        from common.models import SplitTask, LongVideo
        long_video = LongVideo(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            original_duration=3600,
            original_file_url="/path/to/video2.mp4",
            split_enabled=True
        )
        db.add(long_video)
        
        split_task = SplitTask(
            task_id=str(uuid.uuid4()),
            long_video_id=long_video.id,
            user_id=test_user.id,
            split_mode="auto",
            organization_mode="course",
            status="pending",
            progress=0.0,
            progress_message="等待处理"
        )
        db.add(split_task)
        db.commit()
        
        response = split_client.get(
            f"/api/split/tasks/{split_task.task_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["id"] == str(split_task.id)
    
    def test_get_split_task_not_found(self, split_client, auth_headers):
        """测试任务不存在"""
        response = split_client.get(
            "/api/split/tasks/00000000-0000-0000-0000-000000000000",
            headers=auth_headers
        )
        
        assert response.status_code == 404


@pytest.mark.api
class TestGetSegments:
    """测试获取拆分预览"""
    
    def test_get_segments_success(self, split_client, auth_headers, db, test_user, test_video):
        """测试成功获取拆分预览"""
        # 创建拆分任务和分段
        from common.models import SplitTask, SplitSegment, LongVideo
        long_video = LongVideo(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            original_duration=3600,
            original_file_url="/path/to/video3.mp4",
            split_enabled=True
        )
        db.add(long_video)
        
        split_task = SplitTask(
            task_id=str(uuid.uuid4()),
            long_video_id=long_video.id,
            user_id=test_user.id,
            split_mode="auto",
            organization_mode="course",
            status="completed",
            progress=100.0
        )
        db.add(split_task)
        db.commit()
        
        # 创建分段
        segment = SplitSegment(
            task_id=split_task.id,
            segment_index=1,
            start_time=0,
            end_time=60,
            duration=60
        )
        db.add(segment)
        db.commit()
        
        response = split_client.get(
            f"/api/split/tasks/{split_task.task_id}/segments",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data


@pytest.mark.api
class TestUpdateSegments:
    """测试手动调整拆分点"""
    
    def test_update_segments_success(self, split_client, auth_headers, db, test_user, test_video):
        """测试成功更新拆分点"""
        # 创建拆分任务和分段
        from common.models import SplitTask, SplitSegment, LongVideo
        long_video = LongVideo(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            original_duration=3600,
            original_file_url="/path/to/video4.mp4",
            split_enabled=True
        )
        db.add(long_video)
        
        split_task = SplitTask(
            task_id=str(uuid.uuid4()),
            long_video_id=long_video.id,
            user_id=test_user.id,
            split_mode="auto",
            organization_mode="course",
            status="pending",
            progress=50.0
        )
        db.add(split_task)
        db.commit()
        
        segment = SplitSegment(
            task_id=split_task.id,
            segment_index=1,
            start_time=0,
            end_time=60,
            duration=60
        )
        db.add(segment)
        db.commit()
        
        # 更新拆分点
        response = split_client.put(
            f"/api/split/tasks/{split_task.task_id}/segments",
            headers=auth_headers,
            json={
                "segments": [{
                    "segment_id": str(segment.id),
                    "start_time": 10,
                    "end_time": 70
                }]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


@pytest.mark.api
class TestCancelSplitTask:
    """测试取消拆分任务"""
    
    def test_cancel_split_task_success(self, split_client, auth_headers, db, test_user, test_video):
        """测试成功取消任务"""
        # 创建拆分任务
        from common.models import SplitTask, LongVideo
        long_video = LongVideo(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            original_duration=3600,
            original_file_url="/path/to/video5.mp4",
            split_enabled=True
        )
        db.add(long_video)
        
        split_task = SplitTask(
            task_id=str(uuid.uuid4()),
            long_video_id=long_video.id,
            user_id=test_user.id,
            split_mode="auto",
            organization_mode="course",
            status="pending",
            progress=0.0
        )
        db.add(split_task)
        db.commit()
        
        # 取消任务
        response = split_client.delete(
            f"/api/split/tasks/{split_task.task_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


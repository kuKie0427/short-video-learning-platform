"""
视频拆分接口API测试
"""
import pytest
import uuid


def _make_long_video(db, video, url="/path/to/video.mp4"):
    """为已存在的 Video 创建 LongVideo 记录（消除 7 处重复构造样板）"""
    from common.models import LongVideo
    long_video = LongVideo(
        id=str(uuid.uuid4()),
        video_id=video.id,
        original_duration=3600,
        original_file_url=url,
        split_enabled=True
    )
    db.add(long_video)
    db.commit()
    return long_video


@pytest.mark.api
class TestCreateSplitTask:
    """测试创建拆分任务"""
    
    def test_create_split_task_success(self, split_client, auth_headers, db, test_user, test_video, monkeypatch):
        """测试成功创建拆分任务

        注：patch 掉 celery send_task——测试环境无 Redis broker，真实 send_task 会同步
        重试阻塞约 19s（回归速度黑洞）；任务入队本身不是本用例的断言对象，
        断言对象是"任务创建 + 状态落库为 queued"。
        """
        from common.models import LongVideo, SplitTask
        # patch celery send_task：不真发消息，记录调用即可
        from services.split.app.api.split import celery_app
        sent = []
        monkeypatch.setattr(celery_app, "send_task", lambda *a, **kw: sent.append((a, kw)) or None)

        long_video = _make_long_video(db, test_video, "/path/to/video.mp4")

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
        # 任务确已入队且状态落库为 queued（数据库最终态断言）
        assert len(sent) == 1
        task_id = data["data"]["id"]
        task = db.query(SplitTask).filter(SplitTask.id == task_id).first()
        assert task is not None
        assert task.status == "queued"
    
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

    def test_get_split_tasks_includes_video_id(self, split_client, auth_headers, db, test_user, test_video):
        """【回归】任务列表返回 video_id：前端切分列表页按视频关联任务状态

        原缺陷：/api/split/tasks 返回的任务缺少 video_id 字段，
        前端无法把历史任务状态关联到视频列表（任务状态跨会话不可见）。
        修复：任务序列化时经 task.long_video 关联取 video_id。
        """
        from common.models import LongVideo, SplitTask
        long_video = _make_long_video(db, test_video, "/path/to/video.mp4")

        task = SplitTask(
            id=str(uuid.uuid4()),
            task_id=f"split_{uuid.uuid4().hex[:8]}",
            long_video_id=long_video.id,
            user_id=test_user.id,
            split_mode="auto",
            organization_mode="course",
            status="pending",
            progress=0.0
        )
        db.add(task)
        db.commit()

        response = split_client.get("/api/split/tasks", headers=auth_headers)
        assert response.status_code == 200
        tasks = response.json()["data"]
        assert any(
            t["task_id"] == task.task_id and t["video_id"] == str(test_video.id)
            for t in tasks
        ), "任务列表应包含 video_id 且与关联视频一致"

    def test_get_split_tasks_user_isolation(self, split_client, auth_headers, auth_headers_user2, db, test_user, test_user2, test_video):
        """权限隔离：其他用户的任务不出现在我的列表"""
        from common.models import LongVideo, SplitTask
        long_video = _make_long_video(db, test_video, "/path/to/video.mp4")

        other_task = SplitTask(
            id=str(uuid.uuid4()),
            task_id=f"split_{uuid.uuid4().hex[:8]}",
            long_video_id=long_video.id,
            user_id=test_user2.id,  # 其他用户的任务
            split_mode="auto",
            organization_mode="course",
            status="completed",
            progress=100.0
        )
        db.add(other_task)
        db.commit()

        response = split_client.get("/api/split/tasks", headers=auth_headers)
        tasks = response.json()["data"]
        assert all(
            t["task_id"] != other_task.task_id for t in tasks
        ), "列表不应包含其他用户的任务"


@pytest.mark.api
class TestGetSplitTask:
    """测试获取拆分任务详情"""
    
    def test_get_split_task_success(self, split_client, auth_headers, db, test_user, test_video):
        """测试成功获取任务详情"""
        # 创建拆分任务
        from common.models import SplitTask, LongVideo
        long_video = _make_long_video(db, test_video, "/path/to/video2.mp4")
        
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
        long_video = _make_long_video(db, test_video, "/path/to/video3.mp4")
        
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
        long_video = _make_long_video(db, test_video, "/path/to/video4.mp4")
        
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
        long_video = _make_long_video(db, test_video, "/path/to/video5.mp4")
        
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


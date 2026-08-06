"""
Split 服务核心业务 handler 测试

覆盖 analyze（智能分析）、publish-segments（片段发布）、confirm（确认切分结果）:
- analyze：无视频文件走示例数据降级、权限校验、ID 格式校验
- publish-segments：发布成功（视频状态转 published）、空列表、段不存在、越权
- confirm：确认成功生成短视频、任务未完成、任务不存在
"""
import uuid
import pytest

from common.models import SplitTask, SplitSegment, LongVideo, Video


def _make_long_video(db, test_user, video_type="long", original_url="/nonexistent/video.mp4"):
    """创建长视频 + LongVideo 记录（original_file_url 指向不存在的路径 → analyze 走示例数据）"""
    video = Video(
        id=str(uuid.uuid4()),
        author_id=test_user.id,
        title="测试长视频",
        duration=3600,
        play_url="/videos/long.mp4",
        language="zh-CN",
        status="online",
        video_type=video_type
    )
    db.add(video)
    db.flush()

    long_video = LongVideo(
        id=str(uuid.uuid4()),
        video_id=video.id,
        original_duration=3600,
        original_file_url=original_url,
        split_enabled=True
    )
    db.add(long_video)
    db.commit()
    db.refresh(long_video)
    return long_video


@pytest.mark.api
class TestAnalyzeVideo:
    """智能分析接口"""

    def test_analyze_no_file_uses_sample_data(self, split_client, auth_headers, db, test_user):
        """视频文件不存在时降级为示例知识点（used_fallback=True）"""
        long_video = _make_long_video(db, test_user)

        response = split_client.post(
            "/api/split/analyze",
            headers=auth_headers,
            json={"long_video_id": str(long_video.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["used_fallback"] is True
        assert len(data["data"]["knowledge_points"]) >= 1
        assert data["data"]["knowledge_points"][0]["title"]

    def test_analyze_other_users_video_forbidden(self, split_client, auth_headers, db, test_user2):
        """越权分析他人的视频 → 403"""
        long_video = _make_long_video(db, test_user2)

        response = split_client.post(
            "/api/split/analyze",
            headers=auth_headers,
            json={"long_video_id": str(long_video.id)}
        )

        assert response.status_code == 403

    def test_analyze_invalid_id_format(self, split_client, auth_headers):
        """非 UUID 的 long_video_id → 400"""
        response = split_client.post(
            "/api/split/analyze",
            headers=auth_headers,
            json={"long_video_id": "not-a-uuid"}
        )

        assert response.status_code == 400

    def test_analyze_nonexistent_video(self, split_client, auth_headers):
        """不存在的长视频 → 404"""
        response = split_client.post(
            "/api/split/analyze",
            headers=auth_headers,
            json={"long_video_id": str(uuid.uuid4())}
        )

        assert response.status_code == 404


@pytest.mark.api
class TestPublishSegments:
    """发布分割片段"""

    def _make_task_with_segment(self, db, test_user, long_video, with_video=True):
        """创建拆分任务 + 片段（可选关联视频）"""
        task = SplitTask(
            task_id=str(uuid.uuid4()),
            long_video_id=long_video.id,
            user_id=test_user.id,
            split_mode="auto",
            organization_mode="course",
            status="completed",
            progress=100.0
        )
        db.add(task)
        db.flush()

        segment_video = None
        if with_video:
            segment_video = Video(
                id=str(uuid.uuid4()),
                author_id=test_user.id,
                title="待发布片段",
                duration=60,
                play_url="/videos/seg.mp4",
                language="zh-CN",
                status="transcoding",
                video_type="short",
                parent_video_id=long_video.id  # 外键指向 long_videos.id
            )
            db.add(segment_video)
            db.flush()

        segment = SplitSegment(
            id=str(uuid.uuid4()),
            task_id=task.id,
            segment_index=1,
            start_time=0,
            end_time=60,
            duration=60,
            video_id=segment_video.id if segment_video else None
        )
        db.add(segment)
        db.commit()
        db.refresh(segment)
        return task, segment, segment_video

    def test_publish_success_sets_video_published(self, split_client, auth_headers, db, test_user):
        """发布成功：视频状态更新为 published、video_type 为 short"""
        long_video = _make_long_video(db, test_user)
        task, segment, seg_video = self._make_task_with_segment(db, test_user, long_video)

        response = split_client.post(
            "/api/split/publish-segments",
            headers=auth_headers,
            json={"segment_ids": [str(segment.id)]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["published_count"] == 1

        db.refresh(seg_video)
        assert seg_video.status == "published"
        assert seg_video.video_type == "short"

    def test_publish_empty_segment_ids(self, split_client, auth_headers):
        """空片段列表 → 400"""
        response = split_client.post(
            "/api/split/publish-segments",
            headers=auth_headers,
            json={"segment_ids": []}
        )

        assert response.status_code == 400

    def test_publish_nonexistent_segments(self, split_client, auth_headers):
        """片段不存在 → 404"""
        response = split_client.post(
            "/api/split/publish-segments",
            headers=auth_headers,
            json={"segment_ids": [str(uuid.uuid4())]}
        )

        assert response.status_code == 404

    def test_publish_other_users_segments_forbidden(self, split_client, auth_headers, db, test_user2):
        """发布他人任务的片段 → 403"""
        long_video = _make_long_video(db, test_user2)
        task, segment, _ = self._make_task_with_segment(db, test_user2, long_video)

        response = split_client.post(
            "/api/split/publish-segments",
            headers=auth_headers,
            json={"segment_ids": [str(segment.id)]}
        )

        assert response.status_code == 403


@pytest.mark.api
class TestConfirmSplitResult:
    """确认分割结果"""

    def test_confirm_creates_short_videos(self, split_client, auth_headers, db, test_user):
        """确认成功：为每个片段创建短视频并更新任务状态为 confirmed"""
        long_video = _make_long_video(db, test_user)
        task = SplitTask(
            task_id=str(uuid.uuid4()),
            long_video_id=long_video.id,
            user_id=test_user.id,
            split_mode="auto",
            organization_mode="course",
            status="completed",
            progress=100.0
        )
        db.add(task)
        db.flush()

        segment = SplitSegment(
            id=str(uuid.uuid4()),
            task_id=task.id,
            segment_index=1,
            start_time=0,
            end_time=60,
            duration=60
        )
        db.add(segment)
        db.commit()

        response = split_client.post(
            f"/api/split/tasks/{task.task_id}/confirm",
            headers=auth_headers,
            json=[str(segment.id)]  # segment_ids 为裸数组 body 参数
        )

        assert response.status_code == 200
        # 创建了短视频（status=online, parent 指向长视频）
        video = db.query(Video).filter(Video.parent_video_id == long_video.id).first()
        assert video is not None
        assert video.status == "online"
        assert video.video_type == "short"

        db.refresh(task)
        assert task.status == "confirmed"

    def test_confirm_task_not_completed(self, split_client, auth_headers, db, test_user):
        """任务未完成时确认 → 400"""
        long_video = _make_long_video(db, test_user)
        task = SplitTask(
            task_id=str(uuid.uuid4()),
            long_video_id=long_video.id,
            user_id=test_user.id,
            split_mode="auto",
            organization_mode="course",
            status="pending",
            progress=0.0
        )
        db.add(task)
        db.commit()

        response = split_client.post(
            f"/api/split/tasks/{task.task_id}/confirm",
            headers=auth_headers,
            json=[str(uuid.uuid4())]
        )

        assert response.status_code == 400

    def test_confirm_task_not_found(self, split_client, auth_headers):
        """任务不存在 → 404"""
        response = split_client.post(
            "/api/split/tasks/00000000-0000-0000-0000-000000000000/confirm",
            headers=auth_headers,
            json=[str(uuid.uuid4())]
        )

        assert response.status_code == 404

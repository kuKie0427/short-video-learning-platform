"""
Split 服务高级 handler 测试

- direct-split：基于已有知识点直接切分（mock ffmpeg 切分器，验证任务状态流转、
  路径转换、Video/SplitSegment 创建、失败回滚为 failed）
- simple-split：演示用简化分割（验证 demo 用户自动创建、video 不存在 404）
"""
import uuid
import pytest

from common.models import SplitTask, SplitSegment, LongVideo, Video, User

DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"


def _make_long_video(db, test_user):
    video = Video(
        id=str(uuid.uuid4()),
        author_id=test_user.id,
        title="待切分视频",
        duration=3600,
        play_url="/uploads/videos/long.mp4",
        language="zh-CN",
        status="online",
        video_type="long"
    )
    db.add(video)
    db.flush()

    long_video = LongVideo(
        id=str(uuid.uuid4()),
        video_id=video.id,
        original_duration=3600,
        original_file_url="/uploads/videos/long.mp4",
        split_enabled=True
    )
    db.add(long_video)
    db.commit()
    db.refresh(long_video)
    return long_video, video


def _knowledge_points(n=3):
    return [
        {
            "id": i,
            "title": f"知识点{i}",
            "start_time": (i - 1) * 60,
            "end_time": i * 60,
            "duration": 60,
        }
        for i in range(1, n + 1)
    ]


@pytest.mark.api
class TestDirectSplit:
    """直接切分接口"""

    def test_direct_split_success_creates_segments(
        self, split_client, auth_headers, db, test_user, monkeypatch
    ):
        """成功：任务流转 pending→completed，为每个知识点创建 Video + SplitSegment"""
        long_video, video = _make_long_video(db, test_user)

        # mock ffmpeg 切分器（避免真实视频依赖）
        class FakeSplitter:
            def split_segment(self, video_path, start_time, end_time, output_dir,
                              segment_index, generate_thumbnail=True):
                return (
                    f"/app/services/split/{output_dir}/segment_{segment_index:03d}.mp4",
                    f"/app/services/split/{output_dir}/segment_{segment_index:03d}.jpg",
                )

        from services.split.app.services import video_splitter as vs_module
        monkeypatch.setattr(vs_module, "VideoSplitter", lambda: FakeSplitter())

        response = split_client.post(
            "/api/split/direct-split",
            headers=auth_headers,
            json={
                "long_video_id": str(long_video.id),
                "knowledge_points": _knowledge_points(3),
                "organization_mode": "standalone"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "completed"
        assert data["data"]["progress"] == 100.0

        # 任务落库
        task = db.query(SplitTask).filter(
            SplitTask.task_id == data["data"]["task_id"]
        ).first()
        assert task is not None
        assert task.status == "completed"

        # 3 个知识点 → 3 个 SplitSegment + 3 个 segment Video
        segments = db.query(SplitSegment).filter(
            SplitSegment.task_id == task.id
        ).all()
        assert len(segments) == 3
        assert segments[0].start_time == 0

        segment_videos = db.query(Video).filter(
            Video.author_id == test_user.id,
            Video.status == "published"
        ).all()
        assert len(segment_videos) == 3
        # 路径转换：/app/services/split/ 前缀 → /smart_split_output/ 相对路径
        assert segment_videos[0].play_url.startswith("/smart_split_output/")
        assert "segment_000.mp4" in segment_videos[0].play_url

    def test_direct_split_long_video_not_found(self, split_client, auth_headers):
        """长视频不存在 → 404"""
        response = split_client.post(
            "/api/split/direct-split",
            headers=auth_headers,
            json={
                "long_video_id": str(uuid.uuid4()),
                "knowledge_points": _knowledge_points(1),
                "organization_mode": "standalone"
            }
        )

        assert response.status_code == 404

    def test_direct_split_other_users_video_forbidden(
        self, split_client, auth_headers, db, test_user2
    ):
        """越权切分他人视频 → 403"""
        long_video, _ = _make_long_video(db, test_user2)

        response = split_client.post(
            "/api/split/direct-split",
            headers=auth_headers,
            json={
                "long_video_id": str(long_video.id),
                "knowledge_points": _knowledge_points(1),
                "organization_mode": "standalone"
            }
        )

        assert response.status_code == 403

    def test_direct_split_splitter_failure_marks_task_failed(
        self, split_client, auth_headers, db, test_user, monkeypatch
    ):
        """切分异常：返回 500 且任务标记为 failed"""
        long_video, _ = _make_long_video(db, test_user)

        class BrokenSplitter:
            def split_segment(self, *args, **kwargs):
                raise RuntimeError("ffmpeg 不可用")

        from services.split.app.services import video_splitter as vs_module
        monkeypatch.setattr(vs_module, "VideoSplitter", lambda: BrokenSplitter())

        response = split_client.post(
            "/api/split/direct-split",
            headers=auth_headers,
            json={
                "long_video_id": str(long_video.id),
                "knowledge_points": _knowledge_points(1),
                "organization_mode": "standalone"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 400

        # 最近创建的任务应为 failed
        task = db.query(SplitTask).order_by(SplitTask.created_at.desc()).first()
        assert task.status == "failed"
        assert task.error_message


@pytest.mark.api
class TestAnalyzeWithRealFile:
    """analyze 视频文件存在时走真实分析服务（mock SmartSplitService）"""

    def _make_long_video_with_file(self, db, test_user, file_path):
        video = Video(
            id=str(uuid.uuid4()),
            author_id=test_user.id,
            title="有文件的视频",
            duration=3600,
            play_url="/videos/real.mp4",
            language="zh-CN",
            status="online",
            video_type="long"
        )
        db.add(video)
        db.flush()

        long_video = LongVideo(
            id=str(uuid.uuid4()),
            video_id=video.id,
            original_duration=3600,
            original_file_url=file_path,
            split_enabled=True
        )
        db.add(long_video)
        db.commit()
        db.refresh(long_video)
        return long_video

    def test_analyze_with_file_uses_service_result(
        self, split_client, auth_headers, db, test_user, tmp_path, monkeypatch
    ):
        """文件存在时返回服务分析结果（无降级标记）"""
        real_file = tmp_path / "real.mp4"
        real_file.write_bytes(b"fake video content")

        long_video = self._make_long_video_with_file(db, test_user, str(real_file))

        class FakeSmartService:
            def analyze_video(self, video_path, video_name=None):
                return {
                    "knowledge_points": [{"title": "AI 分析结果", "start_time": 0, "end_time": 60}],
                    "used_fallback": False,
                    "cached": False,
                }

        from services.split.app.services import smart_split_service as sss
        monkeypatch.setattr(sss, "SmartSplitService", lambda **kw: FakeSmartService())

        response = split_client.post(
            "/api/split/analyze",
            headers=auth_headers,
            json={"long_video_id": str(long_video.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["used_fallback"] is False
        assert data["data"]["knowledge_points"][0]["title"] == "AI 分析结果"
        assert data["data"]["message"] is None

    def test_analyze_cached_result_message(self, split_client, auth_headers, db, test_user, tmp_path, monkeypatch):
        """服务返回 cached=True 时提示使用缓存"""
        real_file = tmp_path / "cached.mp4"
        real_file.write_bytes(b"fake video content")

        long_video = self._make_long_video_with_file(db, test_user, str(real_file))

        class FakeSmartService:
            def analyze_video(self, video_path, video_name=None):
                return {"knowledge_points": [], "used_fallback": False, "cached": True}

        from services.split.app.services import smart_split_service as sss
        monkeypatch.setattr(sss, "SmartSplitService", lambda **kw: FakeSmartService())

        response = split_client.post(
            "/api/split/analyze",
            headers=auth_headers,
            json={"long_video_id": str(long_video.id)}
        )

        data = response.json()
        assert data["code"] == 200
        assert data["data"]["message"] == "使用缓存的分析结果"

    def test_analyze_service_error_returns_500(self, split_client, auth_headers, db, test_user, tmp_path, monkeypatch):
        """服务抛异常时返回 500 不崩溃"""
        real_file = tmp_path / "error.mp4"
        real_file.write_bytes(b"fake video content")

        long_video = self._make_long_video_with_file(db, test_user, str(real_file))

        class BrokenSmartService:
            def analyze_video(self, video_path, video_name=None):
                raise RuntimeError("AI service down")

        from services.split.app.services import smart_split_service as sss
        monkeypatch.setattr(sss, "SmartSplitService", lambda **kw: BrokenSmartService())

        response = split_client.post(
            "/api/split/analyze",
            headers=auth_headers,
            json={"long_video_id": str(long_video.id)}
        )

        assert response.status_code == 400
        assert response.json()["code"] == 400


@pytest.mark.api
class TestGetSplitResult:
    """获取完整分割结果"""

    def test_get_result_returns_task_and_segments(
        self, split_client, auth_headers, db, test_user
    ):
        """返回任务信息 + 片段列表（含 video_url 路径规范化）"""
        long_video, video = _make_long_video(db, test_user)
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

        # 片段 1：关联视频（play_url 无斜杠前缀 → 响应中补 /）
        seg_video = Video(
            id=str(uuid.uuid4()),
            author_id=test_user.id,
            title="片段视频",
            duration=60,
            play_url="smart_split_output/seg.mp4",
            language="zh-CN",
            status="published",
            video_type="short"
        )
        db.add(seg_video)
        db.flush()

        seg1 = SplitSegment(
            task_id=task.id,
            segment_index=1,
            start_time=0,
            end_time=60,
            duration=60,
            thumbnail_url="thumbnails/seg1.jpg",
            scene_type="auto",
            confidence=0.9,
            video_id=seg_video.id
        )
        # 片段 2：无关联视频
        seg2 = SplitSegment(
            task_id=task.id,
            segment_index=2,
            start_time=60,
            end_time=120,
            duration=60
        )
        db.add(seg1)
        db.add(seg2)
        db.commit()
        db.refresh(seg1)
        db.refresh(seg2)

        response = split_client.get(
            f"/api/split/tasks/{task.task_id}/result",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["task"]["status"] == "completed"
        assert len(data["data"]["segments"]) == 2

        # 路径规范化：无前缀的 thumbnail_url/video_url 自动补 /
        seg1_resp = data["data"]["segments"][0]
        assert seg1_resp["thumbnail_url"] == "/thumbnails/seg1.jpg"
        assert seg1_resp["video_url"] == "/smart_split_output/seg.mp4"
        # 无关联视频的片段 video_url 为 None
        assert data["data"]["segments"][1]["video_url"] is None

    def test_get_result_not_found(self, split_client, auth_headers):
        """任务不存在或无权访问 → 404"""
        response = split_client.get(
            "/api/split/tasks/00000000-0000-0000-0000-000000000000/result",
            headers=auth_headers
        )
        assert response.status_code == 404
    """简化分割接口（演示用）"""

    def test_simple_split_success_creates_demo_user_and_segments(
        self, split_client, db, test_user
    ):
        """成功：自动创建 demo 用户 + LongVideo + 5 个片段，任务直接 completed"""
        video = Video(
            id=str(uuid.uuid4()),
            author_id=test_user.id,
            title="演示视频",
            duration=300,
            play_url="/videos/demo.mp4",
            language="zh-CN",
            status="online",
            video_type="long"
        )
        db.add(video)
        db.commit()

        response = split_client.post(
            f"/api/split/simple-split?video_id={video.id}&threshold=0.2"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"].startswith("split_")
        assert len(data["segments"]) == 5

        # demo 用户自动创建
        demo_user = db.query(User).filter(User.id == DEMO_USER_ID).first()
        assert demo_user is not None

        # 任务 + 片段落库
        task = db.query(SplitTask).filter(
            SplitTask.task_id == data["task_id"]
        ).first()
        assert task.status == "completed"
        assert task.progress == 100.0
        segments = db.query(SplitSegment).filter(
            SplitSegment.task_id == task.id
        ).all()
        assert len(segments) == 5
        assert segments[0].start_time == 0

    def test_simple_split_reuses_existing_long_video(self, split_client, db, test_user):
        """已有 LongVideo 记录时复用，不重复创建"""
        video = Video(
            id=str(uuid.uuid4()),
            author_id=test_user.id,
            title="演示视频2",
            duration=300,
            play_url="/videos/demo2.mp4",
            language="zh-CN",
            status="online",
            video_type="long"
        )
        db.add(video)
        db.commit()

        long_video = LongVideo(
            id=str(uuid.uuid4()),
            video_id=video.id,
            original_duration=300,
            original_file_url="/videos/demo2.mp4",
            split_enabled=True
        )
        db.add(long_video)
        db.commit()

        response = split_client.post(f"/api/split/simple-split?video_id={video.id}")

        assert response.status_code == 200
        # LongVideo 数量仍为 1
        assert db.query(LongVideo).filter(LongVideo.video_id == video.id).count() == 1

    def test_simple_split_video_not_found(self, split_client, db):
        """video 不存在 → 404（修复前为外键错误 500）"""
        response = split_client.post(
            f"/api/split/simple-split?video_id={uuid.uuid4()}"
        )

        assert response.status_code == 404

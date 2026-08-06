"""
上传完成接口 - 分片合并路径测试

覆盖 complete_upload 中"有分片文件"的真实合并分支：
分片读取 → 合并写入 → 大小校验 → 文件哈希 → 存储上传 → 临时目录清理 → 视频创建。
（默认测试用例走"无分片文件"测试模式，本文件补齐合并路径）
"""
import io
import pytest

from pathlib import Path

from common.models.upload import UploadTask
from common.models.video import Video
from common.models import LongVideo


@pytest.mark.api
class TestCompleteUploadMerge:
    """分片合并路径"""

    def test_complete_with_chunks_merges_and_creates_video(
        self, upload_client, auth_headers, db, test_user, tmp_path, monkeypatch
    ):
        """有分片文件时：合并分片 → 上传存储 → 创建短视频 → 清理临时目录"""
        # 存储服务指向临时目录，避免污染工作区
        from services.upload.app.services.storage import LocalStorageService
        from services.upload.app import api as upload_api_module
        from services.upload.app.api import upload as upload_api

        storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
        monkeypatch.setattr(upload_api, "get_storage_service", lambda: storage)

        # 准备上传任务（status=uploaded 才允许 complete）
        upload_id = "UP_MERGE_TEST"
        upload_task = UploadTask(
            upload_id=upload_id,
            user_id=test_user.id,
            file_name="test.mp4",
            file_size=14,  # 两个 chunk 共 14 字节
            duration=120,
            video_type="short",
            status="uploaded"
        )
        db.add(upload_task)
        db.commit()

        # 往临时目录写入两个分片（chunk_0 + chunk_1）
        chunk_dir = upload_api.CHUNK_TEMP_DIR / upload_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        (chunk_dir / "chunk_0").write_bytes(b"hello world, ")
        (chunk_dir / "chunk_1").write_bytes(b"video data!")

        response = upload_client.post(
            "/api/upload/complete",
            headers=auth_headers,
            json={
                "upload_id": upload_id,
                "title": "合并测试",
                "description": "分片合并路径",
                "tags": ["测试"],
                "language": "zh-CN",
                "is_public": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "transcoding"
        assert data["data"]["file_url"] == f"/uploads/videos/{test_user.id}/{upload_id}.mp4"

        # 视频记录已创建
        video = db.query(Video).filter(Video.title == "合并测试").first()
        assert video is not None
        assert video.status == "transcoding"
        assert video.video_type == "short"

        # 合并后的文件已上传到存储（内容 = 两个分片拼接）
        stored_file = Path(tmp_path / "uploads" / "videos" / str(test_user.id) / f"{upload_id}.mp4")
        assert stored_file.read_bytes() == b"hello world, video data!"

        # 临时目录已清理
        assert not chunk_dir.exists()

    def test_complete_long_video_creates_long_video_record(
        self, upload_client, auth_headers, db, test_user, tmp_path, monkeypatch
    ):
        """长视频：额外创建 LongVideo 记录（供智能切分）"""
        from services.upload.app.services.storage import LocalStorageService
        from services.upload.app.api import upload as upload_api

        storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
        monkeypatch.setattr(upload_api, "get_storage_service", lambda: storage)

        upload_id = "UP_MERGE_LONG"
        upload_task = UploadTask(
            upload_id=upload_id,
            user_id=test_user.id,
            file_name="long.mp4",
            file_size=5,
            duration=600,
            video_type="long",
            status="uploaded"
        )
        db.add(upload_task)
        db.commit()

        chunk_dir = upload_api.CHUNK_TEMP_DIR / upload_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        (chunk_dir / "chunk_0").write_bytes(b"12345")

        response = upload_client.post(
            "/api/upload/complete",
            headers=auth_headers,
            json={
                "upload_id": upload_id,
                "title": "长视频测试",
                "language": "zh-CN"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "long_video_id" in data["data"]

        # LongVideo 记录存在且与 Video 关联
        long_video = db.query(LongVideo).first()
        assert long_video is not None
        assert long_video.split_enabled is True

    def test_complete_merge_failure_returns_500(
        self, upload_client, auth_headers, db, test_user, tmp_path, monkeypatch
    ):
        """合并失败（存储上传抛异常）时返回 500 而非静默成功"""
        from services.upload.app.api import upload as upload_api

        def broken_storage(*args, **kwargs):
            raise RuntimeError("storage down")

        monkeypatch.setattr(upload_api, "get_storage_service", broken_storage)

        upload_id = "UP_MERGE_FAIL"
        upload_task = UploadTask(
            upload_id=upload_id,
            user_id=test_user.id,
            file_name="fail.mp4",
            file_size=5,
            duration=60,
            video_type="short",
            status="uploaded"
        )
        db.add(upload_task)
        db.commit()

        chunk_dir = upload_api.CHUNK_TEMP_DIR / upload_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        (chunk_dir / "chunk_0").write_bytes(b"12345")

        response = upload_client.post(
            "/api/upload/complete",
            headers=auth_headers,
            json={"upload_id": upload_id, "title": "失败测试", "language": "zh-CN"}
        )

        assert response.status_code == 500
        data = response.json()
        assert data["code"] == 500
        # 任务状态保持 uploaded，不产生视频
        db.refresh(upload_task)
        assert upload_task.status == "uploaded"

"""
视频拆分服务层测试（video_split_service）

- MockVideoSplitService：等长切分逻辑（auto/manual 模式、自定义片段时长）
- RealVideoSplitService：ffmpeg 检查、ffprobe 时长解析（mock subprocess）
- 工厂函数：mock/real/smart 三分支
"""
import json
import pytest
from unittest import mock

from services.split.app.services.video_split_service import (
    get_video_split_service,
    MockVideoSplitService,
    RealVideoSplitService,
)


@pytest.mark.unit
class TestMockVideoSplitService:
    """模拟拆分服务"""

    def test_split_auto_mode_5_segments(self):
        """300 秒视频按默认 60 秒切 5 段"""
        service = MockVideoSplitService()
        segments = service.split_video("/videos/x.mp4", split_mode="auto")

        assert len(segments) == 5
        assert segments[0] == {
            "segment_index": 0, "start_time": 0, "end_time": 60, "duration": 60,
            "thumbnail_url": "/thumbnails/segment_0.jpg",
            "scene_type": "auto", "confidence": 0.85
        }
        assert segments[-1]["end_time"] == 300

    def test_split_with_custom_segment_duration(self):
        """auto_config 自定义片段时长 30 秒 → 10 段"""
        service = MockVideoSplitService()
        segments = service.split_video(
            "/videos/x.mp4", split_mode="auto",
            auto_config={"segment_duration": 30}
        )
        assert len(segments) == 10

    def test_split_manual_mode(self):
        """manual 模式：scene_type=manual、confidence=1.0"""
        service = MockVideoSplitService()
        segments = service.split_video("/videos/x.mp4", split_mode="manual")
        assert segments[0]["scene_type"] == "manual"
        assert segments[0]["confidence"] == 1.0

    def test_get_video_duration_mock(self):
        assert MockVideoSplitService().get_video_duration("x.mp4") == 300


@pytest.mark.unit
class TestRealVideoSplitService:
    """实际拆分服务（ffmpeg）"""

    def test_init_checks_ffmpeg(self, tmp_path):
        """ffmpeg 可用时构造成功（本机已装 ffmpeg）"""
        service = RealVideoSplitService(output_dir=str(tmp_path / "out"))
        assert service.output_dir.exists()

    def test_get_video_duration_parses_ffprobe(self, tmp_path):
        """ffprobe 输出 JSON 解析为秒数"""
        service = RealVideoSplitService(output_dir=str(tmp_path / "out"))
        fake_result = mock.MagicMock(stdout=json.dumps({"format": {"duration": "123.45"}}))
        with mock.patch("subprocess.run", return_value=fake_result):
            assert service.get_video_duration("/videos/x.mp4") == 123

    def test_get_video_duration_fallback_on_error(self, tmp_path):
        """ffprobe 失败时明确抛出 RuntimeError（由调用方降级）"""
        service = RealVideoSplitService(output_dir=str(tmp_path / "out"))
        with mock.patch("subprocess.run", side_effect=Exception("ffprobe error")):
            with pytest.raises(RuntimeError):
                service.get_video_duration("/videos/x.mp4")


@pytest.mark.unit
class TestRealSplitVideo:
    """实际切分逻辑（mock ffmpeg/ffprobe）"""

    def _service(self, tmp_path):
        return RealVideoSplitService(output_dir=str(tmp_path / "out"))

    def test_video_not_found_raises(self, tmp_path):
        service = self._service(tmp_path)
        with pytest.raises(FileNotFoundError):
            service.split_video("/nonexistent/x.mp4", split_mode="auto")

    def test_split_success_with_default_config(self, tmp_path):
        """300 秒视频按 60 秒切 5 段，ffmpeg 命令构造正确"""
        service = self._service(tmp_path)
        fake_video = tmp_path / "video.mp4"
        fake_video.write_bytes(b"fake")
        with mock.patch.object(service, "get_video_duration", return_value=300), \
             mock.patch("subprocess.run", return_value=mock.MagicMock()) as run:
            segments = service.split_video(
                str(fake_video), split_mode="auto"
            )

        assert len(segments) == 5
        assert segments[0]["start_time"] == 0
        assert segments[0]["end_time"] == 60
        assert segments[-1]["end_time"] == 300
        assert segments[0]["scene_type"] == "auto"

        # ffmpeg 命令: 主切分 + 缩略图各 5 次
        assert run.call_count == 10
        main_cmd = run.call_args_list[0].args[0]
        assert main_cmd[0] == "ffmpeg"
        assert "-c" in main_cmd and main_cmd[main_cmd.index("-c") + 1] == "copy"
        # 缩略图命令含 -vframes 1
        thumb_cmd = run.call_args_list[5].args[0]
        assert "-vframes" in thumb_cmd

    def test_split_with_custom_auto_config(self, tmp_path):
        """auto_config 自定义 30 秒片段 → 10 段"""
        service = self._service(tmp_path)
        fake_video = tmp_path / "video2.mp4"
        fake_video.write_bytes(b"fake")
        with mock.patch.object(service, "get_video_duration", return_value=300), \
             mock.patch("subprocess.run", return_value=mock.MagicMock()):
            segments = service.split_video(
                str(fake_video), split_mode="auto",
                auto_config={"segment_duration": 30}
            )
        assert len(segments) == 10

    def test_short_tail_merged_into_previous(self, tmp_path):
        """尾段时长 < min_duration 时合并到上一段"""
        service = self._service(tmp_path)
        # 305 秒: 60*5 + 尾段 5s < 30 → 合并 → 共 5 段
        fake_video = tmp_path / "video3.mp4"
        fake_video.write_bytes(b"fake")
        with mock.patch.object(service, "get_video_duration", return_value=305), \
             mock.patch("subprocess.run", return_value=mock.MagicMock()):
            segments = service.split_video(
                str(fake_video), split_mode="auto",
                auto_config={"segment_duration": 60, "min_duration": 30}
            )
        # 5 段（尾段 5s 合并进第 5 段 → 第 5 段 0-305 中 240-305 = 65s）
        assert len(segments) == 5
        assert segments[-1]["end_time"] == 305
        assert segments[-1]["duration"] == 65

    def test_ffmpeg_failure_skips_segment(self, tmp_path):
        """某段 ffmpeg 失败时跳过，其余段继续"""
        service = self._service(tmp_path)
        real_run = __import__("subprocess").run

        def flaky_run(cmd, **kwargs):
            # 主切分命令（无 -vframes）处理 segment_2 时失败
            if "-vframes" not in cmd and any("segment_2" in c for c in cmd):
                raise __import__("subprocess").CalledProcessError(1, cmd, stderr=b"boom")
            return mock.MagicMock()

        fake_video = tmp_path / "video4.mp4"
        fake_video.write_bytes(b"fake")
        with mock.patch.object(service, "get_video_duration", return_value=300), \
             mock.patch("subprocess.run", side_effect=flaky_run):
            segments = service.split_video(str(fake_video), split_mode="auto")

        # 5 段中 1 段失败 → 4 段成功
        assert len(segments) == 4
        assert segments[0]["segment_index"] == 0
        assert segments[-1]["segment_index"] == 4


@pytest.mark.unit
class TestGetVideoSplitServiceFactory:
    """服务工厂"""

    def test_default_is_mock(self, monkeypatch, tmp_path):
        monkeypatch.delenv("VIDEO_SPLIT_SERVICE_TYPE", raising=False)
        monkeypatch.setenv("VIDEO_SPLIT_SEGMENT_DURATION", "60")
        assert isinstance(get_video_split_service(), MockVideoSplitService)

    def test_real_type_returns_real_service(self, monkeypatch, tmp_path):
        monkeypatch.setenv("VIDEO_SPLIT_SERVICE_TYPE", "real")
        monkeypatch.setenv("VIDEO_SPLIT_OUTPUT_DIR", str(tmp_path / "out"))
        assert isinstance(get_video_split_service(), RealVideoSplitService)

    def test_smart_type_returns_smart_service(self, monkeypatch, tmp_path):
        """smart 分支返回智能服务（无重型依赖也可加载，降级由管线内处理）"""
        monkeypatch.setenv("VIDEO_SPLIT_SERVICE_TYPE", "smart")
        monkeypatch.setenv("VIDEO_SPLIT_OUTPUT_DIR", str(tmp_path / "out"))
        from services.split.app.services.smart_split_service import SmartSplitService
        assert isinstance(get_video_split_service(), SmartSplitService)

    def test_smart_type_falls_back_to_mock_on_import_error(self, monkeypatch, tmp_path):
        """smart 分支加载失败回退 mock 服务"""
        monkeypatch.setenv("VIDEO_SPLIT_SERVICE_TYPE", "smart")
        monkeypatch.setenv("VIDEO_SPLIT_OUTPUT_DIR", str(tmp_path / "out"))
        with mock.patch.dict("sys.modules", {"services.split.app.services.smart_split_service": None}):
            service = get_video_split_service()
        assert isinstance(service, MockVideoSplitService)

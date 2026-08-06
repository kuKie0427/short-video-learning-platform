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

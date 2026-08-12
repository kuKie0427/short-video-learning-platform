"""
SmartSplitService 服务层测试（mock SmartSplitPipeline）

覆盖:analyze_video 的文件校验、缓存命中跳过分析、分析结果写入 analysis_result.json。
"""
import json
import pytest
from unittest import mock

from services.split.app.services.smart_split_service import SmartSplitService


@pytest.fixture
def service(tmp_path):
    return SmartSplitService(output_dir=str(tmp_path / "out"))


@pytest.mark.unit
class TestAnalyzeVideo:
    """仅分析模式"""

    def test_video_not_found_raises(self, service):
        with pytest.raises(FileNotFoundError):
            service.analyze_video("/nonexistent/x.mp4", video_name="v1")

    def test_analyze_success_and_cache_written(self, service, tmp_path):
        """调用 pipeline 分析，结果落盘 analysis_result.json"""
        fake_video = tmp_path / "video.mp4"
        fake_video.write_bytes(b"fake")

        points = [{"id": 1, "title": "知识点A", "start_time": 0, "end_time": 60}]
        with mock.patch(
            "services.split.app.services.smart_split_service.SmartSplitPipeline"
        ) as MockPipeline:
            MockPipeline.return_value.run.return_value = (points, False)
            result = service.analyze_video(str(fake_video), video_name="v1")

        assert result == {
            "knowledge_points": points,
            "used_fallback": False,
            "cached": False,
        }
        # analysis_result.json 缓存写入
        cache_file = tmp_path / "out" / "v1" / "analysis_result.json"
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        assert cached["knowledge_points"] == points
        assert cached["cache_version"] == "1.0"

    def test_analyze_cache_hit_skips_pipeline(self, service, tmp_path):
        """缓存命中时直接返回 cached=True，不调用 pipeline"""
        fake_video = tmp_path / "video.mp4"
        fake_video.write_bytes(b"fake")

        # 预写 knowledge 缓存
        knowledge_file = tmp_path / "out" / "v2" / "knowledge" / "knowledge_points.txt"
        knowledge_file.parent.mkdir(parents=True)
        knowledge_file.write_text("[00:00]-[01:00] 缓存知识点\n", encoding="utf-8")

        with mock.patch(
            "services.split.app.services.smart_split_service.SmartSplitPipeline"
        ) as MockPipeline:
            result = service.analyze_video(str(fake_video), video_name="v2")

        assert result["cached"] is True
        assert result["used_fallback"] is False
        assert result["knowledge_points"][0]["title"] == "缓存知识点"
        MockPipeline.assert_not_called()

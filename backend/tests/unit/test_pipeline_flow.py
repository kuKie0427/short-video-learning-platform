"""
SmartSplitPipeline 流程编排测试（mock AI 组件，不依赖 torch/opencv/模型权重）

覆盖:无 AI 依赖时报错、完整切分流程（目录创建/步骤调用/knowledge 文件写入）、
缓存命中跳过分析、analysis_only 模式、fallback 标志检测。
"""
import pytest
from unittest import mock

from services.split.app.services.smart_split import pipeline as pipeline_mod
from services.split.app.services.smart_split.pipeline import SmartSplitPipeline


@pytest.fixture
def mock_ai_components(monkeypatch):
    """将 AI 重型组件替换为假实现，并声明依赖可用"""
    monkeypatch.setattr(pipeline_mod, "_AI_DEPS_AVAILABLE", True)

    calls = {"order": []}

    class FakeSpeechToText:
        def extract_audio(self, video_path, audio_path):
            calls["order"].append("extract_audio")
            return audio_path

        def process_audio(self, audio_file, output_file):
            calls["order"].append("process_audio")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("test")
            return output_file

    class FakeKeyframeExtractor:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            calls["order"].append("keyframes")
            return ["frame_1.jpg", "frame_2.jpg"]

    class FakeKnowledgeAnalyzer:
        def __init__(self, *args, **kwargs):
            self.knowledge_points = [
                {"start_time": 0, "end_time": 60, "duration": 60, "content": "极限的定义"},
                {"start_time": 60, "end_time": 120, "duration": 60, "content": "导数的概念"},
            ]

        def analyze_knowledge_points(self):
            calls["order"].append("analyze")
            return self.knowledge_points

    class FakeVideoSplitter:
        def __init__(self, *args, **kwargs):
            pass

        def parse_knowledge_points(self):
            calls["order"].append("parse_kp")
            return [{"start_time": 0, "end_time": 60, "duration": 60, "title": "t"}]

        def split_video(self, kp_list, method="copy"):
            calls["order"].append("split")
            return [
                {
                    "path": "/out/seg_1.mp4",
                    "filename": "seg_1.mp4",
                    "knowledge_point": kp_list[0],
                    "size_mb": 1.5,
                }
            ]

    monkeypatch.setattr(pipeline_mod, "SpeechToText", FakeSpeechToText)
    monkeypatch.setattr(pipeline_mod, "KeyframeExtractor", FakeKeyframeExtractor)
    monkeypatch.setattr(pipeline_mod, "KnowledgePointAnalyzer", FakeKnowledgeAnalyzer)
    monkeypatch.setattr(pipeline_mod, "VideoSplitter", FakeVideoSplitter)
    return calls


@pytest.mark.unit
class TestPipelineFlow:
    """流程编排"""

    def test_run_without_ai_deps_raises(self, tmp_path):
        """无重型 AI 依赖时 run 给出明确错误（组件可用性检查）"""
        from services.split.app.services.smart_split import pipeline as p
        if p._AI_DEPS_AVAILABLE:
            pytest.skip("本环境已安装 AI 依赖，跳过")
        pipeline = SmartSplitPipeline(output_base_dir=str(tmp_path / "out"))
        with pytest.raises(ImportError):
            pipeline.run("/videos/x.mp4", video_name="v1")

    def test_full_split_flow(self, tmp_path, mock_ai_components):
        """完整切分: 步骤顺序调用 + 目录创建 + knowledge 文件写入 + segments 返回"""
        pipeline = SmartSplitPipeline(
            output_base_dir=str(tmp_path / "out"),
            glm_api_key=None
        )
        segments, used_fallback = pipeline.run(
            "/videos/x.mp4", analysis_only=False, video_name="v1"
        )

        # 步骤顺序: 提取音频 → 转写 → 关键帧 → 分析 → 切分
        assert mock_ai_components["order"] == [
            "extract_audio", "process_audio", "keyframes", "analyze", "parse_kp", "split"
        ]
        # 目录创建
        work_dir = tmp_path / "out" / "v1"
        for sub in ["audio", "keyframes", "stt", "knowledge", "videos"]:
            assert (work_dir / sub).is_dir()
        # knowledge 文件写入（供后续步骤解析）
        assert (work_dir / "knowledge" / "knowledge_points.txt").exists()
        # 返回 segments
        assert len(segments) == 1
        assert segments[0]["scene_type"] == "smart"
        assert segments[0]["video_url"] == "/out/seg_1.mp4"
        assert used_fallback is False

    def test_cache_skips_analysis(self, tmp_path, mock_ai_components):
        """已有知识点缓存时跳过分析步骤（组件不被实例化）"""
        work_dir = tmp_path / "out" / "v2"
        knowledge_dir = work_dir / "knowledge"
        knowledge_dir.mkdir(parents=True)
        (knowledge_dir / "knowledge_points.txt").write_text(
            "[00:00]-[01:00] 缓存知识点\n", encoding="utf-8"
        )

        pipeline = SmartSplitPipeline(output_base_dir=str(tmp_path / "out"))
        segments, used_fallback = pipeline.run(
            "/videos/x.mp4", analysis_only=False, video_name="v2"
        )

        # 未调用分析步骤（extract_audio 等）
        assert "extract_audio" not in mock_ai_components["order"]
        assert "process_audio" not in mock_ai_components["order"]
        assert "analyze" not in mock_ai_components["order"]
        # 直接进入切分
        assert "parse_kp" in mock_ai_components["order"]
        assert len(segments) >= 1

    def test_analysis_only_mode(self, tmp_path, mock_ai_components):
        """仅分析模式: 返回格式化知识点,不执行切分"""
        pipeline = SmartSplitPipeline(output_base_dir=str(tmp_path / "out"))
        points, used_fallback = pipeline.run(
            "/videos/x.mp4", analysis_only=True, video_name="v3"
        )

        assert len(points) == 2
        assert points[0]["id"] == 1
        assert points[0]["title"] == "极限的定义"
        assert points[0]["start_time"] == 0
        # 未调用切分
        assert "parse_kp" not in mock_ai_components["order"]
        assert "split" not in mock_ai_components["order"]

    def test_fallback_flag_detection(self, tmp_path, monkeypatch):
        """分析结果标题以'片段'开头 → used_fallback=True"""
        monkeypatch.setattr(pipeline_mod, "_AI_DEPS_AVAILABLE", True)

        class FallbackAnalyzer:
            def __init__(self, *args, **kwargs):
                pass

            def analyze_knowledge_points(self):
                return [
                    {"start_time": 0, "end_time": 60, "duration": 60, "title": "片段1"},
                ]

        monkeypatch.setattr(pipeline_mod, "SpeechToText", mock.MagicMock)
        monkeypatch.setattr(pipeline_mod, "KeyframeExtractor", mock.MagicMock)
        monkeypatch.setattr(pipeline_mod, "KnowledgePointAnalyzer", FallbackAnalyzer)
        monkeypatch.setattr(pipeline_mod, "VideoSplitter", mock.MagicMock)

        pipeline = SmartSplitPipeline(output_base_dir=str(tmp_path / "out"))
        points, used_fallback = pipeline.run(
            "/videos/x.mp4", analysis_only=True, video_name="v4"
        )

        assert used_fallback is True

"""
GLM 知识点分析降级路径测试

验证：未配置 GLM_API_KEY 或未安装 zhipuai SDK 时，
系统不崩溃并自动降级为 60 秒等长切分（fallback）。
"""
import json
import os
import pytest

from common.config.settings import settings


@pytest.mark.unit
class TestGlmFallback:
    """AI 依赖降级测试"""

    def test_settings_has_no_hardcoded_key(self):
        """配置中不应内置/硬编码 API 密钥（环境变量未设置时）"""
        if "GLM_API_KEY" not in os.environ:
            assert settings.GLM_API_KEY is None

    def test_analyzer_without_key_creates_no_client(self, tmp_path):
        """未配置密钥时不创建 GLM 客户端"""
        from services.split.app.services.smart_split.knowledge_analyzer import KnowledgePointAnalyzer

        stt_file = tmp_path / "stt.jsonl"
        stt_file.write_text(
            json.dumps({"start": 0, "end": 30, "text": "测试内容"}) + "\n",
            encoding="utf-8"
        )
        analyzer = KnowledgePointAnalyzer(
            stt_output_path=str(stt_file),
            image_folder_path=str(tmp_path / "images"),
            api_key=None
        )
        assert analyzer.client is None

    def test_analyze_falls_back_to_equal_split(self, tmp_path):
        """无密钥时知识点分析降级为 60 秒等长切分"""
        from services.split.app.services.smart_split.knowledge_analyzer import KnowledgePointAnalyzer

        stt_file = tmp_path / "stt.jsonl"
        segments = [
            {"start": 0, "end": 30, "text": "极限的定义"},
            {"start": 30, "end": 60, "text": "极限的计算方法"},
            {"start": 60, "end": 90, "text": "导数的概念"},
            {"start": 90, "end": 125, "text": "微积分基本定理"},
        ]
        with open(stt_file, "w", encoding="utf-8") as f:
            for s in segments:
                f.write(json.dumps(s) + "\n")

        analyzer = KnowledgePointAnalyzer(
            stt_output_path=str(stt_file),
            image_folder_path=str(tmp_path / "images"),
            api_key=None
        )
        result = analyzer.analyze_knowledge_points()

        # 降级切分：每 60 秒一段，125 秒 → 3 段（0-60, 60-120, 120-125）
        assert result, "降级切分不应返回空"
        assert result[0]["start_time"] == 0
        assert result[0]["end_time"] == 60
        assert result[-1]["end_time"] >= 120
        # 降级标志：标题为"片段N"格式
        assert result[0]["title"].startswith("片段")

    def test_pipeline_constructs_without_key(self, tmp_path):
        """管线在无密钥时也能正常构造（不崩溃）"""
        from services.split.app.services.smart_split.pipeline import SmartSplitPipeline

        pipeline = SmartSplitPipeline(
            output_base_dir=str(tmp_path / "out"),
            glm_api_key=None
        )
        assert pipeline.glm_api_key is None

    def test_heavy_deps_missing_raises_clear_error(self):
        """未安装 AI 重型依赖时，实例化关键组件应给出明确错误而非静默崩溃"""
        from services.split.app.services.smart_split import keyframe_extractor as ke
        if ke.cv2 is None:
            with pytest.raises(ImportError):
                ke.KeyframeExtractor(video_path="dummy.mp4")

        from services.split.app.services.smart_split import speech_to_text as stt
        if stt.torch is None:
            with pytest.raises(ImportError):
                stt.SpeechToText()

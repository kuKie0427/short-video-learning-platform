"""
KnowledgePointAnalyzer 纯逻辑测试（不依赖 GLM API / opencv）

覆盖:时间格式化、STT 结果加载、语音内容组织/筛选/合并、
关键图片选择、图片文字描述、批量分析结果解析。
"""
import json
import pytest

from services.split.app.services.smart_split.knowledge_analyzer import (
    KnowledgePointAnalyzer,
)


def _make_analyzer(tmp_path, **kwargs):
    stt_file = tmp_path / "stt.jsonl"
    stt_file.write_text("", encoding="utf-8")
    return KnowledgePointAnalyzer(
        stt_output_path=str(stt_file),
        image_folder_path=str(tmp_path / "images"),
        api_key=None,
        **kwargs
    )


@pytest.mark.unit
class TestFormatTime:
    """时间格式化"""

    def test_format_seconds(self, tmp_path):
        analyzer = _make_analyzer(tmp_path)
        assert analyzer.format_time(0) == "[00:00]"
        assert analyzer.format_time(90) == "[01:30]"
        assert analyzer.format_time(3723) == "[62:03]"


@pytest.mark.unit
class TestLoadSttResults:
    """STT 结果加载"""

    def test_load_valid_jsonl(self, tmp_path):
        stt_file = tmp_path / "stt.jsonl"
        stt_file.write_text(
            json.dumps({"start": 0, "end": 10, "text": "你好"}) + "\n"
            + json.dumps({"start": 10, "end": 20, "text": "世界"}) + "\n",
            encoding="utf-8"
        )
        analyzer = KnowledgePointAnalyzer(
            stt_output_path=str(stt_file),
            image_folder_path=str(tmp_path / "images"),
            api_key=None
        )
        results = analyzer.load_stt_results()
        assert len(results) == 2
        assert results[0]["text"] == "你好"

    def test_load_empty_file(self, tmp_path):
        analyzer = _make_analyzer(tmp_path)
        assert analyzer.load_stt_results() == []

    def test_load_bad_lines_skipped(self, tmp_path):
        stt_file = tmp_path / "stt.jsonl"
        stt_file.write_text("not-json\n" + json.dumps({"start": 1}) + "\n", encoding="utf-8")
        analyzer = KnowledgePointAnalyzer(
            stt_output_path=str(stt_file),
            image_folder_path=str(tmp_path / "images"),
            api_key=None
        )
        assert analyzer.load_stt_results() == []

    def test_missing_file_returns_empty(self, tmp_path):
        analyzer = KnowledgePointAnalyzer(
            stt_output_path=str(tmp_path / "none.jsonl"),
            image_folder_path=str(tmp_path / "images"),
            api_key=None
        )
        assert analyzer.load_stt_results() == []


@pytest.mark.unit
class TestSpeechContent:
    """语音内容组织与筛选"""

    def test_get_all_speech_content_sorts_and_filters(self, tmp_path):
        analyzer = _make_analyzer(tmp_path)
        results = [
            {"start": 30, "end": 40, "text": "后"},
            {"start": 0, "end": 10, "text": "前"},
            {"start": 10, "end": 20, "text": "  "},  # 空白文本被过滤
        ]
        content = analyzer.get_all_speech_content(results)

        assert len(content) == 2
        assert content[0]["start"] == 0
        assert content[0]["mid_time"] == 5.0
        # index 为原始列表索引（排序前的位置），空白条目被过滤后保留原索引
        assert content[1]["index"] == 2

    def test_select_key_segments_within_limit(self, tmp_path):
        analyzer = _make_analyzer(tmp_path, max_speech_segments=50)
        content = [{"start": i * 10, "end": i * 10 + 5, "text": f"s{i}"} for i in range(10)]
        assert analyzer.select_key_speech_segments(content) == content

    def test_select_key_segments_sampling(self, tmp_path):
        """超过上限时均匀抽样；抽样后末尾片段被保留（实现为尾部优先）"""
        analyzer = _make_analyzer(tmp_path, max_speech_segments=5)
        content = [{"start": i * 10, "end": i * 10 + 5, "text": f"s{i}"} for i in range(20)]
        selected = analyzer.select_key_speech_segments(content)

        assert len(selected) <= 5
        # 末尾片段保留（实现逻辑: 抽样不足 10s 时追加最后一条）
        assert any(s["end"] == 195 for s in selected)

    def test_merge_adjacent_segments(self, tmp_path):
        """时间间隔 <3s 的连续片段被合并"""
        analyzer = _make_analyzer(tmp_path, max_speech_segments=2)
        segments = [
            {"start": 0, "end": 10, "mid_time": 5, "text": "第一段"},
            {"start": 11, "end": 20, "mid_time": 15, "text": "第二段"},  # 间隔 1s → 合并
            {"start": 30, "end": 40, "mid_time": 35, "text": "第三段"},  # 间隔 10s → 不合并
        ]
        merged = analyzer.merge_speech_segments(segments)

        assert len(merged) == 2
        assert "第一段 第二段" in merged[0]["text"]
        assert merged[1]["text"] == "第三段"


@pytest.mark.unit
class TestImageSelection:
    """关键图片选择"""

    def _image_files(self, n):
        return [
            {"filename": f"frame_{i}.jpg", "timestamp": i * 10}
            for i in range(n)
        ]

    def test_all_images_when_within_limit(self, tmp_path):
        analyzer = _make_analyzer(tmp_path, max_direct_images=8)
        images = self._image_files(5)
        direct, text = analyzer.select_key_images(images)
        assert direct == images
        assert text == []

    def test_split_when_exceed_limit(self, tmp_path):
        analyzer = _make_analyzer(tmp_path, max_direct_images=3)
        images = self._image_files(10)
        direct, text = analyzer.select_key_images(images)

        assert len(direct) == 3
        assert len(text) == 7
        # 直接发送的按时间排序
        timestamps = [d["timestamp"] for d in direct]
        assert timestamps == sorted(timestamps)

    def test_describe_images_type_inference(self, tmp_path):
        analyzer = _make_analyzer(tmp_path)
        desc = analyzer.describe_images_as_text([
            {"filename": "slide_1.png", "timestamp": 60},
            {"filename": "diagram_2.png", "timestamp": 120},
            {"filename": "formula_3.png", "timestamp": 180},
            {"filename": "other.png", "timestamp": 240},
        ])
        assert "幻灯片" in desc
        assert "图表" in desc
        assert "公式" in desc
        assert "截图" in desc
        assert "[01:00]" in desc


@pytest.mark.unit
class TestParseBatchResult:
    """批量分析结果解析"""

    def test_parse_valid_lines(self, tmp_path):
        analyzer = _make_analyzer(tmp_path)
        result = "[00:00]-[01:30] 极限的定义\n[01:30]-[03:00] 导数的概念"
        points = analyzer.parse_batch_analysis_result(result)

        assert len(points) == 2
        assert points[0]["start_time"] == 0
        assert points[0]["end_time"] == 90
        assert points[0]["title"] == "极限的定义"
        assert points[1]["duration"] == 90

    def test_parse_empty_and_bad_lines(self, tmp_path):
        analyzer = _make_analyzer(tmp_path)
        assert analyzer.parse_batch_analysis_result("") == []
        assert analyzer.parse_batch_analysis_result(None) == []
        assert analyzer.parse_batch_analysis_result("无法解析的行") == []
        # 带 <|end_of_box|> 标记的行也能解析（标记先被移除）
        points = analyzer.parse_batch_analysis_result("[00:00]-[01:00] 知识点<|end_of_box|>")
        assert len(points) == 1
        assert points[0]["title"] == "知识点"

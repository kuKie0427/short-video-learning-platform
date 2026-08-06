"""
视频分割器测试（VideoSplitter）

- parse_knowledge_points：4 种知识点格式解析、注释/空行/非法行/时间倒置处理
- parse_time_to_seconds：MM:SS 与 HH:MM:SS 转换
- split_video：mock ffmpeg subprocess，验证 copy/转码命令参数、文件名安全化、失败处理
"""
import os
import subprocess
import pytest
from unittest import mock

from services.split.app.services.smart_split.video_splitter import VideoSplitter


@pytest.mark.unit
class TestParseTimeToSeconds:
    """时间格式转换"""

    def test_mm_ss(self):
        splitter = VideoSplitter("v.mp4", "k.txt")
        assert splitter.parse_time_to_seconds("01:30") == 90

    def test_hh_mm_ss(self):
        splitter = VideoSplitter("v.mp4", "k.txt")
        assert splitter.parse_time_to_seconds("01:02:03") == 3723

    def test_invalid_format_raises(self):
        splitter = VideoSplitter("v.mp4", "k.txt")
        with pytest.raises(ValueError):
            splitter.parse_time_to_seconds("abc")


@pytest.mark.unit
class TestParseKnowledgePoints:
    """知识点文件解析"""

    def test_parses_multiple_formats(self, tmp_path):
        kf = tmp_path / "knowledge.txt"
        kf.write_text(
            "1. [00:00]-[00:30] 极限的定义\n"
            "[01:00]-[02:00] 导数的概念\n"
            "3. 03:00-03:30 积分入门\n"
            "04:00-04:45 微积分基本定理\n",
            encoding="utf-8"
        )
        splitter = VideoSplitter("v.mp4", str(kf))
        points = splitter.parse_knowledge_points()

        assert len(points) == 4
        assert points[0] == {
            "index": 1, "start_time": 0, "end_time": 30,
            "duration": 30, "title": "极限的定义"
        }
        assert points[3]["start_time"] == 240
        assert points[3]["end_time"] == 285

    def test_skips_comments_empty_and_bad_lines(self, tmp_path):
        kf = tmp_path / "knowledge.txt"
        kf.write_text(
            "# 注释行\n"
            "\n"
            "无法识别的行内容\n"
            "[05:00]-[04:00] 时间倒置（end<=start 跳过）\n"
            "[00:10]-[01:00] 正常行\n",
            encoding="utf-8"
        )
        splitter = VideoSplitter("v.mp4", str(kf))
        points = splitter.parse_knowledge_points()

        assert len(points) == 1
        assert points[0]["title"] == "正常行"

    def test_missing_file_returns_empty(self, tmp_path):
        splitter = VideoSplitter("v.mp4", str(tmp_path / "nonexistent.txt"))
        assert splitter.parse_knowledge_points() == []


@pytest.mark.unit
class TestSplitVideo:
    """ffmpeg 分割（mock subprocess）"""

    def _make_points(self):
        return [
            {"start_time": 0, "end_time": 60, "title": "第一节:极限", "index": 1},
            {"start_time": 60, "end_time": 120, "title": '第二节<导数>/测试', "index": 2},
        ]

    def test_copy_method_builds_ffmpeg_command(self, tmp_path):
        splitter = VideoSplitter("input.mp4", "k.txt", output_dir=str(tmp_path / "out"))
        points = self._make_points()

        with mock.patch("subprocess.run", return_value=mock.MagicMock(returncode=0)) as run:
            # 模拟输出文件存在
            with mock.patch("os.path.exists", return_value=True), \
                 mock.patch("os.path.getsize", return_value=1024 * 1024):
                files = splitter.split_video(points, method="copy")

        assert len(files) == 2
        # copy 模式：-c copy，无转码参数
        cmd = run.call_args_list[0].args[0]
        assert cmd[0] == "ffmpeg"
        assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"
        assert "-ss" in cmd
        assert "-avoid_negative_ts" in cmd
        # 文件名已做安全化（非法字符替换为 _）
        assert files[1]["filename"].endswith(".mp4")
        assert "<" not in files[1]["filename"] and "/" not in files[1]["filename"]
        assert files[0]["size_mb"] == 1.0

    def test_reencode_method_uses_x264(self, tmp_path):
        splitter = VideoSplitter("input.mp4", "k.txt", output_dir=str(tmp_path / "out"))
        points = self._make_points()

        with mock.patch("subprocess.run", return_value=mock.MagicMock(returncode=0)) as run, \
             mock.patch("os.path.exists", return_value=True), \
             mock.patch("os.path.getsize", return_value=1024):
            splitter.split_video(points, method="reencode")

        cmd = run.call_args_list[0].args[0]
        assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "libx264"
        assert "-crf" in cmd

    def test_ffmpeg_failure_is_skipped(self, tmp_path):
        """ffmpeg 返回非 0 或抛异常时，该段跳过不中断"""
        splitter = VideoSplitter("input.mp4", "k.txt", output_dir=str(tmp_path / "out"))
        points = self._make_points()

        with mock.patch("subprocess.run", return_value=mock.MagicMock(returncode=1)):
            files = splitter.split_video(points)
        assert files == []

        with mock.patch("subprocess.run", side_effect=RuntimeError("ffmpeg missing")):
            files = splitter.split_video(points)
        assert files == []

    def test_output_dir_created(self, tmp_path):
        out = tmp_path / "nested" / "out"
        VideoSplitter("input.mp4", "k.txt", output_dir=str(out))
        assert out.exists()

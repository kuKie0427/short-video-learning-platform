"""
SpeechToText 纯逻辑测试（不依赖 torch/funasr 模型）

覆盖:音频提取（ffmpeg 命令构造与失败处理）、长段切分、音频裁剪。
实例化时 monkeypatch torch 为非 None（无重型依赖环境）。
"""
import pytest
from unittest import mock

import services.split.app.services.smart_split.speech_to_text as stt_mod


@pytest.fixture
def stt(tmp_path, monkeypatch):
    """构造实例（绕过 torch 缺失检查）"""
    monkeypatch.setattr(stt_mod, "torch", mock.MagicMock())
    return stt_mod.SpeechToText(model_path=str(tmp_path / "model"), vad_model_path="fsmn-vad")


@pytest.mark.unit
class TestExtractAudio:
    """ffmpeg 音频提取"""

    def test_extract_audio_success_builds_command(self, stt, tmp_path):
        video = tmp_path / "in.mp4"
        audio = tmp_path / "out.wav"
        with mock.patch("subprocess.run", return_value=mock.MagicMock()) as run:
            result = stt.extract_audio(str(video), str(audio))

        assert result == str(audio)
        cmd = run.call_args.args[0]
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert "-ar" in cmd and cmd[cmd.index("-ar") + 1] == "16000"
        assert "-acodec" in cmd
        assert "-y" in cmd

    def test_extract_audio_failure_returns_none(self, stt, tmp_path):
        with mock.patch(
            "subprocess.run",
            side_effect=__import__("subprocess").CalledProcessError(1, "ffmpeg")
        ):
            result = stt.extract_audio("in.mp4", "out.wav")

        assert result is None


@pytest.mark.unit
class TestSplitLongSegments:
    """长语音段切分"""

    def test_segment_within_limit_unchanged(self, stt):
        segments = [(0, 5000)]
        assert stt.split_long_segments(segments, max_duration_ms=10000) == [[0, 5000]]

    def test_long_segment_split(self, stt):
        """超过 10 秒的段被按 10 秒切分（入参为 (start, end) 元组列表）"""
        segments = [(0, 25000)]
        result = stt.split_long_segments(segments, max_duration_ms=10000)

        assert len(result) >= 2
        # 每段时长不超过上限，且时间连续覆盖
        for seg in result:
            assert seg[1] - seg[0] <= 10000
        assert result[0][0] == 0
        assert result[-1][1] == 25000


@pytest.mark.unit
class TestCropAudio:
    """音频裁剪"""

    def test_crop_slices_bytes(self, stt):
        audio_data = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
        # 时间为毫秒: 1000ms-3000ms, sample_rate=1Hz → 字节 [1:3]
        result = stt.crop_audio(audio_data, 1000, 3000, sample_rate=1)
        assert result == b"\x01\x02"

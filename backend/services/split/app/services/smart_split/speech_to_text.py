import os
import json
import subprocess

# 重型 AI 依赖为可选：未安装时导入不失败，实例化时给出明确错误
try:
    import torch
    import soundfile as sf
except ImportError as e:
    torch = None
    sf = None
    _AI_DEPS_ERROR = f"缺少 AI 依赖(torch/soundfile): {e}"
else:
    _AI_DEPS_ERROR = None


class SpeechToText:
    def __init__(self, model_path="/app/SenseVoiceSmall", vad_model_path="fsmn-vad"):
        if torch is None:
            raise ImportError(_AI_DEPS_ERROR)
        self.model_path = model_path
        self.vad_model_path = vad_model_path
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

    def extract_audio(self, video_path, audio_path):
        """从视频提取音频"""
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1',
            audio_path, '-y'
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return audio_path
        except subprocess.CalledProcessError as e:
            print(f"音频提取失败: {e}")
            return None

    def process_audio(self, audio_path, output_file):
        """语音转文字"""
        try:
            from funasr import AutoModel
            from funasr.utils.postprocess_utils import rich_transcription_postprocess
            
            # 加载VAD模型
            vad_model = AutoModel(
                model=self.vad_model_path,
                trust_remote_code=True,
                device=self.device,
                disable_update=True
            )
            
            # VAD语音活动检测
            vad_res = vad_model.generate(
                input=audio_path,
                cache={},
                max_single_segment_time=10000,
                min_single_segment_time=500,
                speech_trim_time=100,
                batch_size_s=60,
            )
            
            segments = self.split_long_segments(vad_res[0]['value'], max_duration_ms=10000)
            audio_data, sample_rate = sf.read(audio_path)
            
            # 加载STT模型
            model = AutoModel(
                model=self.model_path,
                trust_remote_code=True,
                device=self.device,
                disable_update=True
            )
            
            results = []
            for idx, segment in enumerate(segments):
                start_time, end_time = segment
                cropped_audio = self.crop_audio(audio_data, start_time, end_time, sample_rate)
                temp_audio_file = "temp_audio.wav"
                sf.write(temp_audio_file, cropped_audio, sample_rate)
                
                res = model.generate(
                    input=temp_audio_file,
                    cache={},
                    language="auto",
                    use_itn=True,
                    batch_size_s=60,
                    merge_vad=False,
                    merge_length_s=0
                )
                
                text = rich_transcription_postprocess(res[0]['text'])
                results.append({
                    "start": start_time // 1000,
                    "end": end_time // 1000,
                    "text": text
                })
            
            if os.path.exists("temp_audio.wav"):
                os.remove("temp_audio.wav")
            
            with open(output_file, "w", encoding="utf-8") as f:
                for result in results:
                    f.write(json.dumps(result, ensure_ascii=False) + '\n')
            
            return output_file
        except Exception as e:
            print(f"语音转文字失败: {e}")
            return None

    def split_long_segments(self, segments, max_duration_ms=10000):
        new_segments = []
        for start, end in segments:
            duration = end - start
            if duration <= max_duration_ms:
                new_segments.append([start, end])
            else:
                num_parts = int(duration / max_duration_ms) + 1
                part_duration = duration / num_parts
                for i in range(num_parts):
                    part_start = start + i * part_duration
                    part_end = min(end, start + (i + 1) * part_duration)
                    if part_end - part_start >= 500:
                        new_segments.append([int(part_start), int(part_end)])
        return new_segments

    def crop_audio(self, audio_data, start_time, end_time, sample_rate):
        start_sample = int(start_time * sample_rate / 1000)
        end_sample = int(end_time * sample_rate / 1000)
        return audio_data[start_sample:end_sample]

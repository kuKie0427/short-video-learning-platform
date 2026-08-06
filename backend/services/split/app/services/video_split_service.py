"""
视频拆分服务抽象层
支持模拟服务和实际视频分割服务集成
"""
import os
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class VideoSplitServiceInterface(ABC):
    """视频拆分服务接口"""
    
    @abstractmethod
    def split_video(
        self,
        video_path: str,
        split_mode: str,
        auto_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """拆分视频
        
        Args:
            video_path: 视频文件路径
            split_mode: 拆分模式（auto/manual/scene）
            auto_config: 自动配置参数
            
        Returns:
            拆分片段列表，每个片段包含：
            - segment_index: 片段索引
            - start_time: 开始时间（秒）
            - end_time: 结束时间（秒）
            - duration: 时长（秒）
            - thumbnail_url: 缩略图URL（可选）
            - scene_type: 场景类型（可选）
            - confidence: 置信度（可选）
        """
        pass
    
    @abstractmethod
    def get_video_duration(self, video_path: str) -> int:
        """获取视频时长
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频时长（秒）
        """
        pass


class MockVideoSplitService(VideoSplitServiceInterface):
    """模拟视频拆分服务（用于开发和测试）"""
    
    def __init__(self, default_segment_duration: int = 60):
        """初始化模拟服务
        
        Args:
            default_segment_duration: 默认片段时长（秒）
        """
        self.default_segment_duration = default_segment_duration
        logger.info("使用模拟视频拆分服务")
    
    def split_video(
        self,
        video_path: str,
        split_mode: str,
        auto_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """模拟拆分视频"""
        # 模拟获取视频时长（实际应该使用ffprobe等工具）
        total_duration = self.get_video_duration(video_path)
        
        # 根据拆分模式生成片段
        segments = []
        segment_duration = auto_config.get('segment_duration', self.default_segment_duration) if auto_config else self.default_segment_duration
        
        segment_index = 0
        current_time = 0
        
        while current_time < total_duration:
            start_time = current_time
            end_time = min(current_time + segment_duration, total_duration)
            duration = end_time - start_time
            
            segments.append({
                'segment_index': segment_index,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'thumbnail_url': f"/thumbnails/segment_{segment_index}.jpg",
                'scene_type': 'auto' if split_mode == 'auto' else 'manual',
                'confidence': 0.85 if split_mode == 'auto' else 1.0
            })
            
            segment_index += 1
            current_time = end_time
        
        logger.info(f"模拟拆分完成，生成 {len(segments)} 个片段")
        return segments
    
    def get_video_duration(self, video_path: str) -> int:
        """模拟获取视频时长"""
        # 实际项目中应该使用ffprobe等工具获取真实时长
        # 这里返回一个模拟值（5分钟）
        return 300


class RealVideoSplitService(VideoSplitServiceInterface):
    """实际视频拆分服务（使用FFmpeg）"""
    
    def __init__(self, output_dir: str = "output_splited_videos"):
        """初始化实际服务
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("使用实际视频拆分服务")
        
        # 检查FFmpeg是否可用
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """检查FFmpeg是否安装"""
        import shutil
        if not shutil.which("ffmpeg"):
            raise RuntimeError("FFmpeg未安装，请先安装FFmpeg")
        if not shutil.which("ffprobe"):
            raise RuntimeError("ffprobe未安装，请先安装FFmpeg")
        logger.info("FFmpeg检查通过")
    
    def get_video_duration(self, video_path: str) -> int:
        """获取视频实际时长（使用ffprobe）"""
        import subprocess
        import json
        
        try:
            # 使用ffprobe获取视频信息
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # 解析JSON输出
            probe_data = json.loads(result.stdout)
            duration = float(probe_data.get("format", {}).get("duration", 0))
            
            return int(duration)
        
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe执行失败: {e.stderr}")
            raise RuntimeError(f"无法获取视频时长: {e.stderr}")
        except json.JSONDecodeError as e:
            logger.error(f"解析ffprobe输出失败: {e}")
            raise RuntimeError("无法解析视频信息")
        except Exception as e:
            logger.error(f"获取视频时长失败: {e}", exc_info=True)
            raise RuntimeError(f"获取视频时长失败: {str(e)}")
    
    def split_video(
        self,
        video_path: str,
        split_mode: str,
        auto_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """实际拆分视频（使用FFmpeg）"""
        import subprocess
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        # 获取视频时长
        total_duration = self.get_video_duration(video_path)
        logger.info(f"视频总时长: {total_duration}秒")
        
        # 确定拆分点
        if split_mode == "auto" and auto_config:
            segment_duration = auto_config.get('segment_duration', 60)
            min_duration = auto_config.get('min_duration', 30)
            max_duration = auto_config.get('max_duration', 180)
        else:
            segment_duration = 60
            min_duration = 30
            max_duration = 180
        
        # 计算拆分点
        split_points = []
        current_time = 0
        segment_index = 0
        
        while current_time < total_duration:
            start_time = current_time
            end_time = min(current_time + segment_duration, total_duration)
            duration = end_time - start_time
            
            # 确保片段时长在合理范围内
            if duration < min_duration and current_time > 0:
                # 合并到上一个片段
                if split_points:
                    last_segment = split_points[-1]
                    last_segment['end_time'] = end_time
                    last_segment['duration'] = end_time - last_segment['start_time']
                    current_time = end_time
                    continue
            
            if duration > max_duration:
                end_time = start_time + max_duration
                duration = max_duration
            
            split_points.append({
                'segment_index': segment_index,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration
            })
            
            segment_index += 1
            current_time = end_time
        
        # 执行视频拆分
        segments = []
        video_name = Path(video_path).stem
        
        for segment_info in split_points:
            segment_index = segment_info['segment_index']
            start_time = segment_info['start_time']
            end_time = segment_info['end_time']
            duration = segment_info['duration']
            
            # 输出文件路径
            output_file = self.output_dir / f"{video_name}_segment_{segment_index}.mp4"
            thumbnail_file = self.output_dir / f"{video_name}_segment_{segment_index}_thumb.jpg"
            
            try:
                # 使用FFmpeg拆分视频
                cmd = [
                    "ffmpeg",
                    "-i", video_path,
                    "-ss", str(start_time),
                    "-t", str(duration),
                    "-c", "copy",  # 使用流复制，速度快
                    "-avoid_negative_ts", "make_zero",
                    "-y",  # 覆盖输出文件
                    str(output_file)
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # 生成缩略图（从片段中间位置）
                thumbnail_time = start_time + duration / 2
                thumbnail_cmd = [
                    "ffmpeg",
                    "-i", video_path,
                    "-ss", str(thumbnail_time),
                    "-vframes", "1",
                    "-y",
                    str(thumbnail_file)
                ]
                
                subprocess.run(
                    thumbnail_cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                segments.append({
                    'segment_index': segment_index,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': duration,
                    'thumbnail_url': f"/thumbnails/{thumbnail_file.name}",
                    'video_url': f"/videos/{output_file.name}",
                    'scene_type': split_mode,
                    'confidence': 0.9
                })
                
                logger.info(f"片段 {segment_index} 拆分成功: {start_time}s - {end_time}s")
            
            except subprocess.CalledProcessError as e:
                logger.error(f"拆分片段 {segment_index} 失败: {e.stderr}")
                # 继续处理其他片段
                continue
            except Exception as e:
                logger.error(f"拆分片段 {segment_index} 时发生错误: {e}", exc_info=True)
                continue
        
        logger.info(f"视频拆分完成，共生成 {len(segments)} 个片段")
        return segments


def get_video_split_service() -> VideoSplitServiceInterface:
    """获取视频拆分服务实例（工厂函数）"""
    # 从环境变量读取服务类型
    service_type = os.getenv("VIDEO_SPLIT_SERVICE_TYPE", "mock")
    
    if service_type == "real":
        # 使用实际服务
        output_dir = os.getenv("VIDEO_SPLIT_OUTPUT_DIR", "output_splited_videos")
        return RealVideoSplitService(output_dir=output_dir)
    elif service_type == "smart":
        # 使用智能拆分服务
        try:
            from .smart_split_service import SmartSplitService
            output_dir = os.getenv("VIDEO_SPLIT_OUTPUT_DIR", "smart_split_output")
            return SmartSplitService(output_dir=output_dir)
        except Exception as e:
            logger.warning(f"智能拆分服务加载失败，回退到模拟服务: {e}")
            segment_duration = int(os.getenv("VIDEO_SPLIT_SEGMENT_DURATION", "60"))
            return MockVideoSplitService(default_segment_duration=segment_duration)
    else:
        # 默认使用模拟服务
        segment_duration = int(os.getenv("VIDEO_SPLIT_SEGMENT_DURATION", "60"))
        return MockVideoSplitService(default_segment_duration=segment_duration)


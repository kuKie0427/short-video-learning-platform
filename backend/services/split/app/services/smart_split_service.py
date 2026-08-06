"""
智能视频拆分服务 - 集成版
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from .video_split_service import VideoSplitServiceInterface
from .smart_split.pipeline import SmartSplitPipeline

logger = logging.getLogger(__name__)


class SmartSplitService(VideoSplitServiceInterface):
    """智能视频拆分服务 - 使用完整AI管线"""
    
    def __init__(self, output_dir: str = "smart_split_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"SmartSplitService initialized with output_dir: {output_dir}")
    
    def get_video_duration(self, video_path: str) -> int:
        """获取视频时长"""
        import subprocess
        import json
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            return int(float(data.get("format", {}).get("duration", 0)))
        except Exception:
            return 300
    
    def analyze_video(
        self,
        video_path: str,
        video_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """仅分析视频，不进行实际切割
        
        Args:
            video_path: 视频文件路径
            video_name: 视频名称（用于缓存目录）
            
        Returns:
            分析结果：knowledge_points列表和是否使用fallback
        """
        logger.info(f"开始视频分析: {video_path}")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        if not video_name:
            video_name = Path(video_path).stem
        
        # 检查缓存：如果knowledge_points.txt已存在，直接返回
        knowledge_file = self.output_dir / video_name / "knowledge" / "knowledge_points.txt"
        if knowledge_file.exists():
            logger.info(f"发现缓存的分析结果: {knowledge_file}")
            try:
                knowledge_points = self._parse_knowledge_points_file(str(knowledge_file))
                return {
                    "knowledge_points": knowledge_points,
                    "used_fallback": False,
                    "cached": True
                }
            except Exception as e:
                logger.warning(f"解析缓存文件失败: {e}，重新分析")
        
        try:
            # 获取配置设置
            from common.config.settings import settings
            
            # 调试：检查API密钥是否正确加载
            api_key = settings.GLM_API_KEY
            logger.info(f"使用API密钥 (前4位): {api_key[:4] if api_key else 'None'}...")
            
            # 使用智能拆分管线（仅分析模式）
            pipeline = SmartSplitPipeline(
                output_base_dir=str(self.output_dir),
                glm_api_key=api_key
            )
            
            # 传递video_name确保缓存目录一致
            knowledge_points, used_fallback = pipeline.run(video_path, analysis_only=True, video_name=video_name)
            
            logger.info(f"视频分析完成，生成 {len(knowledge_points)} 个知识点")
            
            # 保存完整分析结果到缓存（用于后续切分复用）
            import json
            from datetime import datetime
            analysis_cache_file = self.output_dir / video_name / "analysis_result.json"
            analysis_cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            analysis_result = {
                "knowledge_points": knowledge_points,
                "used_fallback": used_fallback,
                "video_path": video_path,
                "video_name": video_name,
                "analysis_time": datetime.now().isoformat(),
                "cache_version": "1.0"
            }
            
            try:
                with open(analysis_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(analysis_result, f, ensure_ascii=False, indent=2)
                logger.info(f"分析结果已缓存到: {analysis_cache_file}")
            except Exception as cache_err:
                logger.warning(f"保存分析缓存失败: {cache_err}")
            
            return {
                "knowledge_points": knowledge_points,
                "used_fallback": used_fallback,
                "cached": False
            }
            
        except Exception as e:
            logger.error(f"视频分析失败: {e}", exc_info=True)
            raise
    
    def _parse_knowledge_points_file(self, file_path: str) -> List[Dict[str, Any]]:
        """解析knowledge_points.txt文件"""
        import re
        knowledge_points = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 支持格式：[MM:SS]-[MM:SS] 标题
            pattern = r'\[(\d{2}):(\d{2})\]-\[(\d{2}):(\d{2})\]\s+(.+)'
            match = re.match(pattern, line)
            if match:
                start_min, start_sec = int(match.group(1)), int(match.group(2))
                end_min, end_sec = int(match.group(3)), int(match.group(4))
                title = match.group(5)
                
                start_time = start_min * 60 + start_sec
                end_time = end_min * 60 + end_sec
                
                knowledge_points.append({
                    'id': idx + 1,
                    'title': title,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time
                })
        
        return knowledge_points
    
    def split_video(
        self,
        video_path: str,
        split_mode: str,
        auto_config: Optional[Dict[str, Any]] = None,
        video_id: Optional[str] = None  # 新增：用于缓存匹配的视频ID
    ) -> List[Dict[str, Any]]:
        """智能拆分视频
        
        Args:
            video_path: 视频文件路径
            split_mode: 拆分模式（这里忽略，始终使用智能模式）
            auto_config: 自动配置参数
            video_id: 视频UUID，用于缓存目录匹配
            
        Returns:
            拆分片段列表
        """
        logger.info(f"开始智能拆分: {video_path}")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        # 使用传入的video_id作为缓存目录名，确保与analyze一致
        if video_id:
            video_name = video_id
            logger.info(f"使用传入的video_id作为缓存目录: {video_name}")
        else:
            video_name = Path(video_path).stem
            logger.warning(f"未传入video_id，使用文件名: {video_name}")
        
        # 检查是否存在分析结果缓存
        import json
        analysis_cache_file = self.output_dir / video_name / "analysis_result.json"
        
        if analysis_cache_file.exists():
            logger.info(f"发现分析缓存，跳过重复分析: {analysis_cache_file}")
            try:
                with open(analysis_cache_file, 'r', encoding='utf-8') as f:
                    analysis_result = json.load(f)
                
                # 从缓存的分析结果生成切分片段
                knowledge_points = analysis_result.get('knowledge_points', [])
                logger.info(f"使用缓存分析结果生成切分片段，共 {len(knowledge_points)} 个知识点")
                
                segments = self._generate_segments_from_knowledge_points(knowledge_points)
                logger.info(f"从缓存生成 {len(segments)} 个切分片段")
                return segments
                
            except Exception as cache_err:
                logger.warning(f"读取分析缓存失败，将重新分析: {cache_err}")
        
        try:
            # 获取配置设置
            from common.config.settings import settings
            
            # 使用智能拆分管线（完整模式）
            pipeline = SmartSplitPipeline(
                output_base_dir=str(self.output_dir),
                glm_api_key=settings.GLM_API_KEY
            )
            
            # 传递video_name给pipeline确保缓存一致性
            segments, _ = pipeline.run(video_path, analysis_only=False, video_name=video_name)
            
            logger.info(f"智能拆分完成，生成 {len(segments)} 个片段")
            return segments
            
        except Exception as e:
            logger.error(f"智能拆分失败: {e}", exc_info=True)
            # 如果智能拆分失败，回退到简单拆分
            logger.warning("回退到简单拆分模式")
            return self._fallback_split(video_path, auto_config)
    
    def _generate_segments_from_knowledge_points(self, knowledge_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从知识点生成切分片段（复用分析结果，避免重复分析）"""
        segments = []
        
        for i, kp in enumerate(knowledge_points):
            # 提取时间戳
            start_time = kp.get('start_timestamp', 0)
            end_time = kp.get('end_timestamp', start_time + 60)
            
            # 确保时间戳有效
            if start_time >= end_time:
                end_time = start_time + 60
            
            segment = {
                'segment_index': i,
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'title': kp.get('knowledge_point', f'片段 {i+1}'),
                'scene_type': 'knowledge',
                'confidence': kp.get('confidence', 0.8),
                'thumbnail_url': None
            }
            segments.append(segment)
        
        logger.info(f"从 {len(knowledge_points)} 个知识点生成了 {len(segments)} 个切分片段")
        return segments
    
    def _fallback_split(self, video_path: str, auto_config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """回退拆分方案"""
        total_duration = self.get_video_duration(video_path)
        segment_duration = 60
        if auto_config:
            segment_duration = auto_config.get('segment_duration', 60)
        
        segments = []
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
                'scene_type': 'fallback',
                'confidence': 0.5
            })
            
            segment_index += 1
            current_time = end_time
        
        return segments

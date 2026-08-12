import os
import logging
from pathlib import Path
from typing import List, Dict, Any

# AI 重型组件为可选依赖：未安装 torch/opencv 时仍可构造管线（仅降级模式可用）
try:
    from .keyframe_extractor import KeyframeExtractor, cv2 as _keyframe_cv2
    from .speech_to_text import SpeechToText, torch as _stt_torch
    # 组件可 import 不代表依赖可用（cv2/torch 可能为 None），据此计算真实可用性
    _AI_DEPS_AVAILABLE = _keyframe_cv2 is not None and _stt_torch is not None
except ImportError:
    KeyframeExtractor = None
    SpeechToText = None
    _AI_DEPS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("未安装 AI 重型依赖(torch/opencv 等)，智能切分管线仅支持降级模式")

from .knowledge_analyzer import KnowledgePointAnalyzer
from .video_splitter import VideoSplitter

logger = logging.getLogger(__name__)

class SmartSplitPipeline:
    """智能视频拆分管线 - 整合所有步骤"""
    
    def __init__(self, output_base_dir="./smart_split_output", glm_api_key=None):
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # 未显式传入时从配置读取（不内置默认密钥）；未配置时 GLM 知识点分析自动走降级切分
        if glm_api_key is None:
            from common.config.settings import settings
            glm_api_key = settings.GLM_API_KEY
        
        self.glm_api_key = glm_api_key
        
    def run(self, video_path: str, analysis_only: bool = False, video_name: str = None):
        """运行智能拆分流程
        
        Args:
            video_path: 视频文件路径
            analysis_only: 是否仅分析（不切割视频）
            video_name: 缓存目录名（UUID），确保分析和切分使用相同缓存
            
        Returns:
            如果analysis_only=True: (knowledge_points列表, used_fallback标志)
            如果analysis_only=False: (segments列表, used_fallback标志)
        """
        if video_name is None:
            video_name = Path(video_path).stem
            logger.warning(f"未传入video_name，使用文件名: {video_name}")
        else:
            logger.info(f"使用传入的video_name作为缓存目录: {video_name}")
        logger.info(f"开始智能{'分析' if analysis_only else '拆分'}流程: {video_path}")

        # 智能模式需要重型 AI 依赖（torch/opencv），缺失时给出明确错误
        if not _AI_DEPS_AVAILABLE:
            raise ImportError(
                "未安装 AI 重型依赖(torch/opencv/funasr)，无法执行智能切分，"
                "请安装 services/split/requirements.txt 或使用降级模式"
            )
        
        # 创建临时工作目录（使用传入的video_name而非从路径提取）
        work_dir = self.output_base_dir / video_name
        work_dir.mkdir(parents=True, exist_ok=True)
        
        audio_dir = work_dir / "audio"
        keyframes_dir = work_dir / "keyframes"
        stt_dir = work_dir / "stt"
        knowledge_dir = work_dir / "knowledge"
        videos_dir = work_dir / "videos"
        
        for d in [audio_dir, keyframes_dir, stt_dir, knowledge_dir, videos_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # 检查是否存在知识点缓存（避免重复分析）
        knowledge_file = knowledge_dir / "knowledge_points.txt"
        knowledge_points = None
        used_fallback = False
        
        if knowledge_file.exists() and not analysis_only:
            # 完整切分模式且已有缓存，直接加载知识点跳到步骤5
            logger.info(f"✓ 检测到知识点缓存，跳过重复分析（步骤1-4）: {knowledge_file}")
            try:
                knowledge_points = self._parse_knowledge_points_file(str(knowledge_file))
                logger.info(f"✓ 成功加载 {len(knowledge_points)} 个缓存知识点，直接进入切分")
            except Exception as parse_err:
                logger.warning(f"解析缓存失败，将重新分析: {parse_err}")
                knowledge_points = None
        
        try:
            # 如果没有缓存或解析失败，执行完整分析
            if knowledge_points is None:
                # 步骤1: 提取音频
                logger.info("步骤1: 提取音频")
                audio_path = audio_dir / f"{video_name}.wav"
                stt_processor = SpeechToText()
                audio_file = stt_processor.extract_audio(video_path, str(audio_path))
                if not audio_file:
                    raise RuntimeError("音频提取失败")
                
                # 步骤2: 语音转文字
                logger.info("步骤2: 语音转文字")
                stt_output = stt_dir / "output.txt"
                stt_result = stt_processor.process_audio(audio_file, str(stt_output))
                if not stt_result:
                    raise RuntimeError("语音转文字失败")
                
                # 步骤3: 提取关键帧
                logger.info("步骤3: 提取关键帧")
                extractor = KeyframeExtractor(
                    video_path=video_path,
                    output_dir=str(keyframes_dir),
                    interval=1,
                    threshold=0.15,
                    strategy='all'
                )
                keyframes = extractor.run()
                
                # 步骤4: GLM知识点分析
                logger.info("步骤4: GLM知识点分析")
                logger.info(f"使用API密钥 (前4位): {self.glm_api_key[:4] if self.glm_api_key else 'None'}...")
                analyzer = KnowledgePointAnalyzer(
                    stt_output_path=str(stt_output),
                    image_folder_path=str(keyframes_dir),
                    api_key=self.glm_api_key,
                    time_window=30,
                    max_direct_images=8,
                    max_speech_segments=50
                )
                knowledge_points = analyzer.analyze_knowledge_points()
                
                # 检查是否使用了fallback（通过scene_type判断）
                used_fallback = len(knowledge_points) > 0 and knowledge_points[0].get('title', '').startswith('片段')
                
                # 保存知识点
                with open(knowledge_file, 'w', encoding='utf-8') as f:
                    for kp in knowledge_points:
                        start_min = int(kp['start_time'] // 60)
                        start_sec = int(kp['start_time'] % 60)
                        end_min = int(kp['end_time'] // 60)
                        end_sec = int(kp['end_time'] % 60)
                        title = kp.get('content') or kp.get('title', '未命名')
                        f.write(f"[{start_min:02d}:{start_sec:02d}]-[{end_min:02d}:{end_sec:02d}] {title}\n")
            
            # 如果仅分析模式，返回知识点列表
            if analysis_only:
                logger.info(f"分析完成，生成 {len(knowledge_points)} 个知识点")
                # 转换为前端需要的格式
                formatted_points = []
                for idx, kp in enumerate(knowledge_points):
                    formatted_points.append({
                        'id': idx + 1,
                        'title': kp.get('content') or kp.get('title', '未命名'),
                        'start_time': kp['start_time'],
                        'end_time': kp['end_time'],
                        'duration': kp.get('duration', kp['end_time'] - kp['start_time'])
                    })
                return formatted_points, used_fallback
            
            # 步骤5: 视频分割
            logger.info("步骤5: 视频分割")
            splitter = VideoSplitter(
                video_path=video_path,
                knowledge_file=str(knowledge_file),
                output_dir=str(videos_dir)
            )
            kp_list = splitter.parse_knowledge_points()
            video_files = splitter.split_video(kp_list, method='copy')
            
            # 转换为统一格式
            segments = []
            for idx, vf in enumerate(video_files):
                kp = vf.get('knowledge_point', {})
                segments.append({
                    'segment_index': idx,
                    'start_time': kp.get('start_time', 0),
                    'end_time': kp.get('end_time', 0),
                    'duration': kp.get('duration', 0),
                    'thumbnail_url': None,
                    'video_url': vf.get('path'),
                    'scene_type': 'smart',
                    'confidence': 0.9
                })
            
            logger.info(f"智能拆分完成，生成 {len(segments)} 个片段")
            return segments, used_fallback
            
        except Exception as e:
            logger.error(f"智能拆分失败: {e}", exc_info=True)
            raise
    
    def _parse_knowledge_points_file(self, file_path: str) -> list:
        """解析knowledge_points.txt文件，返回知识点列表"""
        import re
        knowledge_points = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 解析格式: [MM:SS]-[MM:SS] 标题
            match = re.match(r'\[(\d+):(\d+)\]-\[(\d+):(\d+)\]\s+(.+)', line)
            if match:
                start_min, start_sec, end_min, end_sec, title = match.groups()
                start_time = int(start_min) * 60 + int(start_sec)
                end_time = int(end_min) * 60 + int(end_sec)
                
                knowledge_points.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time,
                    'title': title,
                    'content': title
                })
        
        return knowledge_points

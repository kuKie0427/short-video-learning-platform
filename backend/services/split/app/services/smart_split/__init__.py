"""
智能视频拆分模块

包含以下组件:
- KeyframeExtractor: 关键帧提取器
- SpeechToText: 语音转文字处理器
- KnowledgePointAnalyzer: GLM知识点分析器
- VideoSplitter: 视频分割器
- SmartSplitPipeline: 智能拆分管线

注意:keyframe_extractor / speech_to_text 依赖 torch、opencv 等重型 AI 库,
按需导入（from .smart_split.xxx import Xxx）,不在包级导入,
避免无 AI 依赖环境（如仅测试降级路径）启动失败。
"""

__all__ = [
    'KeyframeExtractor',
    'SpeechToText',
    'KnowledgePointAnalyzer',
    'VideoSplitter',
    'SmartSplitPipeline'
]

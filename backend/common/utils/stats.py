"""
统计功能工具
支持播放次数统计和热度分数计算
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from ..database.connection import get_redis

logger = logging.getLogger(__name__)


def record_play_count(video_id: str, user_id: Optional[str] = None):
    """记录视频播放次数
    
    Args:
        video_id: 视频ID
        user_id: 用户ID（可选，用于去重统计）
    """
    redis_client = get_redis()
    if not redis_client:
        logger.warning("Redis客户端不可用，无法记录播放次数")
        return
    
    try:
        # 使用Redis计数器记录播放次数
        play_count_key = f"video:play_count:{video_id}"
        redis_client.incr(play_count_key)
        
        # 设置过期时间（30天）
        redis_client.expire(play_count_key, 30 * 24 * 60 * 60)
        
        # 如果提供了用户ID，记录用户播放记录（用于去重）
        if user_id:
            user_play_key = f"video:user_play:{video_id}:{user_id}"
            redis_client.setex(user_play_key, 24 * 60 * 60, "1")  # 24小时内同一用户只统计一次
        
        logger.debug(f"记录播放次数: video_id={video_id}, user_id={user_id}")
    
    except Exception as e:
        logger.error(f"记录播放次数失败: {e}", exc_info=True)


def get_play_count(video_id: str) -> int:
    """获取视频播放次数
    
    Args:
        video_id: 视频ID
        
    Returns:
        播放次数
    """
    redis_client = get_redis()
    if not redis_client:
        return 0
    
    try:
        play_count_key = f"video:play_count:{video_id}"
        count = redis_client.get(play_count_key)
        return int(count) if count else 0
    except Exception as e:
        logger.error(f"获取播放次数失败: {e}", exc_info=True)
        return 0


def calculate_hot_score(
    play_count: int,
    like_count: int,
    comment_count: int,
    favorite_count: int,
    created_at: datetime,
    base_score: float = 0.0
) -> float:
    """计算热度分数
    
    热度算法：
    hot_score = (play_count * 0.3 + like_count * 0.3 + comment_count * 0.2 + favorite_count * 0.2) * time_decay
    
    Args:
        play_count: 播放次数
        like_count: 点赞数
        comment_count: 评论数
        favorite_count: 收藏数
        created_at: 创建时间
        base_score: 基础分数（可选）
        
    Returns:
        热度分数
    """
    # 计算时间衰减因子（新内容有加成）
    now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.now()
    age_hours = (now - created_at).total_seconds() / 3600
    
    # 时间衰减：24小时内1.5倍，48小时内1.2倍，72小时内1.0倍，之后逐渐衰减
    if age_hours <= 24:
        time_decay = 1.5
    elif age_hours <= 48:
        time_decay = 1.2
    elif age_hours <= 72:
        time_decay = 1.0
    elif age_hours <= 168:  # 7天
        time_decay = 0.8
    elif age_hours <= 720:  # 30天
        time_decay = 0.5
    else:
        time_decay = 0.3
    
    # 计算加权分数
    weighted_score = (
        play_count * 0.3 +
        like_count * 0.3 +
        comment_count * 0.2 +
        favorite_count * 0.2
    )
    
    # 应用时间衰减
    hot_score = (weighted_score + base_score) * time_decay
    
    return round(hot_score, 2)


def get_video_stats(video_id: str) -> dict:
    """获取视频统计信息
    
    Args:
        video_id: 视频ID
        
    Returns:
        统计信息字典
    """
    play_count = get_play_count(video_id)
    
    return {
        "play_count": play_count,
        "video_id": video_id
    }


"""
统计功能单元测试
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from common.utils.stats import (
    record_play_count,
    get_play_count,
    calculate_hot_score,
    get_video_stats
)


@pytest.mark.unit
class TestPlayCount:
    """测试播放次数统计"""
    
    @patch('common.utils.stats.get_redis')
    def test_record_play_count(self, mock_get_redis):
        """测试记录播放次数"""
        mock_redis = Mock()
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.setex.return_value = True
        mock_get_redis.return_value = mock_redis
        
        record_play_count("video-123", "user-456")
        
        mock_redis.incr.assert_called_once()
        mock_redis.expire.assert_called_once()
        mock_redis.setex.assert_called_once()
    
    @patch('common.utils.stats.get_redis')
    def test_get_play_count(self, mock_get_redis):
        """测试获取播放次数"""
        mock_redis = Mock()
        mock_redis.get.return_value = "100"
        mock_get_redis.return_value = mock_redis
        
        count = get_play_count("video-123")
        
        assert count == 100
        mock_redis.get.assert_called_once()
    
    @patch('common.utils.stats.get_redis')
    def test_get_play_count_not_exists(self, mock_get_redis):
        """测试获取不存在的播放次数"""
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis
        
        count = get_play_count("video-123")
        
        assert count == 0
    
    @patch('common.utils.stats.get_redis')
    def test_record_play_count_redis_unavailable(self, mock_get_redis):
        """测试Redis不可用时的处理"""
        mock_get_redis.return_value = None
        
        # 应该不会抛出异常
        record_play_count("video-123", "user-456")


@pytest.mark.unit
class TestHotScore:
    """测试热度分数计算"""
    
    def test_calculate_hot_score_basic(self):
        """测试基础热度分数计算"""
        created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        score = calculate_hot_score(
            play_count=100,
            like_count=50,
            comment_count=20,
            favorite_count=10,
            created_at=created_at
        )
        
        assert score > 0
        assert isinstance(score, float)
    
    def test_calculate_hot_score_time_decay_new(self):
        """测试时间衰减（新内容）"""
        # 24小时内的内容
        created_at_new = datetime.now(timezone.utc) - timedelta(hours=12)
        # 7天前的内容
        created_at_old = datetime.now(timezone.utc) - timedelta(days=7)
        
        score_new = calculate_hot_score(
            play_count=100,
            like_count=50,
            comment_count=20,
            favorite_count=10,
            created_at=created_at_new
        )
        
        score_old = calculate_hot_score(
            play_count=100,
            like_count=50,
            comment_count=20,
            favorite_count=10,
            created_at=created_at_old
        )
        
        # 新内容应该有更高的分数（由于时间衰减因子）
        assert score_new > score_old
    
    def test_calculate_hot_score_zero_interactions(self):
        """测试零互动时的热度分数"""
        created_at = datetime.now(timezone.utc)
        
        score = calculate_hot_score(
            play_count=0,
            like_count=0,
            comment_count=0,
            favorite_count=0,
            created_at=created_at
        )
        
        assert score >= 0
    
    def test_calculate_hot_score_high_interactions(self):
        """测试高互动时的热度分数"""
        created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        score = calculate_hot_score(
            play_count=10000,
            like_count=5000,
            comment_count=2000,
            favorite_count=1000,
            created_at=created_at
        )
        
        assert score > 0
        # 高互动应该有更高的分数
        assert score > 1000
    
    def test_calculate_hot_score_with_base_score(self):
        """测试带基础分数的热度计算"""
        created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        score_with_base = calculate_hot_score(
            play_count=100,
            like_count=50,
            comment_count=20,
            favorite_count=10,
            created_at=created_at,
            base_score=100.0
        )
        
        score_without_base = calculate_hot_score(
            play_count=100,
            like_count=50,
            comment_count=20,
            favorite_count=10,
            created_at=created_at,
            base_score=0.0
        )
        
        assert score_with_base > score_without_base


@pytest.mark.unit
class TestVideoStats:
    """测试视频统计信息"""
    
    @patch('common.utils.stats.get_play_count')
    def test_get_video_stats(self, mock_get_play_count):
        """测试获取视频统计信息"""
        mock_get_play_count.return_value = 150
        
        stats = get_video_stats("video-123")
        
        assert stats["play_count"] == 150
        assert stats["video_id"] == "video-123"
        mock_get_play_count.assert_called_once_with("video-123")



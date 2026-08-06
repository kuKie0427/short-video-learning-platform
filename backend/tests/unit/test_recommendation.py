"""
推荐算法单元测试
"""
import pytest
from sqlalchemy.orm import Session

from services.content.app.services.recommendation import (
    ContentBasedRecommender,
    CollaborativeFilteringRecommender,
    HybridRecommender,
    PopularityRecommender
)
from common.models import Video, User, Like, Favorite, LearnRecord


class TestContentBasedRecommender:
    """测试基于内容的推荐算法"""
    
    def test_build_user_profile(self, db, test_user, test_video):
        """测试构建用户兴趣画像"""
        # 创建用户行为数据
        like = Like(user_id=test_user.id, video_id=test_video.id)
        db.add(like)
        db.commit()
        
        recommender = ContentBasedRecommender(db, str(test_user.id))
        profile = recommender.build_user_profile()
        
        assert "tags" in profile
        assert "authors" in profile
        assert "languages" in profile
    
    def test_recommend_empty_profile(self, db, test_user):
        """测试空用户画像的推荐"""
        recommender = ContentBasedRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)
        
        # 空画像应该返回基础视频列表
        assert isinstance(videos, list)
    
    def test_filter_videos(self, db, test_user, test_video):
        """测试过滤已看过的视频"""
        # 创建学习记录
        record = LearnRecord(
            user_id=test_user.id,
            video_id=test_video.id,
            status="completed"
        )
        db.add(record)
        db.commit()
        
        recommender = ContentBasedRecommender(db, str(test_user.id))
        videos = recommender.get_base_videos()
        filtered = recommender.filter_videos(videos, exclude_seen=True)
        
        # 应该过滤掉已看过的视频
        video_ids = [str(v.id) for v in filtered]
        assert str(test_video.id) not in video_ids


class TestCollaborativeFilteringRecommender:
    """测试协同过滤推荐算法"""
    
    def test_find_similar_users(self, db, test_user, test_user2, test_video):
        """测试查找相似用户"""
        # 两个用户都喜欢同一个视频
        like1 = Like(user_id=test_user.id, video_id=test_video.id)
        like2 = Like(user_id=test_user2.id, video_id=test_video.id)
        db.add(like1)
        db.add(like2)
        db.commit()
        
        recommender = CollaborativeFilteringRecommender(db, str(test_user.id))
        similar_users = recommender.find_similar_users(limit=5)
        
        assert isinstance(similar_users, list)
    
    def test_recommend_no_similar_users(self, db, test_user):
        """测试没有相似用户时的推荐"""
        recommender = CollaborativeFilteringRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)
        
        # 应该返回基础推荐或空列表
        assert isinstance(videos, list)


class TestHybridRecommender:
    """测试混合推荐算法"""
    
    def test_recommend_hybrid(self, db, test_user, test_video):
        """测试混合推荐"""
        # 创建一些用户行为
        like = Like(user_id=test_user.id, video_id=test_video.id)
        db.add(like)
        db.commit()
        
        recommender = HybridRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)
        
        assert isinstance(videos, list)
    
    def test_recommend_with_weights(self, db, test_user):
        """测试自定义权重的混合推荐"""
        recommender = HybridRecommender(
            db, 
            str(test_user.id),
            content_weight=0.7,
            collaborative_weight=0.3
        )
        videos = recommender.recommend(limit=10)
        
        assert isinstance(videos, list)


class TestPopularityRecommender:
    """测试热度推荐算法"""
    
    def test_recommend_by_popularity(self, db, test_user, test_video):
        """测试基于热度的推荐"""
        # 创建多个点赞
        for i in range(5):
            like = Like(user_id=str(test_user.id), video_id=test_video.id)
            db.add(like)
        db.commit()
        
        recommender = PopularityRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)
        
        assert isinstance(videos, list)
    
    def test_recommend_by_time(self, db, test_user):
        """测试基于时间的推荐"""
        recommender = PopularityRecommender(db, str(test_user.id))
        videos = recommender.recommend_by_time(limit=10, days=7)
        
        assert isinstance(videos, list)


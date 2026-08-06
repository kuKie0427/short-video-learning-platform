"""
智能推荐系统模块
包含多种推荐算法和策略
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
import math
import random

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))
sys.path.append(project_root)

from common.models import User, Video, Like, Favorite, Comment, LearnRecord
from common.utils.redis_client import (
    get_recommendation_cache, set_recommendation_cache, invalidate_recommendation_cache
)


class RecommendationEngine:
    """推荐引擎基类"""
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.cache_duration = timedelta(hours=1)  # 缓存时间
        
    def get_base_videos(self) -> List[Video]:
        """获取基础视频集合"""
        return self.db.query(Video).filter(
            Video.status.in_(["online", "published"]),
            Video.video_type == "short",
            Video.parent_video_id.is_(None)  # 只显示独立视频，不显示子片段
        ).all()
    
    def filter_videos(self, videos: List[Video], exclude_seen: bool = True) -> List[Video]:
        """过滤视频"""
        if not exclude_seen or not self.user_id:
            return videos
        
        # 排除用户已经看过的视频
        seen_video_ids = set()
        
        # 获取用户学习记录中的视频
        learned_videos = self.db.query(LearnRecord).filter(
            LearnRecord.user_id == self.user_id
        ).all()
        seen_video_ids.update(str(record.video_id) for record in learned_videos)
        
        # 获取用户点赞的视频
        liked_videos = self.db.query(Like).filter(
            Like.user_id == self.user_id
        ).all()
        seen_video_ids.update(str(like.video_id) for like in liked_videos)
        
        # 过滤掉已看过的视频
        return [video for video in videos if str(video.id) not in seen_video_ids]


class ContentBasedRecommender(RecommendationEngine):
    """基于内容的推荐算法"""
    
    def __init__(self, db: Session, user_id: str):
        super().__init__(db, user_id)
        
    def build_user_profile(self) -> Dict[str, float]:
        """构建用户兴趣画像"""
        profile = {
            "tags": {},
            "authors": {},
            "languages": {},
            "video_types": {}
        }
        
        # 分析用户历史行为
        behaviors = self._get_user_behaviors()
        
        for behavior_type, videos in behaviors.items():
            weight = self._get_behavior_weight(behavior_type)
            
            for video in videos:
                # 标签权重
                if video.tags:
                    for tag in video.tags:
                        profile["tags"][tag] = profile["tags"].get(tag, 0) + weight
                
                # 作者权重
                author_id = str(video.author_id)
                profile["authors"][author_id] = profile["authors"].get(author_id, 0) + weight
                
                # 语言权重
                profile["languages"][video.language] = profile["languages"].get(video.language, 0) + weight
                
                # 视频类型权重
                profile["video_types"][video.video_type] = profile["video_types"].get(video.video_type, 0) + weight
        
        return profile
    
    def _get_user_behaviors(self) -> Dict[str, List[Video]]:
        """获取用户行为数据"""
        behaviors = {}
        
        # 点赞行为
        liked_videos = self.db.query(Video).join(Like).filter(
            Like.user_id == self.user_id
        ).all()
        behaviors["like"] = liked_videos
        
        # 收藏行为
        favorited_videos = self.db.query(Video).join(Favorite).filter(
            Favorite.user_id == self.user_id
        ).all()
        behaviors["favorite"] = favorited_videos
        
        # 学习行为
        learned_videos = self.db.query(Video).join(LearnRecord).filter(
            LearnRecord.user_id == self.user_id,
            LearnRecord.status.in_(["in_progress", "completed"])
        ).all()
        behaviors["learn"] = learned_videos
        
        return behaviors
    
    def _get_behavior_weight(self, behavior_type: str) -> float:
        """获取行为权重"""
        weights = {
            "like": 1.0,
            "favorite": 1.5,  # 收藏权重更高
            "learn": 2.0      # 学习行为权重最高
        }
        return weights.get(behavior_type, 1.0)
    
    def calculate_similarity(self, video: Video, profile: Dict) -> float:
        """计算视频与用户画像的相似度"""
        similarity = 0.0
        
        # 标签相似度
        if video.tags and profile["tags"]:
            video_tags = set(video.tags)
            profile_tags = set(profile["tags"].keys())
            
            if video_tags and profile_tags:
                tag_overlap = video_tags & profile_tags
                if tag_overlap:
                    # 计算加权标签相似度
                    tag_score = sum(profile["tags"][tag] for tag in tag_overlap)
                    similarity += tag_score * 0.4
        
        # 作者相似度
        author_id = str(video.author_id)
        if author_id in profile["authors"]:
            similarity += profile["authors"][author_id] * 0.3
        
        # 语言相似度
        if video.language in profile["languages"]:
            similarity += profile["languages"][video.language] * 0.2
        
        # 视频类型相似度
        if video.video_type in profile["video_types"]:
            similarity += profile["video_types"][video.video_type] * 0.1
        
        return similarity
    
    def recommend(self, limit: int = 50) -> List[Video]:
        """基于内容的推荐"""
        base_videos = self.get_base_videos()
        profile = self.build_user_profile()
        
        # 计算每个视频的相似度分数
        scored_videos = []
        for video in base_videos:
            score = self.calculate_similarity(video, profile)
            scored_videos.append((video, score))
        
        # 按分数排序
        scored_videos.sort(key=lambda x: x[1], reverse=True)
        
        # 过滤已看过的视频
        filtered_videos = self.filter_videos([v for v, _ in scored_videos])
        
        # 取前limit个
        return filtered_videos[:limit]


class CollaborativeFilteringRecommender(RecommendationEngine):
    """协同过滤推荐算法"""
    
    def __init__(self, db: Session, user_id: str):
        super().__init__(db, user_id)
        
    def find_similar_users(self, k: int = 10, limit: int = None) -> List[str]:
        """寻找相似用户"""
        # 兼容两种参数命名
        if limit is not None:
            k = limit
            
        # 获取目标用户的行为模式
        target_user_pattern = self._get_user_behavior_pattern(self.user_id)
        
        # 获取所有其他用户
        all_users = self.db.query(User).filter(User.id != self.user_id).all()
        
        # 计算用户相似度
        user_similarities = []
        for user in all_users:
            user_pattern = self._get_user_behavior_pattern(str(user.id))
            similarity = self._calculate_user_similarity(target_user_pattern, user_pattern)
            user_similarities.append((str(user.id), similarity))
        
        # 按相似度排序，取前k个
        user_similarities.sort(key=lambda x: x[1], reverse=True)
        return [user_id for user_id, _ in user_similarities[:k]]
    
    def _get_user_behavior_pattern(self, user_id: str) -> Dict[str, Set[str]]:
        """获取用户行为模式"""
        pattern = {
            "liked_videos": set(),
            "favorited_videos": set(),
            "learned_videos": set()
        }
        
        # 点赞的视频
        liked_videos = self.db.query(Like).filter(Like.user_id == user_id).all()
        pattern["liked_videos"] = {str(like.video_id) for like in liked_videos}
        
        # 收藏的视频
        favorited_videos = self.db.query(Favorite).filter(Favorite.user_id == user_id).all()
        pattern["favorited_videos"] = {str(favorite.video_id) for favorite in favorited_videos}
        
        # 学习的视频
        learned_videos = self.db.query(LearnRecord).filter(
            LearnRecord.user_id == user_id,
            LearnRecord.status.in_(["in_progress", "completed"])
        ).all()
        pattern["learned_videos"] = {str(record.video_id) for record in learned_videos}
        
        return pattern
    
    def _calculate_user_similarity(self, pattern1: Dict, pattern2: Dict) -> float:
        """计算用户相似度"""
        similarity = 0.0
        
        # 计算各个行为的相似度
        for behavior_type in ["liked_videos", "favorited_videos", "learned_videos"]:
            set1 = pattern1[behavior_type]
            set2 = pattern2[behavior_type]
            
            if set1 and set2:
                # 使用Jaccard相似度
                intersection = len(set1 & set2)
                union = len(set1 | set2)
                if union > 0:
                    behavior_similarity = intersection / union
                    
                    # 不同行为的权重
                    weights = {
                        "liked_videos": 0.3,
                        "favorited_videos": 0.4,
                        "learned_videos": 0.3
                    }
                    similarity += behavior_similarity * weights[behavior_type]
        
        return similarity
    
    def recommend(self, limit: int = 50) -> List[Video]:
        """协同过滤推荐"""
        # 寻找相似用户
        similar_users = self.find_similar_users()
        
        if not similar_users:
            return []
        
        # 获取相似用户喜欢的视频
        recommended_video_ids = set()
        
        for user_id in similar_users:
            # 获取该用户点赞、收藏、学习的视频
            user_pattern = self._get_user_behavior_pattern(user_id)
            
            for behavior_type in ["liked_videos", "favorited_videos", "learned_videos"]:
                recommended_video_ids.update(user_pattern[behavior_type])
        
        # 排除目标用户已经看过的视频
        target_user_pattern = self._get_user_behavior_pattern(self.user_id)
        seen_videos = (target_user_pattern["liked_videos"] | 
                      target_user_pattern["favorited_videos"] | 
                      target_user_pattern["learned_videos"])
        
        recommended_video_ids = recommended_video_ids - seen_videos
        
        # 获取视频详情
        if not recommended_video_ids:
            return []
        
        videos = self.db.query(Video).filter(
            Video.id.in_(list(recommended_video_ids)),
            Video.status.in_(["online", "published"]),
            Video.video_type == "short"
        ).all()
        
        # 按热度排序
        videos_with_popularity = []
        for video in videos:
            like_count = self.db.query(Like).filter(Like.video_id == video.id).count()
            videos_with_popularity.append((video, like_count))
        
        videos_with_popularity.sort(key=lambda x: x[1], reverse=True)
        
        return [video for video, _ in videos_with_popularity[:limit]]


class HybridRecommender(RecommendationEngine):
    """混合推荐算法"""
    
    def __init__(self, db: Session, user_id: str, content_weight: float = 0.6, collaborative_weight: float = 0.4):
        super().__init__(db, user_id)
        self.content_recommender = ContentBasedRecommender(db, user_id)
        self.collaborative_recommender = CollaborativeFilteringRecommender(db, user_id)
        self.content_weight = content_weight
        self.collaborative_weight = collaborative_weight
        
    def recommend(self, limit: int = 50, strategy: str = "weighted") -> List[Video]:
        """混合推荐"""
        # 获取不同算法的推荐结果
        content_recs = self.content_recommender.recommend(limit * 2)
        collaborative_recs = self.collaborative_recommender.recommend(limit * 2)
        
        if strategy == "weighted":
            return self._weighted_hybrid(content_recs, collaborative_recs, limit)
        elif strategy == "switching":
            return self._switching_hybrid(content_recs, collaborative_recs, limit)
        else:
            return self._cascade_hybrid(content_recs, collaborative_recs, limit)
    
    def _weighted_hybrid(self, content_recs: List[Video], 
                        collaborative_recs: List[Video], 
                        limit: int) -> List[Video]:
        """加权混合"""
        # 给内容推荐和协同过滤推荐分配权重
        all_videos = {}
        
        # 内容推荐权重
        for i, video in enumerate(content_recs):
            video_id = str(video.id)
            if video_id not in all_videos:
                all_videos[video_id] = {"video": video, "score": 0.0}
            # 排名越靠前，权重越高
            all_videos[video_id]["score"] += (len(content_recs) - i) * self.content_weight
        
        # 协同过滤推荐权重
        for i, video in enumerate(collaborative_recs):
            video_id = str(video.id)
            if video_id not in all_videos:
                all_videos[video_id] = {"video": video, "score": 0.0}
            all_videos[video_id]["score"] += (len(collaborative_recs) - i) * self.collaborative_weight
        
        # 按总分排序
        scored_videos = sorted(all_videos.values(), key=lambda x: x["score"], reverse=True)
        
        return [item["video"] for item in scored_videos[:limit]]
    
    def _switching_hybrid(self, content_recs: List[Video], 
                         collaborative_recs: List[Video], 
                         limit: int) -> List[Video]:
        """切换混合"""
        # 根据用户行为历史选择算法
        user_behavior_count = self._get_user_behavior_count()
        
        if user_behavior_count < 10:  # 新用户使用内容推荐
            return content_recs[:limit]
        else:  # 老用户使用协同过滤
            return collaborative_recs[:limit]
    
    def _cascade_hybrid(self, content_recs: List[Video], 
                       collaborative_recs: List[Video], 
                       limit: int) -> List[Video]:
        """级联混合"""
        # 先用内容推荐，再用协同过滤补充
        final_recs = content_recs[:limit]
        
        # 如果内容推荐不足，用协同过滤补充
        if len(final_recs) < limit:
            remaining = limit - len(final_recs)
            # 过滤掉已经推荐的内容
            current_ids = {str(video.id) for video in final_recs}
            additional_recs = [
                video for video in collaborative_recs 
                if str(video.id) not in current_ids
            ][:remaining]
            final_recs.extend(additional_recs)
        
        return final_recs
    
    def _get_user_behavior_count(self) -> int:
        """获取用户行为数量"""
        like_count = self.db.query(Like).filter(Like.user_id == self.user_id).count()
        favorite_count = self.db.query(Favorite).filter(Favorite.user_id == self.user_id).count()
        learn_count = self.db.query(LearnRecord).filter(LearnRecord.user_id == self.user_id).count()
        
        return like_count + favorite_count + learn_count


class PopularityRecommender(RecommendationEngine):
    """基于热度的推荐算法"""
    
    def __init__(self, db: Session, user_id: str):
        super().__init__(db, user_id)
        
    def recommend(self, limit: int = 50, time_window: str = "all") -> List[Video]:
        """基于热度的推荐"""
        # 根据时间窗口过滤
        time_filters = self._get_time_filters(time_window)
        
        # 查询热门视频（综合点赞、评论、收藏）
        # 热度相同时，优先显示最新发布的视频
        query = self.db.query(
            Video,
            (func.count(Like.id) + 
             func.count(Comment.id) * 0.5 + 
             func.count(Favorite.id) * 1.5).label('popularity_score')
        ).outerjoin(Like, Video.id == Like.video_id)\
         .outerjoin(Comment, Video.id == Comment.video_id)\
         .outerjoin(Favorite, Video.id == Favorite.video_id)\
         .filter(
            Video.status.in_(["online", "published"]),
            Video.video_type == "short",
            Video.parent_video_id.is_(None),
            *time_filters
        ).group_by(Video.id).order_by(desc(Video.created_at), desc('popularity_score'))
        
        results = query.limit(limit * 2).all()
        videos = [result[0] for result in results]
        
        # 对于热度推荐，不过滤已看过的视频（让新视频有更多曝光机会）
        # filtered_videos = self.filter_videos(videos)
        
        return videos[:limit]
    
    def _get_time_filters(self, time_window: str):
        """获取时间过滤条件"""
        now = datetime.now()
        
        if time_window == "day":
            return [Video.created_at >= now - timedelta(days=1)]
        elif time_window == "week":
            return [Video.created_at >= now - timedelta(weeks=1)]
        elif time_window == "month":
            return [Video.created_at >= now - timedelta(days=30)]
        else:
            return []
    
    def recommend_by_time(self, limit: int = 50, time_window: str = "all", days: int = None) -> List[Video]:
        """按时间推荐（与 recommend 相同，只是提供更直观的方法名）"""
        # 如果指定了 days 参数，转换为 time_window
        if days is not None:
            if days <= 1:
                time_window = "day"
            elif days <= 7:
                time_window = "week"
            else:
                time_window = "month"
        return self.recommend(limit=limit, time_window=time_window)


class RecommendationService:
    """推荐服务管理器"""
    
    def __init__(self, db: Session):
        self.db = db
        self.cache_expire_seconds = 3600  # 缓存1小时
        
    def get_recommendations(self, user_id: str, strategy: str = "hybrid", 
                          limit: int = 50) -> List[Video]:
        """获取推荐视频（带缓存）"""
        
        # 尝试从缓存获取
        cached_video_ids = get_recommendation_cache(user_id, strategy)
        if cached_video_ids:
            # 从缓存中获取视频ID列表，查询视频对象
            videos = self.db.query(Video).filter(
                Video.id.in_(cached_video_ids[:limit]),
                Video.status.in_(["online", "published"]),
                Video.video_type == "short"
            ).all()
            
            # 保持缓存中的顺序
            video_dict = {str(video.id): video for video in videos}
            ordered_videos = [
                video_dict[vid] for vid in cached_video_ids[:limit] 
                if vid in video_dict
            ]
            
            if ordered_videos:
                return ordered_videos
        
        # 缓存未命中，计算推荐结果
        if strategy == "content":
            recommender = ContentBasedRecommender(self.db, user_id)
        elif strategy == "collaborative":
            recommender = CollaborativeFilteringRecommender(self.db, user_id)
        elif strategy == "popularity":
            recommender = PopularityRecommender(self.db, user_id)
        else:  # hybrid
            recommender = HybridRecommender(self.db, user_id)
        
        videos = recommender.recommend(limit)
        
        # 将结果存入缓存
        if videos:
            video_ids = [str(video.id) for video in videos]
            set_recommendation_cache(user_id, strategy, video_ids, self.cache_expire_seconds)
        
        return videos
    
    def get_diverse_recommendations(self, user_id: str, 
                                  strategies: List[str] = None,
                                  limit_per_strategy: int = 10,
                                  limit: int = None) -> List[Video]:
        """获取多样化推荐"""
        if strategies is None:
            strategies = ["content", "collaborative", "popularity"]
        
        # 如果指定了 limit 参数，计算每个策略的数量
        if limit is not None:
            limit_per_strategy = max(1, limit // len(strategies))
        
        all_recommendations = []
        
        for strategy in strategies:
            recommendations = self.get_recommendations(user_id, strategy, limit_per_strategy)
            all_recommendations.extend(recommendations)
        
        # 去重并随机排序以增加多样性
        unique_recommendations = list({str(video.id): video for video in all_recommendations}.values())
        random.shuffle(unique_recommendations)
        
        # 如果指定了总数限制，进行截断
        if limit is not None:
            return unique_recommendations[:limit]
        
        return unique_recommendations
    
    def update_user_preferences(self, user_id: str, video_id: str, 
                              action_type: str, weight: float = 1.0):
        """更新用户偏好（用于实时反馈）"""
        # 使推荐缓存失效，因为用户行为已改变
        invalidate_recommendation_cache(user_id)
        
        # 这里可以实现实时更新用户画像的逻辑
        # 在实际应用中，可以结合缓存和异步处理
        pass
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_, and_
from pydantic import BaseModel
import math

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.append(project_root)

from common.database.connection import get_db
from common.models import User, Video, Like, Favorite, Comment, LearnRecord, Follow
from ..services.recommendation import (
    ContentBasedRecommender, CollaborativeFilteringRecommender,
    HybridRecommender, PopularityRecommender, RecommendationService
)
from common.utils.auth import get_current_user, get_optional_user, get_optional_user, verify_token
from common.utils.response import success_response, error_response, not_found_response

router = APIRouter(prefix="/api/feed", tags=["feed"])

security = HTTPBearer()


def get_video_stats_batch(db: Session, video_ids: List[str]) -> dict:
    """批量获取视频统计信息，避免N+1查询"""
    if not video_ids:
        return {}
    
    # 批量查询点赞数
    like_counts = db.query(
        Like.video_id,
        func.count(Like.id).label('count')
    ).filter(
        Like.video_id.in_(video_ids)
    ).group_by(Like.video_id).all()
    
    like_count_map = {str(video_id): count for video_id, count in like_counts}
    
    # 批量查询评论数
    comment_counts = db.query(
        Comment.video_id,
        func.count(Comment.id).label('count')
    ).filter(
        Comment.video_id.in_(video_ids)
    ).group_by(Comment.video_id).all()
    
    comment_count_map = {str(video_id): count for video_id, count in comment_counts}
    
    # 批量查询收藏数
    favorite_counts = db.query(
        Favorite.video_id,
        func.count(Favorite.id).label('count')
    ).filter(
        Favorite.video_id.in_(video_ids)
    ).group_by(Favorite.video_id).all()
    
    favorite_count_map = {str(video_id): count for video_id, count in favorite_counts}
    
    # 构建统计信息字典
    stats_map = {}
    for video_id in video_ids:
        stats_map[video_id] = {
            "like_count": like_count_map.get(video_id, 0),
            "comment_count": comment_count_map.get(video_id, 0),
            "favorite_count": favorite_count_map.get(video_id, 0)
        }
    
    return stats_map


class VideoFeedResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    tags: Optional[List[str]]
    duration: int
    play_url: str
    cover_url: Optional[str]
    language: str
    status: str
    video_type: str
    author_id: str
    author_nickname: str
    author_avatar: Optional[str]
    like_count: int
    comment_count: int
    favorite_count: int
    is_liked: bool = False
    is_favorited: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True


class FeedResponse(BaseModel):
    videos: List[VideoFeedResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    next_cursor: Optional[str] = None


class SearchResponse(BaseModel):
    videos: List[VideoFeedResponse]
    total: int
    query: str
    search_type: str


# 使用统一的get_current_user函数


@router.get("/my_videos", summary="获取当前用户的视频列表")
async def get_my_videos(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    days: int = Query(None, ge=1, le=30, description="最近几天的视频（可选）"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取当前用户上传的所有视频"""
    
    if not current_user:
        return error_response("需要登录", code=401)
    
    # 查询用户的视频
    query = db.query(Video).filter(Video.author_id == current_user.id)
    
    # 如果指定了天数，只查询最近N天的视频
    if days:
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Video.created_at >= cutoff_date)
    
    # 按创建时间倒序排列（最新的在前面）
    query = query.order_by(desc(Video.created_at))
    
    # 计算总数
    total = query.count()
    
    # 分页
    offset = (page - 1) * page_size
    videos = query.offset(offset).limit(page_size).all()
    
    # 获取视频统计信息
    video_ids = [str(video.id) for video in videos]
    stats_map = get_video_stats_batch(db, video_ids)
    
    # 构建响应数据
    feed_videos = []
    for video in videos:
        video_id_str = str(video.id)
        stats = stats_map.get(video_id_str, {"like_count": 0, "comment_count": 0, "favorite_count": 0})
        
        # 获取long_video_id（如果是长视频）
        long_video_id = None
        if video.video_type == "long" and hasattr(video, 'long_video') and video.long_video:
            # long_video 是一个列表，取第一个
            long_video_id = str(video.long_video[0].id) if len(video.long_video) > 0 else None
        
        feed_videos.append({
            "id": str(video.id),
            "title": video.title,
            "description": video.description,
            "tags": video.tags,
            "duration": video.duration,
            "play_url": video.play_url,
            "cover_url": video.cover_url,
            "language": video.language,
            "status": video.status,
            "video_type": video.video_type,
            "long_video_id": long_video_id,  # 添加long_video_id
            "author_id": str(video.author_id),
            "author_nickname": video.author.nickname,
            "author_avatar": video.author.avatar_url,
            "like_count": stats["like_count"],
            "comment_count": stats["comment_count"],
            "favorite_count": stats["favorite_count"],
            "is_liked": False,  # 自己的视频
            "is_favorited": False,  # 自己的视频
            "created_at": video.created_at.isoformat()
        })
    
    has_next = offset + len(videos) < total
    
    return success_response(data={
        "videos": feed_videos,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": has_next
    })


@router.get("/recommend", summary="智能推荐视频流")
async def get_recommend_feed(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    strategy: str = Query("hybrid", regex="^(hybrid|content|collaborative|popularity)$", description="推荐策略"),
    current_user: Optional[User] = Depends(get_optional_user),  # 开发环境：可选认证
    db: Session = Depends(get_db)
):
    """获取智能推荐视频流"""
    
    # 初始化推荐服务
    recommendation_service = RecommendationService(db)
    
    # 获取推荐视频
    user_id = str(current_user.id) if current_user else None
    recommended_videos = recommendation_service.get_recommendations(
        user_id=user_id,
        strategy=strategy,
        limit=page_size * 5  # 获取更多用于分页
    )
    
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 分页处理
    total = len(recommended_videos)
    videos = recommended_videos[offset:offset + page_size]
    
    # 获取用户互动信息
    video_ids = [str(video.id) for video in videos]
    liked_video_ids = set()
    favorited_video_ids = set()
    
    if current_user:
        # 获取点赞信息
        user_likes = db.query(Like).filter(
            Like.user_id == current_user.id,
            Like.video_id.in_(video_ids)
        ).all()
        liked_video_ids = {str(like.video_id) for like in user_likes}
        
        # 获取收藏信息
        user_favorites = db.query(Favorite).filter(
            Favorite.user_id == current_user.id,
            Favorite.video_id.in_(video_ids)
        ).all()
        favorited_video_ids = {str(favorite.video_id) for favorite in user_favorites}
    
    # 批量获取统计信息，避免N+1查询
    stats_map = get_video_stats_batch(db, video_ids)
    
    # 构建响应数据
    feed_videos = []
    for video in videos:
        video_id_str = str(video.id)
        stats = stats_map.get(video_id_str, {"like_count": 0, "comment_count": 0, "favorite_count": 0})
        
        feed_videos.append({
            "id": str(video.id),
            "title": video.title,
            "description": video.description,
            "tags": video.tags,
            "duration": video.duration,
            "play_url": video.play_url,
            "cover_url": video.cover_url,
            "language": video.language,
            "status": video.status,
            "video_type": video.video_type,
            "author_id": str(video.author_id),
            "author_nickname": video.author.nickname,
            "author_avatar": video.author.avatar_url,
            "like_count": stats["like_count"],
            "comment_count": stats["comment_count"],
            "favorite_count": stats["favorite_count"],
            "is_liked": str(video.id) in liked_video_ids,
            "is_favorited": str(video.id) in favorited_video_ids,
            "created_at": video.created_at.isoformat()
        })
    
    # 计算是否有下一页
    has_next = offset + len(videos) < total
    next_cursor = str(uuid.uuid4()) if has_next else None
    
    return success_response(data={
        "videos": feed_videos,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
        "next_cursor": next_cursor
    })


@router.get("/diverse", summary="多样化推荐")
async def get_diverse_feed(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取多样化推荐视频流（多种算法混合）"""
    
    # 初始化推荐服务
    recommendation_service = RecommendationService(db)
    
    # 获取多样化推荐
    recommended_videos = recommendation_service.get_diverse_recommendations(
        user_id=str(current_user.id),
        limit=page_size * 5
    )
    
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 分页处理
    total = len(recommended_videos)
    videos = recommended_videos[offset:offset + page_size]
    
    # 获取用户互动信息
    video_ids = [str(video.id) for video in videos]
    
    # 获取点赞信息
    user_likes = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.video_id.in_(video_ids)
    ).all()
    liked_video_ids = {str(like.video_id) for like in user_likes}
    
    # 获取收藏信息
    user_favorites = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.video_id.in_(video_ids)
    ).all()
    favorited_video_ids = {str(favorite.video_id) for favorite in user_favorites}
    
    # 批量获取统计信息，避免N+1查询
    stats_map = get_video_stats_batch(db, video_ids)
    
    # 构建响应数据
    feed_videos = []
    for video in videos:
        video_id_str = str(video.id)
        stats = stats_map.get(video_id_str, {"like_count": 0, "comment_count": 0, "favorite_count": 0})
        
        feed_videos.append({
            "id": str(video.id),
            "title": video.title,
            "description": video.description,
            "tags": video.tags,
            "duration": video.duration,
            "play_url": video.play_url,
            "cover_url": video.cover_url,
            "language": video.language,
            "status": video.status,
            "video_type": video.video_type,
            "author_id": str(video.author_id),
            "author_nickname": video.author.nickname,
            "author_avatar": video.author.avatar_url,
            "like_count": stats["like_count"],
            "comment_count": stats["comment_count"],
            "favorite_count": stats["favorite_count"],
            "is_liked": str(video.id) in liked_video_ids,
            "is_favorited": str(video.id) in favorited_video_ids,
            "created_at": video.created_at.isoformat()
        })
    
    # 计算是否有下一页
    has_next = offset + len(videos) < total
    next_cursor = str(uuid.uuid4()) if has_next else None
    
    return success_response(data={
        "videos": feed_videos,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
        "next_cursor": next_cursor
    })


@router.get("/personalized", summary="个性化推荐")
async def get_personalized_feed(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    tags: Optional[str] = Query(None, description="指定标签，多个用逗号分隔"),
    language: Optional[str] = Query(None, description="指定语言"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取个性化推荐视频流（可指定偏好）"""
    
    # 初始化推荐服务
    recommendation_service = RecommendationService(db)
    
    # 获取基础推荐
    recommended_videos = recommendation_service.get_recommendations(
        user_id=str(current_user.id),
        strategy="content",  # 使用内容推荐进行个性化
        limit=page_size * 5
    )
    
    # 如果指定了标签，进行过滤
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        recommended_videos = [
            video for video in recommended_videos 
            if video.tags and any(tag in video.tags for tag in tag_list)
        ]
    
    # 如果指定了语言，进行过滤
    if language:
        recommended_videos = [
            video for video in recommended_videos 
            if video.language == language
        ]
    
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 分页处理
    total = len(recommended_videos)
    videos = recommended_videos[offset:offset + page_size]
    
    # 获取用户互动信息
    video_ids = [str(video.id) for video in videos]
    
    # 获取点赞信息
    user_likes = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.video_id.in_(video_ids)
    ).all()
    liked_video_ids = {str(like.video_id) for like in user_likes}
    
    # 获取收藏信息
    user_favorites = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.video_id.in_(video_ids)
    ).all()
    favorited_video_ids = {str(favorite.video_id) for favorite in user_favorites}
    
    # 批量获取统计信息，避免N+1查询
    stats_map = get_video_stats_batch(db, video_ids)
    
    # 构建响应数据
    feed_videos = []
    for video in videos:
        video_id_str = str(video.id)
        stats = stats_map.get(video_id_str, {"like_count": 0, "comment_count": 0, "favorite_count": 0})
        
        feed_videos.append(VideoFeedResponse(
            id=str(video.id),
            title=video.title,
            description=video.description,
            tags=video.tags,
            duration=video.duration,
            play_url=video.play_url,
            cover_url=video.cover_url,
            language=video.language,
            status=video.status,
            video_type=video.video_type,
            author_id=str(video.author_id),
            author_nickname=video.author.nickname,
            author_avatar=video.author.avatar_url,
            like_count=stats["like_count"],
            comment_count=stats["comment_count"],
            favorite_count=stats["favorite_count"],
            is_liked=str(video.id) in liked_video_ids,
            is_favorited=str(video.id) in favorited_video_ids,
            created_at=video.created_at
        ))
    
    # 计算是否有下一页
    has_next = offset + len(videos) < total
    next_cursor = str(uuid.uuid4()) if has_next else None
    
    # 构建字典格式的响应
    feed_videos_dict = []
    for video_resp in feed_videos:
        feed_videos_dict.append({
            "id": video_resp.id,
            "title": video_resp.title,
            "description": video_resp.description,
            "tags": video_resp.tags,
            "duration": video_resp.duration,
            "play_url": video_resp.play_url,
            "cover_url": video_resp.cover_url,
            "language": video_resp.language,
            "status": video_resp.status,
            "video_type": video_resp.video_type,
            "author_id": video_resp.author_id,
            "author_nickname": video_resp.author_nickname,
            "author_avatar": video_resp.author_avatar,
            "like_count": video_resp.like_count,
            "comment_count": video_resp.comment_count,
            "favorite_count": video_resp.favorite_count,
            "is_liked": video_resp.is_liked,
            "is_favorited": video_resp.is_favorited,
            "created_at": video_resp.created_at.isoformat()
        })
    
    return success_response(data={
        "videos": feed_videos_dict,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
        "next_cursor": next_cursor
    })


class FeedbackRequest(BaseModel):
    video_id: str
    action_type: str  # like, favorite, watch, skip
    feedback_value: Optional[float] = 1.0


@router.post("/feedback", summary="推荐反馈")
async def submit_recommendation_feedback(
    feedback: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """提交推荐反馈（用于优化推荐算法）"""
    
    # 验证视频存在
    video = db.query(Video).filter(Video.id == feedback.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    # 这里可以记录用户的反馈行为
    # 在实际应用中，可以结合缓存和异步处理来更新推荐模型
    
    # 示例：记录用户对推荐视频的反馈
    # 可以存储在专门的推荐反馈表中，用于模型训练
    
    return {"message": "反馈已接收，将用于优化推荐效果"}


@router.get("/following", summary="关注用户视频流")
async def get_following_feed(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取关注用户的视频流"""
    
    offset = (page - 1) * page_size
    
    # 获取当前用户关注的用户ID列表
    following_relations = db.query(Follow).filter(
        Follow.follower_id == current_user.id
    ).all()
    
    following_user_ids = [str(follow.following_id) for follow in following_relations]
    
    if not following_user_ids:
        # 如果没有关注任何用户，返回空列表
        return success_response(data={
            "videos": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "has_next": False,
            "next_cursor": None
        })
    
    # 查询关注用户发布的视频
    query = db.query(Video).filter(
        Video.author_id.in_(following_user_ids),
        Video.status == "online",
        Video.video_type == "short"
    ).order_by(desc(Video.created_at))
    
    # 获取总数
    total = query.count()
    
    # 获取视频列表
    videos = query.offset(offset).limit(page_size).all()
    
    # 获取用户互动信息
    video_ids = [str(video.id) for video in videos]
    
    # 获取点赞信息
    user_likes = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.video_id.in_(video_ids)
    ).all()
    liked_video_ids = {str(like.video_id) for like in user_likes}
    
    # 获取收藏信息
    user_favorites = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.video_id.in_(video_ids)
    ).all()
    favorited_video_ids = {str(favorite.video_id) for favorite in user_favorites}
    
    # 批量获取统计信息，避免N+1查询
    stats_map = get_video_stats_batch(db, video_ids)
    
    # 构建响应数据
    feed_videos = []
    for video in videos:
        video_id_str = str(video.id)
        stats = stats_map.get(video_id_str, {"like_count": 0, "comment_count": 0, "favorite_count": 0})
        
        feed_videos.append({
            "id": str(video.id),
            "title": video.title,
            "description": video.description,
            "tags": video.tags,
            "duration": video.duration,
            "play_url": video.play_url,
            "cover_url": video.cover_url,
            "language": video.language,
            "status": video.status,
            "video_type": video.video_type,
            "author_id": str(video.author_id),
            "author_nickname": video.author.nickname,
            "author_avatar": video.author.avatar_url,
            "like_count": stats["like_count"],
            "comment_count": stats["comment_count"],
            "favorite_count": stats["favorite_count"],
            "is_liked": str(video.id) in liked_video_ids,
            "is_favorited": str(video.id) in favorited_video_ids,
            "created_at": video.created_at.isoformat()
        })
    
    # 计算是否有下一页
    has_next = offset + len(videos) < total
    next_cursor = str(uuid.uuid4()) if has_next else None
    
    return success_response(data={
        "videos": feed_videos,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
        "next_cursor": next_cursor
    })


@router.get("/hot", summary="热门视频")
async def get_hot_feed(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取热门视频（按点赞数排序）"""
    
    offset = (page - 1) * page_size
    
    # 查询热门视频（按点赞数排序）
    query = db.query(
        Video,
        func.count(Like.id).label('like_count')
    ).outerjoin(
        Like, Video.id == Like.video_id
    ).filter(
        Video.status == "online",
        Video.video_type == "short"
    ).group_by(Video.id).order_by(desc('like_count'))
    
    # 获取总数
    total = query.count()
    
    # 获取视频列表
    results = query.offset(offset).limit(page_size).all()
    videos = [result[0] for result in results]
    
    # 获取用户互动信息（如果已登录）
    video_ids = [str(video.id) for video in videos]
    liked_video_ids = set()
    favorited_video_ids = set()
    
    if current_user:
        user_likes = db.query(Like).filter(
            Like.user_id == current_user.id,
            Like.video_id.in_(video_ids)
        ).all()
        liked_video_ids = {str(like.video_id) for like in user_likes}
        
        user_favorites = db.query(Favorite).filter(
            Favorite.user_id == current_user.id,
            Favorite.video_id.in_(video_ids)
        ).all()
        favorited_video_ids = {str(favorite.video_id) for favorite in user_favorites}
    
    # 批量获取统计信息
    stats_map = get_video_stats_batch(db, video_ids)
    
    # 构建响应数据
    feed_videos = []
    for video in videos:
        video_id_str = str(video.id)
        stats = stats_map.get(video_id_str, {"like_count": 0, "comment_count": 0, "favorite_count": 0})
        
        feed_videos.append({
            "id": str(video.id),
            "title": video.title,
            "description": video.description,
            "tags": video.tags,
            "duration": video.duration,
            "play_url": video.play_url,
            "cover_url": video.cover_url,
            "language": video.language,
            "status": video.status,
            "video_type": video.video_type,
            "author_id": str(video.author_id),
            "author_nickname": video.author.nickname,
            "author_avatar": video.author.avatar_url,
            "like_count": stats["like_count"],
            "comment_count": stats["comment_count"],
            "favorite_count": stats["favorite_count"],
            "is_liked": str(video.id) in liked_video_ids,
            "is_favorited": str(video.id) in favorited_video_ids,
            "created_at": video.created_at.isoformat()
        })
    
    has_next = offset + len(videos) < total
    next_cursor = str(uuid.uuid4()) if has_next else None
    
    return success_response(data={
        "videos": feed_videos,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
        "next_cursor": next_cursor
    })


@router.get("/search", summary="搜索视频")
async def search_videos(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词"),
    search_type: str = Query("all", regex="^(all|title|tag|author)$", description="搜索类型"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """搜索视频"""
    
    offset = (page - 1) * page_size
    
    # 构建搜索查询
    query = db.query(Video).filter(
        Video.status == "online",
        Video.video_type == "short"
    )
    
    # 根据搜索类型添加搜索条件
    search_conditions = []
    if search_type in ["all", "title"]:
        search_conditions.append(Video.title.ilike(f"%{q}%"))
    
    if search_type in ["all", "tag"] and Video.tags is not None:
        # 对于数组字段的搜索
        search_conditions.append(
            Video.tags.any(q)
        )
    
    if search_type in ["all", "author"]:
        search_conditions.append(User.nickname.ilike(f"%{q}%"))
        query = query.join(User, Video.author_id == User.id)
    
    if search_conditions:
        query = query.filter(or_(*search_conditions))
    
    # 获取总数
    total = query.count()
    
    # 获取搜索结果
    videos = query.order_by(desc(Video.created_at)).offset(offset).limit(page_size).all()
    
    # 获取用户互动信息（如果已登录）
    video_ids = [str(video.id) for video in videos]
    liked_video_ids = set()
    favorited_video_ids = set()
    
    if current_user:
        user_likes = db.query(Like).filter(
            Like.user_id == current_user.id,
            Like.video_id.in_(video_ids)
        ).all()
        liked_video_ids = {str(like.video_id) for like in user_likes}
        
        user_favorites = db.query(Favorite).filter(
            Favorite.user_id == current_user.id,
            Favorite.video_id.in_(video_ids)
        ).all()
        favorited_video_ids = {str(favorite.video_id) for favorite in user_favorites}
    
    # 批量获取统计信息
    stats_map = get_video_stats_batch(db, video_ids)
    
    # 构建响应数据
    search_videos = []
    for video in videos:
        video_id_str = str(video.id)
        stats = stats_map.get(video_id_str, {"like_count": 0, "comment_count": 0, "favorite_count": 0})
        
        search_videos.append({
            "id": str(video.id),
            "title": video.title,
            "description": video.description,
            "tags": video.tags,
            "duration": video.duration,
            "play_url": video.play_url,
            "cover_url": video.cover_url,
            "language": video.language,
            "status": video.status,
            "video_type": video.video_type,
            "author_id": str(video.author_id),
            "author_nickname": video.author.nickname,
            "author_avatar": video.author.avatar_url,
            "like_count": stats["like_count"],
            "comment_count": stats["comment_count"],
            "favorite_count": stats["favorite_count"],
            "is_liked": str(video.id) in liked_video_ids,
            "is_favorited": str(video.id) in favorited_video_ids,
            "created_at": video.created_at.isoformat()
        })
    
    return success_response(data={
        "videos": search_videos,
        "total": total,
        "query": q,
        "search_type": search_type
    })


@router.get("/video/{video_id}", summary="获取视频详情")
async def get_video_detail(
    video_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取视频详情"""
    
    # 查询视频
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.status == "online"
    ).first()
    
    if not video:
        return not_found_response("视频不存在或已被删除")
    
    # 批量获取统计信息，避免N+1查询
    stats_map = get_video_stats_batch(db, [str(video.id)])
    stats = stats_map.get(str(video.id), {"like_count": 0, "comment_count": 0, "favorite_count": 0})
    like_count = stats["like_count"]
    comment_count = stats["comment_count"]
    favorite_count = stats["favorite_count"]
    
    # 获取用户互动状态（如果已登录）
    is_liked = False
    is_favorited = False
    last_position = 0  # 默认从头开始
    
    if current_user:
        is_liked = db.query(Like).filter(
            Like.user_id == current_user.id,
            Like.video_id == video.id
        ).first() is not None
        
        is_favorited = db.query(Favorite).filter(
            Favorite.user_id == current_user.id,
            Favorite.video_id == video.id
        ).first() is not None
        
        # 获取学习记录
        learn_record = db.query(LearnRecord).filter(
            LearnRecord.user_id == current_user.id,
            LearnRecord.video_id == video.id
        ).first()
        
        if learn_record and learn_record.last_position:
            last_position = learn_record.last_position
        elif not learn_record:
            # 创建学习记录（如果不存在）
            learn_record = LearnRecord(
                user_id=current_user.id,
                video_id=video.id,
                status="not_started"
            )
            db.add(learn_record)
            db.commit()
    
    video_data = {
        "id": str(video.id),
        "title": video.title,
        "description": video.description,
        "tags": video.tags,
        "duration": video.duration,
        "play_url": video.play_url,
        "cover_url": video.cover_url,
        "language": video.language,
        "status": video.status,
        "video_type": video.video_type,
        "author_id": str(video.author_id),
        "author_nickname": video.author.nickname,
        "author_avatar": video.author.avatar_url,
        "like_count": like_count,
        "comment_count": comment_count,
        "favorite_count": favorite_count,
        "is_liked": is_liked,
        "is_favorited": is_favorited,
        "last_position": last_position,  # 添加上次播放位置
        "created_at": video.created_at.isoformat()
    }
    
    return success_response(data=video_data)
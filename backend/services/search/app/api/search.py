"""
搜索API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from common.database.connection import get_db
from common.models import User, Video
from common.utils.auth import get_current_user
from common.utils.response import success_response
from common.utils.stats import get_play_count, calculate_hot_score

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/suggest", summary="搜索建议")
async def get_search_suggestions(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词前缀"),
    limit: int = Query(10, ge=1, le=20, description="返回数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取搜索建议"""
    # 简化实现：从视频标题和标签中提取建议
    # 实际项目中应该使用Elasticsearch等搜索引擎
    
    suggestions = []
    
    # 从视频标题中提取建议
    videos = db.query(Video).filter(
        Video.status == "online",
        Video.title.ilike(f"%{q}%")
    ).limit(limit).all()
    
    for video in videos:
        if video.title not in suggestions:
            suggestions.append(video.title)
            if len(suggestions) >= limit:
                break
    
    # 从标签中提取建议（使用PostgreSQL数组操作）
    if len(suggestions) < limit:
        # PostgreSQL数组字段搜索
        from sqlalchemy import func
        all_videos = db.query(Video).filter(
            Video.status == "online",
            Video.tags.isnot(None)
        ).all()
        
        for video in all_videos:
            if video.tags:
                for tag in video.tags:
                    if q.lower() in tag.lower() and tag not in suggestions:
                        suggestions.append(tag)
                        if len(suggestions) >= limit:
                            break
            if len(suggestions) >= limit:
                break
    
    # 获取用户搜索历史（简化版，实际应该从数据库查询）
    history = []
    
    return success_response(
        data={
            "suggestions": suggestions[:limit],
            "history": history
        }
    )


@router.get("/videos", summary="视频搜索")
async def search_videos(
    q: Optional[str] = Query(None, description="关键字"),
    tags: Optional[str] = Query(None, description="标签列表（逗号分隔）"),
    duration_range: Optional[str] = Query(None, description="时长范围"),
    language: Optional[str] = Query(None, description="语言"),
    sort_by: Optional[str] = Query("latest", description="排序方式"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """搜索视频"""
    from sqlalchemy import desc, or_
    from common.models import Like, Favorite, Comment
    
    offset = (page - 1) * page_size
    
    # 构建搜索查询
    query = db.query(Video).filter(
        Video.status == "online",
        Video.video_type == "short"
    )
    
    # 关键字搜索
    if q:
        search_conditions = [
            Video.title.ilike(f"%{q}%"),
            Video.description.ilike(f"%{q}%")
        ]
        query = query.filter(or_(*search_conditions))
    
    # 标签筛选
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        for tag in tag_list:
            query = query.filter(Video.tags.contains([tag]))
    
    # 时长范围筛选
    if duration_range:
        # duration_range格式：060（0-60秒）、60180（60-180秒）等
        if len(duration_range) >= 3:
            min_duration = int(duration_range[:2]) if duration_range[:2].isdigit() else 0
            max_duration = int(duration_range[2:]) if duration_range[2:].isdigit() else None
            if max_duration:
                query = query.filter(
                    Video.duration >= min_duration,
                    Video.duration <= max_duration
                )
    
    # 语言筛选
    if language:
        query = query.filter(Video.language == language)
    
    # 排序
    if sort_by == "latest":
        query = query.order_by(desc(Video.created_at))
    elif sort_by == "hot":
        # 按创建时间排序（实际应该按热度分数排序，但需要在应用层计算）
        query = query.order_by(desc(Video.created_at))
    elif sort_by == "relevance":
        # 按创建时间排序（实际应该按相关性排序）
        query = query.order_by(desc(Video.created_at))
    
    # 获取总数
    total = query.count()
    
    # 获取搜索结果
    videos = query.offset(offset).limit(page_size).all()
    
    # 获取用户互动信息
    video_ids = [str(video.id) for video in videos]
    
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
    
    # 构建响应数据
    items = []
    for video in videos:
        like_count = db.query(Like).filter(Like.video_id == video.id).count()
        comment_count = db.query(Comment).filter(Comment.video_id == video.id).count()
        favorite_count = db.query(Favorite).filter(Favorite.video_id == video.id).count()
        
        # 获取播放次数和计算热度分数
        play_count = get_play_count(str(video.id))
        hot_score = calculate_hot_score(
            play_count=play_count,
            like_count=like_count,
            comment_count=comment_count,
            favorite_count=favorite_count,
            created_at=video.created_at
        )
        
        items.append({
            "video_id": str(video.id),
            "title": video.title,
            "cover_url": video.cover_url,
            "duration": video.duration,
            "author": {
                "id": str(video.author.id),
                "nickname": video.author.nickname,
                "avatar": video.author.avatar_url
            },
            "hot_score": hot_score,
            "stats": {
                "play_count": play_count,
                "like_count": like_count,
                "comment_count": comment_count
            }
        })
    
    return success_response(
        data={
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_more": offset + len(items) < total
            }
        }
    )


import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.append(project_root)

from common.database.connection import get_db
from common.models import User, Video, Like, Favorite, Comment
from common.utils.auth import get_current_user, get_optional_user, verify_token
from common.utils.response import success_response, error_response, not_found_response

router = APIRouter(prefix="/api/interaction", tags=["interaction"])

security = HTTPBearer()


class LikeRequest(BaseModel):
    video_id: str


class LikeResponse(BaseModel):
    success: bool
    like_count: int
    is_liked: bool


class FavoriteRequest(BaseModel):
    video_id: str


class FavoriteResponse(BaseModel):
    success: bool
    favorite_count: int
    is_favorited: bool


class CommentRequest(BaseModel):
    video_id: str
    content: str
    parent_id: Optional[str] = None


class CommentResponse(BaseModel):
    id: str
    video_id: str
    user_id: str
    user_nickname: str
    user_avatar: Optional[str]
    parent_id: Optional[str]
    content: str
    like_count: int
    created_at: datetime
    replies: List['CommentResponse'] = []
    
    class Config:
        from_attributes = True


class CommentsResponse(BaseModel):
    comments: List[CommentResponse]
    total: int


# 使用统一的get_current_user函数


@router.post("/like", summary="点赞/取消点赞视频")
async def toggle_like(
    request: LikeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """点赞或取消点赞视频"""
    
    # 验证视频存在
    video = db.query(Video).filter(
        Video.id == request.video_id,
        Video.status == "online"
    ).first()
    
    if not video:
        return not_found_response("视频不存在")
    
    # 检查是否已点赞
    existing_like = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.video_id == request.video_id
    ).first()
    
    if existing_like:
        # 取消点赞
        db.delete(existing_like)
        is_liked = False
    else:
        # 点赞
        like = Like(
            user_id=current_user.id,
            video_id=request.video_id
        )
        db.add(like)
        is_liked = True
    
    db.commit()
    
    # 获取最新的点赞数
    like_count = db.query(Like).filter(Like.video_id == request.video_id).count()
    
    return success_response(data={
        "success": True,
        "like_count": like_count,
        "is_liked": is_liked
    })


@router.post("/favorite", summary="收藏/取消收藏视频")
async def toggle_favorite(
    request: FavoriteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """收藏或取消收藏视频"""
    
    # 验证视频存在
    video = db.query(Video).filter(
        Video.id == request.video_id,
        Video.status == "online"
    ).first()
    
    if not video:
        return not_found_response("视频不存在")
    
    # 检查是否已收藏
    existing_favorite = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.video_id == request.video_id
    ).first()
    
    if existing_favorite:
        # 取消收藏
        db.delete(existing_favorite)
        is_favorited = False
    else:
        # 收藏
        favorite = Favorite(
            user_id=current_user.id,
            video_id=request.video_id
        )
        db.add(favorite)
        is_favorited = True
    
    db.commit()
    
    # 获取最新的收藏数
    favorite_count = db.query(Favorite).filter(Favorite.video_id == request.video_id).count()
    
    return success_response(data={
        "success": True,
        "favorite_count": favorite_count,
        "is_favorited": is_favorited
    })


@router.post("/comment", summary="发表评论")
async def add_comment(
    request: CommentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """发表评论"""
    
    # 验证视频存在
    video = db.query(Video).filter(
        Video.id == request.video_id,
        Video.status == "online"
    ).first()
    
    if not video:
        return not_found_response("视频不存在")
    
    # 验证父评论存在（如果是回复）
    if request.parent_id:
        parent_comment = db.query(Comment).filter(Comment.id == request.parent_id).first()
        if not parent_comment:
            return not_found_response("父评论不存在")
    
    # 创建评论
    comment = Comment(
        video_id=request.video_id,
        user_id=current_user.id,
        parent_id=request.parent_id,
        content=request.content
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    comment_data = {
        "id": str(comment.id),
        "video_id": str(comment.video_id),
        "user_id": str(comment.user_id),
        "user_nickname": comment.user.nickname,
        "user_avatar": comment.user.avatar_url,
        "parent_id": str(comment.parent_id) if comment.parent_id else None,
        "content": comment.content,
        "like_count": comment.like_count,
        "created_at": comment.created_at.isoformat(),
        "replies": []
    }
    
    return success_response(data=comment_data)


@router.get("/video/{video_id}/comments", summary="获取视频评论列表")
async def get_video_comments(
    video_id: str,
    page: int = 1,
    page_size: int = 20,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取视频评论列表"""
    
    # 验证视频存在
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.status == "online"
    ).first()
    
    if not video:
        return error_response("视频不存在", code=404)
    
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 获取顶级评论（没有父评论的评论）
    top_comments = db.query(Comment).filter(
        Comment.video_id == video_id,
        Comment.parent_id.is_(None)
    ).order_by(desc(Comment.created_at)).offset(offset).limit(page_size).all()
    
    # 获取评论总数
    total = db.query(Comment).filter(
        Comment.video_id == video_id,
        Comment.parent_id.is_(None)
    ).count()
    
    # 构建评论树
    def build_comment_tree(comment):
        # 获取回复
        replies = db.query(Comment).filter(
            Comment.parent_id == comment.id
        ).order_by(Comment.created_at).all()
        
        reply_responses = []
        for reply in replies:
            reply_responses.append(build_comment_tree(reply))
        
        return CommentResponse(
            id=str(comment.id),
            video_id=str(comment.video_id),
            user_id=str(comment.user_id),
            user_nickname=comment.user.nickname,
            user_avatar=comment.user.avatar_url,
            parent_id=str(comment.parent_id) if comment.parent_id else None,
            content=comment.content,
            like_count=comment.like_count,
            created_at=comment.created_at,
            replies=reply_responses
        )
    
    comment_responses = []
    for comment in top_comments:
        comment_data = build_comment_tree(comment)
        comment_responses.append({
            "id": comment_data.id,
            "video_id": comment_data.video_id,
            "user_id": comment_data.user_id,
            "user_nickname": comment_data.user_nickname,
            "user_avatar": comment_data.user_avatar,
            "parent_id": comment_data.parent_id,
            "content": comment_data.content,
            "like_count": comment_data.like_count,
            "created_at": comment_data.created_at.isoformat() if hasattr(comment_data.created_at, 'isoformat') else str(comment_data.created_at),
            "replies": comment_data.replies
        })
    
    return success_response(
        data={
            "comments": comment_responses,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.delete("/comment/{comment_id}", summary="删除评论")
async def delete_comment(
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除评论"""
    
    # 查找评论
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    
    if not comment:
        return not_found_response("评论不存在")
    
    # 验证权限（只能删除自己的评论）
    if comment.user_id != current_user.id:
        return error_response("无权删除此评论", code=403)
    
    # 删除评论及其回复
    db.query(Comment).filter(Comment.parent_id == comment_id).delete()
    db.delete(comment)
    db.commit()
    
    return success_response(data={"success": True, "message": "评论删除成功"})


@router.get("/user/likes", response_model=List[CommentResponse], summary="获取用户点赞的视频")
async def get_user_likes(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户点赞的视频列表"""
    
    offset = (page - 1) * page_size
    
    # 获取用户点赞的视频
    likes = db.query(Like).filter(
        Like.user_id == current_user.id
    ).order_by(desc(Like.created_at)).offset(offset).limit(page_size).all()
    
    # 构建响应数据
    liked_videos = []
    for like in likes:
        video = like.video
        if video.status == "approved":
            like_count = db.query(Like).filter(Like.video_id == video.id).count()
            comment_count = db.query(Comment).filter(Comment.video_id == video.id).count()
            favorite_count = db.query(Favorite).filter(Favorite.video_id == video.id).count()
            
            liked_videos.append(CommentResponse(
                id=str(video.id),
                video_id=str(video.id),
                user_id=str(video.author_id),
                user_nickname=video.author.nickname,
                user_avatar=video.author.avatar_url,
                parent_id=None,
                content=f"用户点赞的视频: {video.title}",
                like_count=like_count,
                created_at=like.created_at,
                replies=[]
            ))
    
    return liked_videos


@router.get("/user/favorites", response_model=List[CommentResponse], summary="获取用户收藏的视频")
async def get_user_favorites(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户收藏的视频列表"""
    
    offset = (page - 1) * page_size
    
    # 获取用户收藏的视频
    favorites = db.query(Favorite).filter(
        Favorite.user_id == current_user.id
    ).order_by(desc(Favorite.created_at)).offset(offset).limit(page_size).all()
    
    # 构建响应数据
    favorited_videos = []
    for favorite in favorites:
        video = favorite.video
        if video.status == "approved":
            like_count = db.query(Like).filter(Like.video_id == video.id).count()
            comment_count = db.query(Comment).filter(Comment.video_id == video.id).count()
            favorite_count = db.query(Favorite).filter(Favorite.video_id == video.id).count()
            
            favorited_videos.append(CommentResponse(
                id=str(video.id),
                video_id=str(video.id),
                user_id=str(video.author_id),
                user_nickname=video.author.nickname,
                user_avatar=video.author.avatar_url,
                parent_id=None,
                content=f"用户收藏的视频: {video.title}",
                like_count=like_count,
                created_at=favorite.created_at,
                replies=[]
            ))
    
    return favorited_videos
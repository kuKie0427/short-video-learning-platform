"""
关注功能API
实现用户关注/取消关注、获取关注列表和粉丝列表
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from pydantic import BaseModel
from datetime import datetime

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.append(project_root)

from common.database.connection import get_db
from common.models import User, Follow
from common.utils.auth import get_current_user, get_optional_user
from common.utils.response import success_response, error_response

router = APIRouter(prefix="/api/follow", tags=["follow"])


class FollowResponse(BaseModel):
    """关注关系响应"""
    id: str
    follower_id: str
    following_id: str
    follower_nickname: str
    follower_avatar: Optional[str]
    following_nickname: str
    following_avatar: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class FollowListResponse(BaseModel):
    """关注列表响应"""
    users: List[FollowResponse]
    total: int
    page: int
    page_size: int


@router.post("/{user_id}", summary="关注用户")
async def follow_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """关注指定用户"""
    
    # 不能关注自己
    if user_id == str(current_user.id):
        return error_response("不能关注自己", code=400)
    
    # 验证目标用户是否存在
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        return error_response("用户不存在", code=404)
    
    # 检查是否已关注
    existing_follow = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()
    
    if existing_follow:
        return error_response("已关注该用户", code=400)
    
    # 创建关注关系
    follow = Follow(
        follower_id=current_user.id,
        following_id=user_id
    )
    
    db.add(follow)
    db.commit()
    db.refresh(follow)
    
    return success_response(
        data={
            "follow_id": str(follow.id),
            "message": "关注成功"
        }
    )


@router.delete("/{user_id}", summary="取消关注")
async def unfollow_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消关注指定用户"""
    
    # 查找关注关系
    follow = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()
    
    if not follow:
        return error_response("未关注该用户", code=404)
    
    # 删除关注关系
    db.delete(follow)
    db.commit()
    
    return success_response(data={"message": "取消关注成功"})


@router.get("/following", summary="获取关注列表")
async def get_following_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户关注的用户列表"""
    
    offset = (page - 1) * page_size
    
    # 查询关注关系
    query = db.query(Follow).filter(
        Follow.follower_id == current_user.id
    ).order_by(desc(Follow.created_at))
    
    total = query.count()
    follows = query.offset(offset).limit(page_size).all()
    
    # 构建响应数据
    follow_responses = []
    for follow in follows:
        following_user = db.query(User).filter(User.id == follow.following_id).first()
        if following_user:
            follow_responses.append({
                "id": str(follow.id),
                "follower_id": str(follow.follower_id),
                "following_id": str(follow.following_id),
                "follower_nickname": current_user.nickname,
                "follower_avatar": current_user.avatar_url,
                "following_nickname": following_user.nickname,
                "following_avatar": following_user.avatar_url,
                "created_at": follow.created_at.isoformat()
            })
    
    return success_response(data={
        "users": follow_responses,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.get("/followers", summary="获取粉丝列表")
async def get_followers_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取关注当前用户的用户列表（粉丝列表）"""
    
    offset = (page - 1) * page_size
    
    # 查询关注关系
    query = db.query(Follow).filter(
        Follow.following_id == current_user.id
    ).order_by(desc(Follow.created_at))
    
    total = query.count()
    follows = query.offset(offset).limit(page_size).all()
    
    # 构建响应数据
    follow_responses = []
    for follow in follows:
        follower_user = db.query(User).filter(User.id == follow.follower_id).first()
        if follower_user:
            follow_responses.append({
                "id": str(follow.id),
                "follower_id": str(follow.follower_id),
                "following_id": str(follow.following_id),
                "follower_nickname": follower_user.nickname,
                "follower_avatar": follower_user.avatar_url,
                "following_nickname": current_user.nickname,
                "following_avatar": current_user.avatar_url,
                "created_at": follow.created_at.isoformat()
            })
    
    return success_response(data={
        "users": follow_responses,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.get("/{user_id}/status", summary="查询关注状态")
async def get_follow_status(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询当前用户是否关注了指定用户"""
    
    follow = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()
    
    is_following = follow is not None
    
    return success_response(
        data={
            "user_id": user_id,
            "is_following": is_following
        }
    )


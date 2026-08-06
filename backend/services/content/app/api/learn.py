"""
学习进度管理API
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.append(project_root)

from common.database.connection import get_db
from common.models import User, Video, LearnRecord
from common.utils.auth import get_current_user, get_optional_user
from common.utils.response import success_response, error_response, not_found_response

router = APIRouter(prefix="/api/learn", tags=["learn"])


class HeartbeatRequest(BaseModel):
    video_id: str
    position: int  # 当前播放位置（秒）
    duration: int  # 视频总时长（秒）


class CompleteRequest(BaseModel):
    video_id: str
    completion_rate: Optional[float] = 100.0  # 完成率（百分比）


@router.post("/heartbeat", summary="学习心跳上报")
async def heartbeat(
    request: HeartbeatRequest,
    current_user: User = Depends(get_current_user),  # 统一强制鉴权（与其他服务一致）
    db: Session = Depends(get_db)
):
    """上报学习进度心跳"""
    
    # 验证视频存在
    video = db.query(Video).filter(
        Video.id == request.video_id,
        Video.status == "online"
    ).first()
    
    if not video:
        return not_found_response("视频不存在")
    
    # 查找或创建学习记录
    learn_record = db.query(LearnRecord).filter(
        LearnRecord.user_id == current_user.id,
        LearnRecord.video_id == request.video_id
    ).first()
    
    if not learn_record:
        # 创建新的学习记录
        learn_record = LearnRecord(
            user_id=current_user.id,
            video_id=request.video_id,
            status="in_progress",
            completed_ratio=0.0,
            last_position=0
        )
        db.add(learn_record)
    
    # 更新学习进度
    learn_record.last_position = request.position
    learn_record.status = "in_progress"
    learn_record.last_watch_time = datetime.now(timezone.utc)
    
    # 计算进度百分比
    if request.duration > 0:
        progress = min((request.position / request.duration) * 100, 100.0)
        learn_record.completed_ratio = progress
        
        # 如果观看超过90%，自动标记为完成
        if progress >= 90.0:
            learn_record.status = "completed"
    
    db.commit()
    db.refresh(learn_record)
    
    return success_response(
        data={
            "video_id": str(learn_record.video_id),
            "progress": float(learn_record.completed_ratio) if learn_record.completed_ratio else 0.0,
            "status": learn_record.status,
            "last_position": learn_record.last_position
        },
        message="学习进度已更新"
    )


@router.post("/complete", summary="完成学习")
async def complete(
    request: CompleteRequest,
    current_user: User = Depends(get_current_user),  # 统一强制鉴权（与其他服务一致）
    db: Session = Depends(get_db)
):
    """标记视频学习完成"""
    
    # 验证视频存在
    video = db.query(Video).filter(
        Video.id == request.video_id,
        Video.status == "online"
    ).first()
    
    if not video:
        return not_found_response("视频不存在")
    
    # 查找或创建学习记录
    learn_record = db.query(LearnRecord).filter(
        LearnRecord.user_id == current_user.id,
        LearnRecord.video_id == request.video_id
    ).first()
    
    if not learn_record:
        # 创建新的学习记录
        learn_record = LearnRecord(
            user_id=current_user.id,
            video_id=request.video_id,
            status="completed",
            completed_ratio=request.completion_rate or 100.0,
            last_watch_time=datetime.now(timezone.utc)
        )
        db.add(learn_record)
    else:
        # 更新为完成状态
        learn_record.status = "completed"
        learn_record.completed_ratio = request.completion_rate or 100.0
        learn_record.last_watch_time = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(learn_record)
    
    return success_response(
        data={
            "video_id": str(learn_record.video_id),
            "status": learn_record.status,
            "progress": float(learn_record.completed_ratio) if learn_record.completed_ratio else 0.0,
            "completed_at": learn_record.last_watch_time.isoformat() if learn_record.last_watch_time else None
        },
        message="学习已完成"
    )


@router.get("/records", summary="获取学习记录")
async def get_records(
    current_user: User = Depends(get_current_user),  # 统一强制鉴权（与其他服务一致）
    db: Session = Depends(get_db)
):
    """获取用户的学习记录"""
    
    # 获取用户的学习记录
    records = db.query(LearnRecord).filter(
        LearnRecord.user_id == current_user.id
    ).order_by(LearnRecord.last_watch_time.desc()).all()
    
    # 获取视频信息
    record_list = []
    for record in records:
        video = db.query(Video).filter(Video.id == record.video_id).first()
        if video:
            record_list.append({
                "id": str(record.id),
                "video_id": str(record.video_id),
                "title": video.title,
                "cover": video.cover_url,
                "status": record.status,
                "progress": float(record.completed_ratio) if record.completed_ratio else 0.0,
                "last_watch_time": record.last_watch_time.isoformat() if record.last_watch_time else None
            })
    
    return success_response(
        data={
            "records": record_list,
            "total": len(record_list)
        },
        message="获取学习记录成功"
    )

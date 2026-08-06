"""
消息通知API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from common.database.connection import get_db
from common.models import User, Notification
from common.utils.auth import get_current_user
from common.utils.response import success_response, error_response

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


class ReadMessagesRequest(BaseModel):
    message_ids: Optional[List[str]] = None  # 为空则标记全部为已读


@router.get("/messages", summary="获取消息列表")
async def get_messages(
    type: Optional[str] = Query(None, description="消息类型：comment_reply/audit_result/system/split_completed"),
    is_read: Optional[bool] = Query(None, description="是否已读"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取消息列表"""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    
    # 筛选条件
    if type:
        query = query.filter(Notification.type == type)
    
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    
    # 排序：未读消息优先，然后按时间倒序
    query = query.order_by(Notification.is_read.asc(), desc(Notification.created_at))
    
    # 分页
    total = query.count()
    offset = (page - 1) * page_size
    notifications = query.offset(offset).limit(page_size).all()
    
    # 构建响应数据
    items = []
    for notification in notifications:
        items.append({
            "id": str(notification.id),
            "type": notification.type,
            "title": notification.title,
            "content": notification.content,
            "is_read": notification.is_read,
            "related_id": notification.related_id,
            "created_at": notification.created_at.isoformat()
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


@router.post("/read", summary="标记消息已读")
async def mark_messages_read(
    request: ReadMessagesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """标记消息已读"""
    if request.message_ids:
        # 标记指定消息为已读
        updated_count = db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.id.in_(request.message_ids)
        ).update({"is_read": True}, synchronize_session=False)
    else:
        # 标记全部消息为已读
        updated_count = db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).update({"is_read": True}, synchronize_session=False)
    
    db.commit()
    
    return success_response(
        data={
            "updated_count": updated_count
        },
        message="消息已标记为已读"
    )


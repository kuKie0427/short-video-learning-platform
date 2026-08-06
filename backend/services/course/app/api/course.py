"""
课程管理API
"""
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_
from pydantic import BaseModel

from common.database.connection import get_db
from common.models import User, Course, CourseVideo, Video, Like, Favorite, LearnRecord
from common.utils.auth import get_current_user
from common.utils.response import success_response, error_response, not_found_response
from common.utils.stats import get_play_count

router = APIRouter(prefix="/api/courses", tags=["courses"])


class CourseCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    language: str = "zh-CN"
    cover_url: Optional[str] = None
    is_public: bool = True


class CourseUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    cover_url: Optional[str] = None


class CourseVideoAddRequest(BaseModel):
    video_ids: List[str]
    segment_indexes: Optional[List[int]] = None


class VideoOrderRequest(BaseModel):
    video_id: str
    segment_index: int


class CourseVideoOrderRequest(BaseModel):
    video_orders: List[VideoOrderRequest]


class CourseResponse(BaseModel):
    course_id: str
    title: str
    description: Optional[str]
    tags: Optional[List[str]]
    language: str
    cover_url: Optional[str]
    author: dict
    status: str
    total_videos: int
    total_duration: int
    stats: dict
    videos: Optional[List[dict]] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CourseListItem(BaseModel):
    course_id: str
    title: str
    cover_url: Optional[str]
    author: dict
    total_videos: int
    total_duration: int
    stats: dict
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("", summary="创建课程")
async def create_course(
    request: CourseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建课程"""
    # 生成课程业务ID
    course_id = f"course_{uuid.uuid4().hex[:8]}"
    
    # 创建课程
    course = Course(
        course_id=course_id,
        author_id=current_user.id,
        title=request.title,
        description=request.description,
        tags=request.tags,
        language=request.language,
        cover_url=request.cover_url,
        status="draft" if not request.is_public else "pending"
    )
    
    db.add(course)
    db.commit()
    db.refresh(course)
    
    return success_response(
        data={
            "course_id": course.course_id,
            "title": course.title,
            "status": course.status,
            "created_at": course.created_at.isoformat()
        },
        message="课程创建成功"
    )


@router.get("/{course_id}", summary="查询课程详情")
async def get_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询课程详情"""
    # 通过course_id查找课程
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        return not_found_response("课程不存在")
    
    # 获取作者信息
    author = {
        "id": str(course.author.id),
        "nickname": course.author.nickname,
        "avatar": course.author.avatar_url
    }
    
    # 获取课程视频列表
    course_videos = db.query(CourseVideo).filter(
        CourseVideo.course_id == course.id
    ).order_by(CourseVideo.segment_index).all()
    
    videos = []
    for cv in course_videos:
        video = cv.video
        if video:
            videos.append({
                "video_id": str(video.id),
                "segment_index": cv.segment_index,
                "title": video.title,
                "duration": video.duration,
                "cover_url": video.cover_url,
                "play_url": video.play_url,
                "status": video.status
            })
    
    # 计算统计数据
    video_ids = [str(cv.video_id) for cv in course_videos]
    total_play_count = sum(get_play_count(video_id) for video_id in video_ids)
    
    stats = {
        "play_count": total_play_count,
        "like_count": db.query(Like).filter(Like.video_id.in_(video_ids)).count(),
        "favorite_count": db.query(Favorite).filter(Favorite.video_id.in_(video_ids)).count(),
        "student_count": db.query(LearnRecord).filter(
            LearnRecord.video_id.in_([cv.video_id for cv in course_videos])
        ).distinct(LearnRecord.user_id).count()
    }
    
    return success_response(
        data={
            "course_id": course.course_id,
            "title": course.title,
            "description": course.description,
            "tags": course.tags,
            "language": course.language,
            "cover_url": course.cover_url,
            "author": author,
            "status": course.status,
            "total_videos": course.total_videos,
            "total_duration": course.total_duration,
            "stats": stats,
            "videos": videos,
            "created_at": course.created_at.isoformat(),
            "updated_at": course.updated_at.isoformat() if course.updated_at else None
        }
    )


@router.post("/{course_id}/videos", summary="添加视频到课程")
async def add_videos_to_course(
    course_id: str,
    request: CourseVideoAddRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加视频到课程"""
    # 查找课程
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        return not_found_response("课程不存在")
    
    # 验证权限
    if course.author_id != current_user.id:
        return error_response("无权操作此课程", code=403)
    
    # 验证视频是否存在
    videos = db.query(Video).filter(Video.id.in_(request.video_ids)).all()
    if len(videos) != len(request.video_ids):
        return error_response("部分视频不存在", code=400)
    
    # 获取当前课程的最大segment_index
    max_index = db.query(func.max(CourseVideo.segment_index)).filter(
        CourseVideo.course_id == course.id
    ).scalar() or -1
    
    # 添加视频
    added_count = 0
    for i, video_id in enumerate(request.video_ids):
        # 检查视频是否已在课程中
        existing = db.query(CourseVideo).filter(
            CourseVideo.course_id == course.id,
            CourseVideo.video_id == video_id
        ).first()
        
        if existing:
            continue
        
        # 确定segment_index
        if request.segment_indexes and i < len(request.segment_indexes):
            segment_index = request.segment_indexes[i]
        else:
            segment_index = max_index + 1 + added_count
        
        course_video = CourseVideo(
            course_id=course.id,
            video_id=video_id,
            segment_index=segment_index
        )
        db.add(course_video)
        added_count += 1
    
    # 更新课程统计信息
    course.total_videos = db.query(CourseVideo).filter(
        CourseVideo.course_id == course.id
    ).count()
    
    # 计算总时长
    course_videos = db.query(CourseVideo).filter(
        CourseVideo.course_id == course.id
    ).join(Video, CourseVideo.video_id == Video.id).all()
    course.total_duration = sum(cv.video.duration for cv in course_videos if cv.video)
    
    db.commit()
    
    return success_response(
        data={
            "course_id": course.course_id,
            "added_count": added_count,
            "total_videos": course.total_videos
        },
        message="视频已添加到课程"
    )


@router.delete("/{course_id}/videos/{video_id}", summary="从课程中移除视频")
async def remove_video_from_course(
    course_id: str,
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """从课程中移除视频"""
    # 查找课程
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        return not_found_response("课程不存在")
    
    # 验证权限
    if course.author_id != current_user.id:
        return error_response("无权操作此课程", code=403)
    
    # 查找课程视频关联
    course_video = db.query(CourseVideo).filter(
        CourseVideo.course_id == course.id,
        CourseVideo.video_id == video_id
    ).first()
    
    if not course_video:
        return not_found_response("视频不在课程中")
    
    # 删除关联
    db.delete(course_video)
    
    # 更新课程统计信息
    course.total_videos = db.query(CourseVideo).filter(
        CourseVideo.course_id == course.id
    ).count()
    
    # 重新计算总时长
    course_videos = db.query(CourseVideo).filter(
        CourseVideo.course_id == course.id
    ).join(Video, CourseVideo.video_id == Video.id).all()
    course.total_duration = sum(cv.video.duration for cv in course_videos if cv.video)
    
    db.commit()
    
    return success_response(
        data={
            "course_id": course.course_id,
            "video_id": video_id,
            "total_videos": course.total_videos
        },
        message="视频已从课程中移除"
    )


@router.put("/{course_id}", summary="更新课程信息")
async def update_course(
    course_id: str,
    request: CourseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新课程信息"""
    # 查找课程
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        return not_found_response("课程不存在")
    
    # 验证权限
    if course.author_id != current_user.id:
        return error_response("无权操作此课程", code=403)
    
    # 更新字段
    if request.title is not None:
        course.title = request.title
    if request.description is not None:
        course.description = request.description
    if request.tags is not None:
        course.tags = request.tags
    if request.cover_url is not None:
        course.cover_url = request.cover_url
    
    db.commit()
    db.refresh(course)
    
    return success_response(
        data={
            "course_id": course.course_id,
            "updated_at": course.updated_at.isoformat() if course.updated_at else None
        },
        message="课程信息已更新"
    )


@router.get("", summary="查询课程列表")
async def get_courses(
    author_id: Optional[str] = Query(None, description="作者ID"),
    tags: Optional[str] = Query(None, description="标签筛选（逗号分隔）"),
    status: Optional[str] = Query(None, description="状态筛选"),
    sort_by: Optional[str] = Query("latest", description="排序方式"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询课程列表"""
    query = db.query(Course)
    
    # 筛选条件
    if author_id:
        query = query.filter(Course.author_id == author_id)
    
    if status:
        query = query.filter(Course.status == status)
    
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        # PostgreSQL数组字段搜索
        if tag_list:
            # 使用PostgreSQL数组操作：检查tags数组是否包含任一标签
            from sqlalchemy import or_
            conditions = []
            for tag in tag_list:
                # PostgreSQL数组包含操作
                conditions.append(Course.tags.contains([tag]))
            if conditions:
                query = query.filter(or_(*conditions))
    
    # 排序
    if sort_by == "latest":
        query = query.order_by(desc(Course.created_at))
    elif sort_by == "hot":
        # 简化版，实际应该按热度排序
        query = query.order_by(desc(Course.total_videos))
    elif sort_by == "students":
        # 简化版，实际应该按学习人数排序
        query = query.order_by(desc(Course.total_videos))
    
    # 分页
    total = query.count()
    offset = (page - 1) * page_size
    courses = query.offset(offset).limit(page_size).all()
    
    # 构建响应数据
    items = []
    for course in courses:
        # 计算统计数据（简化版）
        stats = {
            "play_count": 0,
            "student_count": 0
        }
        
        items.append({
            "course_id": course.course_id,
            "title": course.title,
            "cover_url": course.cover_url,
            "author": {
                "id": str(course.author.id),
                "nickname": course.author.nickname
            },
            "total_videos": course.total_videos,
            "total_duration": course.total_duration,
            "stats": stats,
            "status": course.status,
            "created_at": course.created_at.isoformat()
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


@router.put("/{course_id}/videos/order", summary="调整课程视频顺序")
async def update_video_order(
    course_id: str,
    request: CourseVideoOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """调整课程视频顺序"""
    # 查找课程
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        return not_found_response("课程不存在")
    
    # 验证权限
    if course.author_id != current_user.id:
        return error_response("无权操作此课程", code=403)
    
    # 更新视频顺序
    for order in request.video_orders:
        course_video = db.query(CourseVideo).filter(
            CourseVideo.course_id == course.id,
            CourseVideo.video_id == order.video_id
        ).first()
        
        if course_video:
            course_video.segment_index = order.segment_index
    
    db.commit()
    
    return success_response(
        data={
            "course_id": course.course_id,
            "updated_at": datetime.now().isoformat()
        },
        message="视频顺序已更新"
    )


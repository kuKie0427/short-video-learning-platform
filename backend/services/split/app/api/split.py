import uuid
import os
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import insert
from pydantic import BaseModel

from common.database.connection import get_db
from common.models import User, SplitTask, SplitSegment, Video, LongVideo
from common.utils.auth import get_current_user
from common.utils.response import success_response, error_response, not_found_response
from common.utils.redis_client import invalidate_recommendation_cache, get_redis
from ..celery_app import celery_app
from ..services.video_split_service import get_video_split_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/split", tags=["split"])

security = HTTPBearer()


class SplitTaskRequest(BaseModel):
    long_video_id: str
    split_mode: str  # auto, manual, scene
    auto_config: Optional[Dict[str, Any]] = None
    organization_mode: str  # course, standalone


class SplitTaskResponse(BaseModel):
    id: str
    task_id: str
    long_video_id: str
    user_id: str
    split_mode: str
    auto_config: Optional[Dict[str, Any]]
    organization_mode: str
    status: str
    progress: float
    progress_message: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]  # 设为可选，避免验证失败
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str
        }

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            task_id=obj.task_id,
            long_video_id=str(obj.long_video_id),
            user_id=str(obj.user_id),
            split_mode=obj.split_mode,
            auto_config=obj.auto_config,
            organization_mode=obj.organization_mode,
            status=obj.status,
            progress=obj.progress,
            progress_message=obj.progress_message,
            error_message=obj.error_message,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            completed_at=obj.completed_at
        )


class SplitSegmentResponse(BaseModel):
    id: str
    segment_index: int
    start_time: int
    end_time: int
    duration: int
    thumbnail_url: Optional[str]
    scene_type: Optional[str]
    confidence: Optional[float]
    video_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            uuid.UUID: str
        }

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            segment_index=obj.segment_index,
            start_time=obj.start_time,
            end_time=obj.end_time,
            duration=obj.duration,
            thumbnail_url=obj.thumbnail_url,
            scene_type=obj.scene_type,
            confidence=obj.confidence,
            video_id=str(obj.video_id) if obj.video_id else None,
            created_at=obj.created_at
        )


class SplitResultResponse(BaseModel):
    task: SplitTaskResponse
    segments: List[SplitSegmentResponse]


class SegmentUpdate(BaseModel):
    """单个拆分点的更新信息"""
    segment_id: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    scene_type: Optional[str] = None


class UpdateSegmentsRequest(BaseModel):
    """更新拆分点请求"""
    segments: List[SegmentUpdate]


class AnalyzeRequest(BaseModel):
    """仅分析视频请求"""
    long_video_id: str


class KnowledgePoint(BaseModel):
    """知识点"""
    id: int
    title: str
    start_time: int
    end_time: int
    duration: int


class AnalyzeResponse(BaseModel):
    """分析响应"""
    knowledge_points: List[KnowledgePoint]
    used_fallback: bool
    cached: bool
    message: Optional[str] = None


class DirectSplitRequest(BaseModel):
    """直接切分请求（基于已有分析结果）"""
    long_video_id: str
    knowledge_points: List[KnowledgePoint]
    organization_mode: str = "standalone"


class PublishSegmentsRequest(BaseModel):
    """发布片段请求"""
    segment_ids: List[str]


@router.post("/analyze", summary="仅分析视频（不切割）")
async def analyze_video(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """仅分析视频，返回建议的切分点（GLM知识点）"""
    
    # 验证长视频是否存在
    try:
        lv_id = uuid.UUID(request.long_video_id)
    except ValueError:
        return error_response("长视频ID格式错误")
    
    long_video = db.query(LongVideo).filter(LongVideo.id == lv_id).first()
    if not long_video:
        return not_found_response("长视频不存在")
    
    # 验证权限
    if long_video.video and long_video.video.author_id != current_user.id:
        return error_response("无权操作此视频", code=403)
    
    # 获取视频文件路径 
    video_path = None
    if hasattr(long_video, 'file_path') and long_video.file_path:
        video_path = long_video.file_path
    elif hasattr(long_video, 'original_file_url') and long_video.original_file_url:
        video_path = long_video.original_file_url
    
    # 尝试查找视频文件
    if video_path:
        # 首先检查原始路径
        if os.path.exists(video_path):
            logger.info(f"找到视频文件(原始路径): {video_path}")
        else:
            # 如果原始路径不存在，尝试不同的基础路径
            possible_base_paths = [
                "/app/data",  # Docker容器内路径
                "data",       # 相对于工作目录
                "./data",     # 当前目录下的data
                "../data",    # 上级目录的data
            ]
            
            found = False
            for base_path in possible_base_paths:
                full_path = os.path.join(base_path, video_path.lstrip('/'))
                if os.path.exists(full_path):
                    video_path = full_path
                    logger.info(f"找到视频文件: {video_path}")
                    found = True
                    break
            
            if not found:
                logger.warning(f"无法找到视频文件，尝试的路径: {[os.path.join(bp, video_path.lstrip('/')) for bp in possible_base_paths]}")
                video_path = None
    
    # 如果视频文件不存在，生成示例数据用于演示
    if not video_path or not os.path.exists(video_path):
        logger.warning(f"视频文件不存在: {video_path}，使用示例数据演示功能")
        
        # 生成示例知识点数据
        sample_knowledge_points = [
            {"id": 1, "title": "课程介绍与目标", "start_time": 0, "end_time": 180, "duration": 180},
            {"id": 2, "title": "基础概念讲解", "start_time": 180, "end_time": 420, "duration": 240},
            {"id": 3, "title": "核心原理分析", "start_time": 420, "end_time": 720, "duration": 300},
            {"id": 4, "title": "实践案例演示", "start_time": 720, "end_time": 960, "duration": 240},
            {"id": 5, "title": "总结与答疑", "start_time": 960, "end_time": 1200, "duration": 240}
        ]
        
        return success_response(data={
            "knowledge_points": sample_knowledge_points,
            "used_fallback": True,
            "cached": False,
            "message": "视频文件不存在，使用示例数据演示智能分析功能"
        })
    
    try:
        # 使用SmartSplitService进行分析
        from ..services.smart_split_service import SmartSplitService
        
        service = SmartSplitService(
            output_dir="smart_split_output"
        )
        
        # 调用仅分析方法，使用UUID作为缓存目录名
        result = service.analyze_video(
            video_path=video_path,
            video_name=str(long_video.id)  # 使用UUID确保缓存一致性
        )
        
        knowledge_points = result.get('knowledge_points', [])
        used_fallback = result.get('used_fallback', False)
        cached = result.get('cached', False)
        
        # 构建响应消息
        message = None
        if used_fallback:
            message = "智能分析失败，已使用简单切分"
        elif cached:
            message = "使用缓存的分析结果"
        
        return success_response(data={
            "knowledge_points": knowledge_points,
            "used_fallback": used_fallback,
            "cached": cached,
            "message": message
        })
        
    except Exception as e:
        logger.error(f"视频分析失败: {e}", exc_info=True)
        return error_response(f"分析失败: {str(e)}")


@router.post("/direct-split", summary="直接切分视频（基于已有分析结果）")
async def direct_split_video(
    request: DirectSplitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """直接根据知识点切分视频，不执行智能分析"""
    
    # 验证长视频是否存在
    try:
        lv_id = uuid.UUID(request.long_video_id)
    except Exception:
        lv_id = request.long_video_id
    long_video = db.query(LongVideo).filter(LongVideo.id == lv_id).first()
    if not long_video:
        return not_found_response("长视频不存在")
    
    # 验证权限
    if long_video.video and long_video.video.author_id != current_user.id:
        return error_response("无权操作此视频", code=403)
    
    # 生成任务ID
    task_id = f"split_{uuid.uuid4().hex[:8]}"
    
    # 创建分割任务
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    split_task = SplitTask(
        task_id=task_id,
        long_video_id=long_video.id,
        user_id=current_user.id,
        split_mode='auto',  # 固定为auto模式
        auto_config={'enable_smart_split': True},
        organization_mode=request.organization_mode,
        status="pending",
        progress=0.0,
        created_at=now,
        updated_at=now
    )
    
    db.add(split_task)
    db.commit()
    db.refresh(split_task)
    
    # 直接基于知识点进行切分（同步执行，因为只是按时间切分视频）
    try:
        # 更新任务状态
        split_task.status = "processing"
        split_task.progress = 20.0
        split_task.progress_message = "正在基于知识点切分视频..."
        db.commit()
        
        # 获取视频文件路径
        video = db.query(Video).filter(Video.id == long_video.video_id).first()
        if not video:
            split_task.status = "failed"
            split_task.error_message = "视频不存在"
            db.commit()
            return error_response("视频不存在")
        
        video_path = video.play_url
        if video_path.startswith('/uploads/'):
            # 兼容三种部署形态（原实现硬编码 Docker 路径，本地/CI 部署必失败）：
            # 1. 本地/CI：UPLOAD_BASE_DIR 指向 upload 服务实际落盘目录（文件在 {base}/文件名）
            # 2. Docker compose：未设 UPLOAD_BASE_DIR，回退 /app/data/uploads
            # 3. 测试模式 play_url（/test/videos/...）：按绝对路径处理
            upload_dir = os.getenv('UPLOAD_BASE_DIR')
            if upload_dir:
                video_path = os.path.join(upload_dir, video_path[len('/uploads/'):])
            else:
                video_path = '/app/data' + video_path
        elif not os.path.isabs(video_path):
            video_path = os.path.join('/app/data', video_path.lstrip('/'))
        
        # 使用ffmpeg按时间戳切分视频
        split_task.progress = 40.0
        split_task.progress_message = "正在切分视频文件..."
        db.commit()
        
        from ..services.video_splitter import VideoSplitter
        splitter = VideoSplitter()
        
        # 将知识点转换为切分片段
        segments_data = []
        for idx, kp in enumerate(request.knowledge_points):
            segment_output, thumbnail_output = splitter.split_segment(
                video_path=video_path,
                start_time=kp.start_time,
                end_time=kp.end_time,
                output_dir=f"smart_split_output/{long_video.id}/segments",
                segment_index=idx,
                generate_thumbnail=True
            )
            
            segments_data.append({
                'segment_index': idx,
                'start_time': kp.start_time,
                'end_time': kp.end_time,
                'duration': kp.duration,
                'scene_type': kp.title,
                'video_path': segment_output,
                'thumbnail_path': thumbnail_output
            })
        
        # 保存分割片段到数据库
        split_task.progress = 80.0
        split_task.progress_message = "正在保存切分结果..."
        db.commit()
        
        for seg_data in segments_data:
            # 创建Video记录用于存储切分片段
            # 将本地路径转换为URL路径
            # 路径格式: /app/services/split/smart_split_output/... -> /smart_split_output/...
            # 或者相对路径: smart_split_output/... -> /smart_split_output/...
            video_path_absolute = seg_data['video_path']
            if video_path_absolute.startswith('/app/services/split/'):
                video_path_relative = video_path_absolute.replace('/app/services/split/', '/')
            elif video_path_absolute.startswith('/app/data/'):
                video_path_relative = video_path_absolute.replace('/app/data', '')
            elif not video_path_absolute.startswith('/'):
                # 相对路径，添加开头的斜杠
                video_path_relative = '/' + video_path_absolute
            else:
                video_path_relative = video_path_absolute
            
            # 处理缩略图路径
            thumbnail_url = None
            if seg_data.get('thumbnail_path'):
                thumbnail_path_absolute = seg_data['thumbnail_path']
                if thumbnail_path_absolute.startswith('/app/services/split/'):
                    thumbnail_url = thumbnail_path_absolute.replace('/app/services/split/', '/')
                elif not thumbnail_path_absolute.startswith('/'):
                    thumbnail_url = '/' + thumbnail_path_absolute
                else:
                    thumbnail_url = thumbnail_path_absolute
            
            segment_video = Video(
                title=seg_data.get('scene_type', f"片段{seg_data['segment_index']}"),
                author_id=current_user.id,
                duration=seg_data['duration'],
                play_url=video_path_relative,  # 存储相对路径
                status='published'
            )
            db.add(segment_video)
            db.flush()  # 获取video_id
            
            # 创建分割片段记录
            stmt = insert(SplitSegment.__table__).values(
                task_id=split_task.id,
                segment_index=seg_data['segment_index'],
                start_time=seg_data['start_time'],
                end_time=seg_data['end_time'],
                duration=seg_data['duration'],
                scene_type=seg_data.get('scene_type', 'auto'),
                thumbnail_url=thumbnail_url,
                confidence=None,
                video_id=segment_video.id
            )
            db.execute(stmt)
            db.commit()
        
        # 标记任务完成
        split_task.status = "completed"
        split_task.progress = 100.0
        split_task.progress_message = "切分完成"
        split_task.completed_at = datetime.now(timezone.utc)
        db.commit()
        
        task_data = {
            "id": str(split_task.id),
            "task_id": split_task.task_id,
            "long_video_id": str(split_task.long_video_id),
            "status": split_task.status,
            "progress": float(split_task.progress),
            "progress_message": split_task.progress_message
        }
        
        return success_response(data=task_data)
        
    except Exception as e:
        logger.error(f"视频切分失败: {e}", exc_info=True)
        split_task.status = "failed"
        split_task.error_message = str(e)
        db.commit()
        return error_response(f"切分失败: {str(e)}")


@router.post("/tasks", summary="创建视频分割任务")
async def create_split_task(
    request: SplitTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建视频分割任务"""
    
    # 验证长视频是否存在
    try:
        lv_id = uuid.UUID(request.long_video_id)
    except Exception:
        lv_id = request.long_video_id
    long_video = db.query(LongVideo).filter(LongVideo.id == lv_id).first()
    if not long_video:
        return not_found_response("长视频不存在")
    
    # 验证权限：确保用户只能操作自己的视频
    if long_video.video and long_video.video.author_id != current_user.id:
        return error_response("无权操作此视频", code=403)
    
    # 生成任务ID
    task_id = f"split_{uuid.uuid4().hex[:8]}"
    
    # 创建分割任务
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    split_task = SplitTask(
        task_id=task_id,
        long_video_id=long_video.id,
        user_id=current_user.id,
        split_mode=request.split_mode,
        auto_config=request.auto_config,
        organization_mode=request.organization_mode,
        status="pending",
        progress=0.0,
        created_at=now,
        updated_at=now
    )
    
    db.add(split_task)
    db.commit()
    db.refresh(split_task)
    
    # 触发异步任务处理
    try:
        # 获取长视频信息
        long_video = db.query(LongVideo).filter(LongVideo.id == request.long_video_id).first()
        if long_video:
            # 使用 Celery 异步触发拆分任务（生产模式）
            print(f"已创建分割任务: task_id={split_task.task_id}, long_video_id={str(long_video.id)}, queued to worker")
            # 将任务ID入队，由 worker 异步处理
            celery_app.send_task('split.process_split_task', args=[str(split_task.id)])
            # 更新任务状态为 queued
            split_task.status = "queued"
            split_task.progress = 0.0
            db.commit()
    except Exception as e:
        # 记录错误并更新任务状态为失败
        print(f"触发异步任务失败: {e}")
        split_task.status = "failed"
        split_task.error_message = f"任务启动失败: {str(e)}"
        db.commit()
        import traceback
        traceback.print_exc()
    
    task_data = {
        "id": str(split_task.id),
        "task_id": split_task.task_id,
        "long_video_id": str(split_task.long_video_id),
        "user_id": str(split_task.user_id),
        "split_mode": split_task.split_mode,
        "auto_config": split_task.auto_config,
        "organization_mode": split_task.organization_mode,
        "status": split_task.status,
        "progress": float(split_task.progress) if split_task.progress else 0.0,
        "progress_message": split_task.progress_message or "",
        "error_message": split_task.error_message,
        "created_at": split_task.created_at.isoformat(),
        "updated_at": split_task.updated_at.isoformat() if split_task.updated_at else None,
        "completed_at": split_task.completed_at.isoformat() if split_task.completed_at else None
    }
    return success_response(data=task_data)


@router.get("/tasks", summary="获取分割任务列表")
async def get_split_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的分割任务列表"""
    
    query = db.query(SplitTask).filter(SplitTask.user_id == current_user.id)
    
    if status:
        query = query.filter(SplitTask.status == status)
    
    tasks = query.order_by(SplitTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    tasks_data = []
    for task in tasks:
        # video_id 用于前端切分列表页按视频关联任务状态
        video_id = task.long_video.video_id if task.long_video else None
        tasks_data.append({
            "id": str(task.id),
            "task_id": task.task_id,
            "video_id": str(video_id) if video_id else None,
            "long_video_id": str(task.long_video_id),
            "user_id": str(task.user_id),
            "split_mode": task.split_mode,
            "auto_config": task.auto_config,
            "organization_mode": task.organization_mode,
            "status": task.status,
            "progress": float(task.progress) if task.progress else 0.0,
            "progress_message": task.progress_message or "",
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        })
    
    return success_response(data=tasks_data)


@router.get("/tasks/{task_id}", summary="获取分割任务详情")
async def get_split_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取分割任务详情"""
    
    task = db.query(SplitTask).filter(
        SplitTask.task_id == task_id,
        SplitTask.user_id == current_user.id
    ).first()
    
    if not task:
        return not_found_response("任务不存在或无权访问")
    
    task_data = {
        "id": str(task.id),
        "task_id": task.task_id,
        "long_video_id": str(task.long_video_id),
        "user_id": str(task.user_id),
        "split_mode": task.split_mode,
        "auto_config": task.auto_config,
        "organization_mode": task.organization_mode,
        "status": task.status,
        "progress": float(task.progress) if task.progress is not None else 0.0,
        "progress_message": task.progress_message or "",
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }
    return success_response(data=task_data)


@router.get("/tasks/{task_id}/segments", summary="获取分割结果")
async def get_split_segments(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取分割任务的结果片段"""
    
    # 验证任务权限
    task = db.query(SplitTask).filter(
        SplitTask.task_id == task_id,
        SplitTask.user_id == current_user.id
    ).first()
    
    if not task:
        return not_found_response("任务不存在或无权访问")
    
    # 获取分割片段
    segments = db.query(SplitSegment).filter(
        SplitSegment.task_id == task.id
    ).order_by(SplitSegment.segment_index).all()
    
    segments_data = []
    for segment in segments:
        segments_data.append({
            "id": str(segment.id),
            "segment_index": segment.segment_index,
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "duration": segment.duration,
            "thumbnail_url": segment.thumbnail_url,
            "scene_type": segment.scene_type,
            "confidence": segment.confidence,
            "video_id": str(segment.video_id) if segment.video_id else None,
            "created_at": segment.created_at.isoformat()
        })
    
    return success_response(data=segments_data)


@router.get("/tasks/{task_id}/result", summary="获取完整分割结果")
async def get_split_result(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取完整的分割结果（包含任务和片段）"""
    
    # 验证任务权限
    task = db.query(SplitTask).filter(
        SplitTask.task_id == task_id,
        SplitTask.user_id == current_user.id
    ).first()
    
    if not task:
        return not_found_response("任务不存在或无权访问")
    
    # 获取分割片段
    segments = db.query(SplitSegment).filter(
        SplitSegment.task_id == task.id
    ).order_by(SplitSegment.segment_index).all()
    
    result = {
        "task": {
            "id": str(task.id),
            "task_id": task.task_id,
            "long_video_id": str(task.long_video_id),
            "user_id": str(task.user_id),
            "split_mode": task.split_mode,
            "auto_config": task.auto_config,
            "organization_mode": task.organization_mode,
            "status": task.status,
            "progress": float(task.progress) if task.progress else 0.0,
            "progress_message": task.progress_message,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        },
        "segments": [
            {
                "id": str(segment.id),
                "segment_index": segment.segment_index,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "duration": segment.duration,
                "thumbnail_url": ("/" + segment.thumbnail_url) if (segment.thumbnail_url and not segment.thumbnail_url.startswith("/")) else segment.thumbnail_url,
                "scene_type": segment.scene_type,
                "confidence": float(segment.confidence) if segment.confidence else None,
                "video_id": str(segment.video_id) if segment.video_id else None,
                "video_url": ("/" + segment.video.play_url) if (segment.video and segment.video.play_url and not segment.video.play_url.startswith("/")) else (segment.video.play_url if segment.video else None),
                "created_at": segment.created_at.isoformat()
            }
            for segment in segments
        ]
    }
    
    return success_response(data=result)


@router.post("/tasks/{task_id}/confirm", response_model=SplitResultResponse, summary="确认分割结果")
async def confirm_split_result(
    task_id: str,
    segment_ids: List[str],  # 用户确认的片段ID列表
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """确认分割结果并生成短视频"""
    
    # 验证任务权限
    task = db.query(SplitTask).filter(
        SplitTask.task_id == task_id,
        SplitTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    # 获取长视频信息
    long_video = db.query(LongVideo).filter(LongVideo.id == task.long_video_id).first()
    if not long_video:
        raise HTTPException(status_code=404, detail="长视频不存在")
    
    # 获取用户确认的片段
    # 将片段ID转换为 UUID
    conv_ids = []
    for sid in segment_ids:
        try:
            conv_ids.append(uuid.UUID(sid))
        except Exception:
            conv_ids.append(sid)

    segments = db.query(SplitSegment).filter(
        SplitSegment.task_id == task.id,
        SplitSegment.id.in_(conv_ids)
    ).order_by(SplitSegment.segment_index).all()
    
    if not segments:
        raise HTTPException(status_code=400, detail="未选择任何片段")
    
    # 注意：实际视频拆分已在process_split_task_sync中完成
    # 这里只是确认分割结果并创建短视频记录
    # 如果需要重新生成视频，应该调用视频拆分服务
    for i, segment in enumerate(segments):
        # 创建短视频记录
        video = Video(
            author_id=current_user.id,
            title=f"{task.task_id}_segment_{segment.segment_index}",
            description=f"从长视频分割出的片段 {segment.segment_index}",
            duration=segment.duration,
            play_url=f"/videos/split/{task_id}/segment_{segment.segment_index}",
            cover_url=segment.thumbnail_url,
            language="zh-CN",
            status="online",
            video_type="short",
            parent_video_id=long_video.id  # 外键指向 long_videos.id（曾误用 video_id 导致 ForeignKeyViolation）
        )
        
        db.add(video)
        db.flush()  # 获取video.id
        
        # 更新片段关联的短视频ID
        segment.video_id = video.id
    
    # 更新任务状态
    task.status = "confirmed"
    
    db.commit()
    
    # 返回确认后的结果
    segments = db.query(SplitSegment).filter(
        SplitSegment.task_id == task.id
    ).order_by(SplitSegment.segment_index).all()
    
    return SplitResultResponse(
        task=SplitTaskResponse.from_orm(task),
        segments=[SplitSegmentResponse.from_orm(segment) for segment in segments]
    )


@router.put("/tasks/{task_id}/segments", summary="手动调整拆分点")
async def update_split_segments(
    task_id: str,
    request: UpdateSegmentsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """手动调整拆分点（更新拆分片段的时间点）"""
    
    # 验证任务权限
    task = db.query(SplitTask).filter(
        SplitTask.task_id == task_id,
        SplitTask.user_id == current_user.id
    ).first()
    
    if not task:
        return not_found_response("任务不存在或无权访问")
    
    # 验证任务状态（只有在completed状态下才能调整）
    if task.status not in ["completed", "pending"]:
        return error_response("任务状态不允许调整拆分点", code=400)
    
    # 获取长视频信息，用于验证时间范围
    long_video = db.query(LongVideo).filter(LongVideo.id == task.long_video_id).first()
    if not long_video:
        return not_found_response("长视频不存在")
    
    max_duration = long_video.original_duration if long_video.original_duration else 999999
    
    # 更新每个拆分点
    updated_segments = []
    for segment_update in request.segments:
        # 查找拆分片段
        try:
            seg_uuid = uuid.UUID(segment_update.segment_id)
        except Exception:
            seg_uuid = segment_update.segment_id

        segment = db.query(SplitSegment).filter(
            SplitSegment.id == seg_uuid,
            SplitSegment.task_id == task.id
        ).first()
        
        if not segment:
            return not_found_response(f"拆分片段 {segment_update.segment_id} 不存在")
        
        # 更新拆分点信息
        if segment_update.start_time is not None:
            if segment_update.start_time < 0 or segment_update.start_time >= max_duration:
                return error_response(f"开始时间 {segment_update.start_time} 超出有效范围", code=400)
            segment.start_time = segment_update.start_time
        
        if segment_update.end_time is not None:
            if segment_update.end_time <= 0 or segment_update.end_time > max_duration:
                return error_response(f"结束时间 {segment_update.end_time} 超出有效范围", code=400)
            segment.end_time = segment_update.end_time
            
            # 重新计算时长
            if segment.start_time is not None:
                segment.duration = segment.end_time - segment.start_time
        
        if segment_update.scene_type is not None:
            segment.scene_type = segment_update.scene_type
        
        # 标记为手动调整
        if segment.scene_type != "manual":
            segment.scene_type = "manual"
        
        updated_segments.append(segment)
    
    # 验证时间顺序（确保start_time < end_time，且片段之间不重叠）
    all_segments = db.query(SplitSegment).filter(
        SplitSegment.task_id == task.id
    ).order_by(SplitSegment.segment_index).all()
    
    for i, seg in enumerate(all_segments):
        if seg.start_time >= seg.end_time:
            return error_response(f"片段 {seg.segment_index} 的开始时间必须小于结束时间", code=400)
        if i > 0:
            prev_seg = all_segments[i - 1]
            if seg.start_time < prev_seg.end_time:
                return error_response(f"片段 {seg.segment_index} 与前一片段时间重叠", code=400)
    
    db.commit()
    
    # 返回更新后的结果
    segments = db.query(SplitSegment).filter(
        SplitSegment.task_id == task.id
    ).order_by(SplitSegment.segment_index).all()
    
    task_data = {
        "id": str(task.id),
        "task_id": task.task_id,
        "long_video_id": str(task.long_video_id),
        "user_id": str(task.user_id),
        "split_mode": task.split_mode,
        "auto_config": task.auto_config,
        "organization_mode": task.organization_mode,
        "status": task.status,
        "progress": float(task.progress) if task.progress is not None else 0.0,
        "progress_message": task.progress_message or "",
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }
    
    segments_data = []
    for segment in segments:
        segments_data.append({
            "id": str(segment.id),
            "segment_index": segment.segment_index,
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "duration": segment.duration,
            "thumbnail_url": segment.thumbnail_url,
            "scene_type": segment.scene_type,
            "confidence": segment.confidence,
            "video_id": str(segment.video_id) if segment.video_id else None,
            "created_at": segment.created_at.isoformat()
        })
    
    return success_response(data={
        "task": task_data,
        "segments": segments_data
    })


@router.delete("/tasks/{task_id}", summary="删除分割任务")
async def delete_split_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除分割任务"""
    
    task = db.query(SplitTask).filter(
        SplitTask.task_id == task_id,
        SplitTask.user_id == current_user.id
    ).first()
    
    if not task:
        return not_found_response("任务不存在或无权操作")
    
    # 删除关联的分割片段
    db.query(SplitSegment).filter(SplitSegment.task_id == task.id).delete()
    
    # 删除任务
    db.delete(task)
    db.commit()
    
    return success_response(data={"message": "任务删除成功"})


# 同步分割处理函数（使用服务抽象层）
def process_split_task_sync(task_id: str, db: Session):
    """处理视频分割任务（使用视频拆分服务）"""
    try:
        task_uuid = uuid.UUID(task_id)
    except Exception:
        task_uuid = task_id

    task = db.query(SplitTask).filter(SplitTask.id == task_uuid).first()
    if not task:
        return
    
    # 获取长视频信息
    long_video = db.query(LongVideo).filter(LongVideo.id == task.long_video_id).first()
    if not long_video:
        task.status = "failed"
        task.error_message = "长视频不存在"
        db.commit()
        return
    
    # 获取视频文件路径
    video = db.query(Video).filter(Video.id == long_video.video_id).first()
    if not video:
        task.status = "failed"
        task.error_message = "视频不存在"
        db.commit()
        return
    
    # 更新任务状态
    task.status = "processing"
    task.progress = 10.0
    task.progress_message = "开始分析视频..."
    db.commit()
    
    try:
        # 获取视频拆分服务
        split_service = get_video_split_service()
        try:
            svc_name = split_service.__class__.__name__
        except Exception:
            svc_name = str(type(split_service))
        logger.info(f"[split_task:{task_id}] selected split service: {svc_name}")
        
        # 获取视频文件路径
        video_path = video.play_url
        # 在容器内，uploads目录挂载在 /app/data/uploads
        if video_path.startswith('/uploads/'):
            video_path = '/app/data' + video_path
        elif not os.path.isabs(video_path):
            # 如果是相对路径，转换为绝对路径
            video_path = os.path.join('/app/data', video_path.lstrip('/'))
        
        logger.info(f"[split_task:{task_id}] resolved video path: {video_path}")
        
        # 执行视频拆分，传递video_id用于缓存匹配
        task.progress = 30.0
        task.progress_message = "正在拆分视频..."
        db.commit()
        
        split_segments = split_service.split_video(
            video_path=video_path,
            split_mode=task.split_mode,
            auto_config=task.auto_config,
            video_id=str(task.long_video_id)  # 传递UUID用于缓存匹配
        )
        logger.info(f"[split_task:{task_id}] split_service returned {len(split_segments) if hasattr(split_segments, '__len__') else 'unknown'} segments")
        
        # 保存分割片段
        task.progress = 70.0
        task.progress_message = "正在保存拆分结果..."
        db.commit()
        
        segments = []
        for seg_data in split_segments:
            logger.info(f"[split_task:{task_id}] saving segment index={seg_data.get('segment_index')} start={seg_data.get('start_time')} end={seg_data.get('end_time')}")
            stmt = insert(SplitSegment.__table__).values(
                task_id=task.id,
                segment_index=seg_data['segment_index'],
                start_time=seg_data['start_time'],
                end_time=seg_data['end_time'],
                duration=seg_data['duration'],
                thumbnail_url=seg_data.get('thumbnail_url'),
                scene_type=seg_data.get('scene_type', 'auto'),
                confidence=seg_data.get('confidence')
            ).returning(SplitSegment.__table__.c.id, SplitSegment.__table__.c.created_at)

            try:
                result = db.execute(stmt)
                row = result.fetchone()
                inserted_id = row[0]
                created_at = row[1]
                logger.info(f"[split_task:{task_id}] inserted SplitSegment id={inserted_id}")
            except Exception:
                db.rollback()
                raise

            # 构造一个轻量对象用于返回
            segment = SplitSegment(
                id=inserted_id,
                task_id=task.id,
                segment_index=seg_data['segment_index'],
                start_time=seg_data['start_time'],
                end_time=seg_data['end_time'],
                duration=seg_data['duration'],
                thumbnail_url=seg_data.get('thumbnail_url'),
                scene_type=seg_data.get('scene_type', 'auto'),
                confidence=seg_data.get('confidence'),
                created_at=created_at
            )
            segments.append(segment)
        
        # 更新任务状态
        task.status = "completed"
        task.progress = 100.0
        task.progress_message = "拆分完成"
        task.completed_at = datetime.now(timezone.utc)
        
        db.commit()
        
        return segments
        
    except Exception as e:
        # 处理错误
        task.status = "failed"
        task.error_message = f"拆分失败: {str(e)}"
        task.progress_message = "拆分失败"
        db.commit()
        logger.error(f"视频拆分任务失败: {e}", exc_info=True)
        return []


# 简化分割接口 - 用于前端演示
@router.post("/simple-split", summary="简化视频分割")
async def simple_split(
    video_id: str,
    threshold: float = 0.15,
    db: Session = Depends(get_db)
):
    """简化视频分割接口（用于前端演示）"""
    
    # 验证视频存在（避免外键约束错误返回 500）
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        return not_found_response("视频不存在")
    
    # 确保演示用户存在（simple-split 无认证，固定使用演示用户）
    demo_user_id = "00000000-0000-0000-0000-000000000001"
    demo_user = db.query(User).filter(User.id == demo_user_id).first()
    if not demo_user:
        demo_user = User(
            id=demo_user_id,
            phone="13800138000",
            nickname="演示用户",
            avatar_url="",
            bio="用于前端演示的用户",
            roles=["admin"]
        )
        db.add(demo_user)
        db.commit()
    
    # 创建分割任务
    task_id = f"split_{uuid.uuid4().hex[:8]}"
    
    # 创建长视频记录（如果不存在）
    long_video = db.query(LongVideo).filter(LongVideo.video_id == video_id).first()
    if not long_video:
        long_video = LongVideo(
            video_id=video_id,
            original_duration=300,  # 假设5分钟视频
            original_file_url=f"/videos/{video_id}/original"
        )
        db.add(long_video)
        db.commit()
        db.refresh(long_video)
    
    # 创建分割任务
    split_task = SplitTask(
        task_id=task_id,
        long_video_id=long_video.id,
        user_id="00000000-0000-0000-0000-000000000001",  # 演示用用户ID
        split_mode="auto",
        auto_config={"threshold": threshold},
        organization_mode="standalone",
        status="completed",  # 直接标记为完成
        progress=100.0,
        completed_at=datetime.now(timezone.utc)
    )
    
    db.add(split_task)
    db.commit()
    db.refresh(split_task)
    
    # 模拟生成分割片段
    segments = []
    for i in range(5):
        start_time = i * 60  # 每60秒一个片段
        end_time = (i + 1) * 60
        duration = 60
        
        segment = SplitSegment(
            task_id=str(split_task.id),
            segment_index=i,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            thumbnail_url=f"/thumbnails/{task_id}/segment_{i}.jpg",
            scene_type="general",
            confidence=0.85
        )
        segments.append(segment)
    
    # 保存分割片段
    for segment in segments:
        db.add(segment)
    
    db.commit()
    
    return {
        "task_id": split_task.task_id,
        "segments": [
            {
                "id": str(segment.id),
                "segment_index": segment.segment_index,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "duration": segment.duration
            }
            for segment in segments
        ],
        "message": "分割完成"
    }

@router.post("/publish-segments", summary="����ѡ�е�Ƭ�ε���ҳ")
async def publish_segments(
    request: PublishSegmentsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    ��ѡ�е��з�Ƭ�η�������ҳ
    - �������Video��¼��long_video_idΪNULL��ʹ����ʾ����ҳ
    - ����video_typeΪ'short'
    """
    try:
        if not request.segment_ids:
            return error_response("��ѡ������һ��Ƭ��")
        
        # ת��segment_idsΪUUID
        segment_uuids = []
        for sid in request.segment_ids:
            try:
                segment_uuids.append(uuid.UUID(sid))
            except Exception:
                segment_uuids.append(sid)
        
        # ��ȡƬ����Ϣ
        segments = db.query(SplitSegment).filter(
            SplitSegment.id.in_(segment_uuids)
        ).all()
        
        if not segments:
            return not_found_response("δ�ҵ�ָ����Ƭ��")
        
        # ��֤Ȩ�ޣ����Ƭ�������������Ƿ����ڵ�ǰ�û�
        task_ids = set(seg.task_id for seg in segments)
        tasks = db.query(SplitTask).filter(
            SplitTask.id.in_(task_ids)
        ).all()
        
        for task in tasks:
            if task.user_id != current_user.id:
                return error_response("��Ȩ������Ƭ��", code=403)
        
        # ����Video��¼����long_video_id��ΪNULL��ʹ����ʾ����ҳ
        published_count = 0
        for segment in segments:
            if segment.video_id:
                video = db.query(Video).filter(Video.id == segment.video_id).first()
                if video:
                    # ��parent_video_id��ΪNULL��ʹ����Ϊ������Ƶ��ʾ
                    video.parent_video_id = None
                    video.video_type = 'short'
                    # 无条件更新状态为published，确保视频可见
                    video.status = 'published'
                    published_count += 1
        
        db.commit()
        time.sleep(1)
        # 清除所有用户的推荐缓存，确保新视频立即可见
        try:
            redis_client = get_redis()
            if redis_client:
                # 清除所有推荐缓存（包括匿名用户和所有已登录用户）
                pattern = "recommend:user:*"
                keys = redis_client.keys(pattern)
                if keys:
                    redis_client.delete(*keys)
                    logger.info(f"已清除 {len(keys)} 个推荐缓存键")
        except Exception as e:
            logger.warning(f"清除推荐缓存失败: {e}")
        
        return success_response(
            data={
                "published_count": published_count,
                "message": f"�ɹ����� {published_count} ��Ƭ�ε���ҳ"
            }
        )
        
    except Exception as e:
        logger.error(f"����Ƭ��ʧ��: {e}", exc_info=True)
        db.rollback()
        return error_response(f"����ʧ��: {str(e)}")

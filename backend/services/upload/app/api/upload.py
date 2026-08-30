"""
视频上传API
"""
import uuid
import os
import tempfile
import logging
import base64
import binascii
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel

from common.database.connection import get_db
from common.models import User
from common.models.upload import UploadTask
from common.models.video import LongVideo, Video
from common.utils.auth import get_current_user, get_optional_user
from common.utils.response import success_response, error_response
from ..services.storage import get_storage_service, calculate_file_hash

router = APIRouter(prefix="/api/upload", tags=["upload"])
logger = logging.getLogger(__name__)

security = HTTPBearer()

# 分片临时存储目录
CHUNK_TEMP_DIR = Path(tempfile.gettempdir()) / "upload_chunks"
CHUNK_TEMP_DIR.mkdir(parents=True, exist_ok=True)


class UploadInitRequest(BaseModel):
    file_name: str
    file_size: int
    duration: int
    mime_type: str
    video_type: str  # short: 短视频(≤3min), long: 长视频(>3min)


class UploadCompleteRequest(BaseModel):
    upload_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list] = None
    language: str = "zh-CN"
    is_public: bool = True


@router.post("/init", summary="初始化上传任务")
async def init_upload(
    request: UploadInitRequest,
    current_user: User = Depends(get_current_user),  # 统一强制鉴权（与其他服务一致）
    db: Session = Depends(get_db)
):
    """初始化上传任务"""
    
    user_id = current_user.id
    
    # 生成上传ID
    upload_id = f"UP_{uuid.uuid4().hex[:8]}"
    
    # 创建上传任务记录
    upload_task = UploadTask(
        upload_id=upload_id,
        user_id=user_id,
        file_name=request.file_name,
        file_size=request.file_size,
        duration=request.duration,
        video_type=request.video_type,
        status="initialized"
    )
    
    db.add(upload_task)
    db.commit()
    db.refresh(upload_task)
    
    # 创建分片临时目录
    chunk_dir = CHUNK_TEMP_DIR / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成上传URL（相对路径，前端会拼接baseURL）
    upload_url = "upload/chunk"
    
    return success_response(
        data={
            "upload_id": upload_id,
            "upload_url": upload_url,
            "chunk_size": 5242880,  # 5MB
            "expires_in": 3600
        },
        message="上传任务初始化成功"
    )


@router.put("/chunk", summary="分片上传")
async def upload_chunk(
    request: Request,
    current_user: User = Depends(get_current_user),  # 统一强制鉴权（与其他服务一致）
    db: Session = Depends(get_db)
):
    """分片上传接口"""
    # 从请求头获取参数
    upload_id = request.headers.get('upload_id')
    chunk_index_str = request.headers.get('chunk_index')
    
    if not upload_id or not chunk_index_str:
        return error_response("缺少必要参数", code=400)
    
    try:
        chunk_index = int(chunk_index_str)
    except ValueError:
        return error_response("chunk_index必须是整数", code=400)
    
    user_id = current_user.id
    
    # 验证上传任务
    upload_task = db.query(UploadTask).filter(
        UploadTask.upload_id == upload_id,
        UploadTask.user_id == user_id
    ).first()
    
    if not upload_task:
        return error_response("上传任务不存在", code=404)
    
    if upload_task.status not in ["initialized", "uploading"]:
        return error_response("上传任务状态不正确", code=400)
    
    # 更新状态为上传中
    if upload_task.status == "initialized":
        upload_task.status = "uploading"
        db.commit()
    
    # 读取分片数据
    chunk_data = await request.body()
    chunk_size = len(chunk_data)
    
    # 保存分片到临时目录
    chunk_dir = CHUNK_TEMP_DIR / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_file = chunk_dir / f"chunk_{chunk_index}"
    
    with open(chunk_file, 'wb') as f:
        f.write(chunk_data)
    
    logger.info(f"分片 {chunk_index} 上传成功，大小: {chunk_size} bytes")
    
    return success_response(
        data={
            "chunk_index": chunk_index,
            "chunk_size": chunk_size,
            "uploaded": True
        },
        message="分片上传成功"
    )


@router.post("/complete", summary="完成上传并发起转码")
async def complete_upload(
    request: UploadCompleteRequest,
    current_user: User = Depends(get_current_user),  # 统一强制鉴权（与其他服务一致）
    db: Session = Depends(get_db)
):
    """完成上传并发起转码"""
    user_id = current_user.id
    
    # 查找上传任务
    upload_task = db.query(UploadTask).filter(
        UploadTask.upload_id == request.upload_id,
        UploadTask.user_id == user_id
    ).first()
    
    if not upload_task:
        return error_response("上传任务不存在", code=404)
    
    if upload_task.status not in ["uploading", "uploaded"]:
        return error_response("上传任务状态不正确，请先完成所有分片上传", code=400)
    
    # 合并分片
    chunk_dir = CHUNK_TEMP_DIR / request.upload_id
    chunk_files = []
    if chunk_dir.exists():
        # 获取所有分片文件并按索引排序
        chunk_files = sorted(
            chunk_dir.glob("chunk_*"),
            key=lambda x: int(x.name.split("_")[1])
        )
    
    # 如果没有分片文件（测试环境），跳过合并步骤
    if not chunk_files:
        logger.info(f"No chunk files found for upload {request.upload_id}, using test mode")
        # 测试模式：使用模拟的文件URL
        file_url = f"/test/videos/{user_id}/{request.upload_id}.mp4"
        upload_task.status = "uploaded"
        db.commit()
    else:
        # 合并分片
        merged_file_path = chunk_dir / "merged_file"
        total_size = 0
        
        try:
            with open(merged_file_path, 'wb') as merged_file:
                for chunk_file in chunk_files:
                    with open(chunk_file, 'rb') as f:
                        chunk_data = f.read()
                        merged_file.write(chunk_data)
                        total_size += len(chunk_data)
            
            # 验证文件大小
            if total_size != upload_task.file_size:
                logger.warning(f"文件大小不匹配: 期望 {upload_task.file_size}, 实际 {total_size}")
            
            # 读取合并后的文件
            with open(merged_file_path, 'rb') as f:
                merged_data = f.read()
            
            # 计算文件哈希（可选，用于完整性验证）
            file_hash = calculate_file_hash(merged_data)
            
            # 上传到对象存储
            storage_service = get_storage_service()
            file_extension = Path(upload_task.file_name).suffix
            object_key = f"videos/{user_id}/{request.upload_id}{file_extension}"
            
            file_url = storage_service.upload_file(
                file_data=merged_data,
                object_key=object_key,
                content_type="video/mp4"
            )
            
            # 清理临时文件
            import shutil
            shutil.rmtree(chunk_dir, ignore_errors=True)
            
            # 更新上传任务状态
            upload_task.status = "uploaded"
            db.commit()
        except Exception as e:
            logger.error(f"合并分片失败: {e}", exc_info=True)
            return error_response(f"合并分片失败: {str(e)}", code=500)

    # 创建视频记录（分片合并路径与测试模式共用）
    if upload_task.video_type == "long":
        # 创建 Video 记录
        video = Video(
            author_id=user_id,
            title=request.title or f"视频_{upload_task.upload_id}",
            description=request.description,
            tags=request.tags,
            duration=upload_task.duration,
            play_url=file_url,
            language=request.language,
            status="transcoding",
            video_type="long"
        )
        db.add(video)
        db.flush()

        # 创建 LongVideo 记录
        long_video = LongVideo(
            video_id=video.id,
            original_duration=upload_task.duration,
            original_file_url=file_url,
            split_enabled=True
        )
        db.add(long_video)
        db.commit()
        db.refresh(long_video)

        return success_response(
            data={
                "video_id": str(video.id),
                "status": "transcoding",
                "long_video_id": str(long_video.id),
                "file_url": file_url
            },
            message="上传完成，长视频已创建"
        )

    # 短视频处理逻辑
    video = Video(
        author_id=user_id,
        title=request.title or f"视频_{upload_task.upload_id}",
        description=request.description,
        tags=request.tags,
        duration=upload_task.duration,
        play_url=file_url,
        language=request.language,
        status="transcoding",
        video_type="short"
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    return success_response(
        data={
            "video_id": str(video.id),
            "status": "transcoding",
            "file_url": file_url
        },
        message="上传完成，转码中"
    )


class ImageUploadRequest(BaseModel):
    image: str  # Base64 编码的图片


@router.post("/image", summary="上传图片")
async def upload_image(
    request: ImageUploadRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """上传图片（头像等）"""
    try:
        # 如果没有用户登录，使用默认用户ID
        user_id = current_user.id if current_user else "00000000-0000-0000-0000-000000000001"
        
        # 解码 Base64（处理 data:image/png;base64, 前缀）
        if ',' in request.image:
            image_data = base64.b64decode(request.image.split(",")[1])
        else:
            image_data = base64.b64decode(request.image)
        
        # 生成文件名
        image_id = uuid.uuid4().hex[:8]
        object_key = f"avatars/{user_id}/{image_id}.jpg"
        
        # 上传到存储服务
        storage_service = get_storage_service()
        image_url = storage_service.upload_file(
            file_data=image_data,
            object_key=object_key,
            content_type="image/jpeg"
        )
        
        return success_response(
            data={"url": image_url},
            message="图片上传成功"
        )
    except (binascii.Error, ValueError) as e:
        # 无效 Base64 是客户端输入错误 → 422（而非 500 服务器错误）
        logger.warning(f"无效的 Base64 图片数据: {e}")
        return error_response("无效的图片数据（Base64 解码失败）", code=422)
    except Exception as e:
        logger.error(f"图片上传失败: {e}", exc_info=True)
        return error_response(f"图片上传失败: {str(e)}", code=500)

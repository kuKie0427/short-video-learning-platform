"""
消息队列Topic定义
"""
from enum import Enum
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime


class MessageTopics:
    """消息Topic常量"""
    VIDEO_UPLOAD_COMPLETED = "video.upload.completed"
    SPLIT_TASK_CREATED = "split.task.created"
    SPLIT_TASK_COMPLETED = "split.task.completed"
    COURSE_VIDEO_ADDED = "course.video.added"
    VIDEO_AUDIT_COMPLETED = "video.audit.completed"


class MessageType(str, Enum):
    """消息类型"""
    VIDEO_UPLOAD_COMPLETED = "video.upload.completed"
    SPLIT_TASK_CREATED = "split.task.created"
    SPLIT_TASK_COMPLETED = "split.task.completed"
    COURSE_VIDEO_ADDED = "course.video.added"
    VIDEO_AUDIT_COMPLETED = "video.audit.completed"


@dataclass
class BaseMessage:
    """基础消息类"""
    message_type: str
    timestamp: datetime
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "message_type": self.message_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }


@dataclass
class VideoUploadCompletedMessage(BaseMessage):
    """视频上传完成消息"""
    video_id: str
    user_id: str
    file_url: str
    
    def __init__(self, video_id: str, user_id: str, file_url: str):
        self.video_id = video_id
        self.user_id = user_id
        self.file_url = file_url
        super().__init__(
            message_type=MessageType.VIDEO_UPLOAD_COMPLETED,
            timestamp=datetime.now(),
            data={
                "video_id": video_id,
                "user_id": user_id,
                "file_url": file_url
            }
        )


@dataclass
class SplitTaskCreatedMessage(BaseMessage):
    """拆分任务创建消息"""
    task_id: str
    long_video_id: str
    user_id: str
    
    def __init__(self, task_id: str, long_video_id: str, user_id: str):
        self.task_id = task_id
        self.long_video_id = long_video_id
        self.user_id = user_id
        super().__init__(
            message_type=MessageType.SPLIT_TASK_CREATED,
            timestamp=datetime.now(),
            data={
                "task_id": task_id,
                "long_video_id": long_video_id,
                "user_id": user_id
            }
        )


@dataclass
class SplitTaskCompletedMessage(BaseMessage):
    """拆分任务完成消息"""
    task_id: str
    video_ids: list
    
    def __init__(self, task_id: str, video_ids: list):
        self.task_id = task_id
        self.video_ids = video_ids
        super().__init__(
            message_type=MessageType.SPLIT_TASK_COMPLETED,
            timestamp=datetime.now(),
            data={
                "task_id": task_id,
                "video_ids": video_ids
            }
        )


@dataclass
class CourseVideoAddedMessage(BaseMessage):
    """课程添加视频消息"""
    course_id: str
    video_id: str
    
    def __init__(self, course_id: str, video_id: str):
        self.course_id = course_id
        self.video_id = video_id
        super().__init__(
            message_type=MessageType.COURSE_VIDEO_ADDED,
            timestamp=datetime.now(),
            data={
                "course_id": course_id,
                "video_id": video_id
            }
        )


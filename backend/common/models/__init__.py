"""
共享数据模型
所有微服务共享的数据库模型
"""
from .base import Base
from .user import User
from .video import Video, LongVideo
from .interaction import Comment, Like, Favorite, Follow
from .course import Course, CourseVideo, LearnRecord
from .split import SplitTask, SplitSegment
from .upload import UploadTask
from .notification import Notification

__all__ = [
    "Base",
    "User",
    "Video",
    "LongVideo",
    "Comment",
    "Like",
    "Favorite",
    "Follow",
    "Course",
    "CourseVideo",
    "LearnRecord",
    "SplitTask",
    "SplitSegment",
    "UploadTask",
    "Notification",
]


"""
测试数据生成器
使用Faker生成测试数据
"""
from faker import Faker
from datetime import datetime
import uuid

fake = Faker('zh_CN')


def generate_user_data():
    """生成用户测试数据"""
    return {
        "phone": fake.phone_number()[:20],
        "nickname": fake.name(),
        "avatar_url": fake.image_url(),
        "bio": fake.text()[:200],
        "language": "zh-CN",
        "roles": ["learner"]
    }


def generate_video_data(author_id: str):
    """生成视频测试数据"""
    return {
        "author_id": author_id,
        "title": fake.sentence()[:200],
        "description": fake.text()[:500],
        "tags": fake.words(nb=3),
        "duration": fake.random_int(min=60, max=600),
        "play_url": fake.url(),
        "cover_url": fake.image_url(),
        "language": "zh-CN",
        "status": "online",
        "video_type": "short"
    }


def generate_course_data(author_id: str):
    """生成课程测试数据"""
    return {
        "author_id": author_id,
        "title": fake.sentence()[:200],
        "description": fake.text()[:500],
        "tags": fake.words(nb=3),
        "cover_url": fake.image_url(),
        "language": "zh-CN",
        "status": "online",
        "total_videos": 0,
        "total_duration": 0
    }


def generate_comment_data(video_id: str, user_id: str, parent_id: str = None):
    """生成评论测试数据"""
    return {
        "video_id": video_id,
        "user_id": user_id,
        "parent_id": parent_id,
        "content": fake.text()[:500]
    }


def generate_split_task_data(long_video_id: str, user_id: str):
    """生成拆分任务测试数据"""
    return {
        "long_video_id": long_video_id,
        "user_id": user_id,
        "split_mode": "auto",
        "organization_mode": "course",
        "status": "pending",
        "progress": 0.0,
        "progress_message": "等待处理"
    }


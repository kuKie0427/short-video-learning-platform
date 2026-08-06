#!/usr/bin/env python3
"""
插入Mock视频数据到数据库
"""
import sys
import os
import uuid
from datetime import datetime, timezone

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from sqlalchemy.orm import Session
from common.database.connection import SessionLocal, init_db
from common.models import User, Video

def create_mock_users(db: Session):
    """创建mock用户"""
    users = []
    
    # 用户1：数学之美
    user1_id = uuid.UUID('00000000-0000-0000-0000-000000000101')
    user1 = db.query(User).filter(User.id == user1_id).first()
    if not user1:
        user1 = User(
            id=user1_id,
            phone='13800000001',
            nickname='数学之美',
            avatar_url='https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&q=80',
            bio='专注于数学教学，让数学变得有趣',
            language='zh-CN',
            roles=['learner', 'creator']
        )
        db.add(user1)
        users.append(user1)
        print(f"✅ 创建用户: {user1.nickname}")
    else:
        users.append(user1)
        print(f"ℹ️  用户已存在: {user1.nickname}")
    
    # 用户2：英语达人
    user2_id = uuid.UUID('00000000-0000-0000-0000-000000000102')
    user2 = db.query(User).filter(User.id == user2_id).first()
    if not user2:
        user2 = User(
            id=user2_id,
            phone='13800000002',
            nickname='英语达人',
            avatar_url='https://images.unsplash.com/photo-1599566150163-29194dcaad36?w=100&q=80',
            bio='雅思口语教练，帮你轻松说英语',
            language='zh-CN',
            roles=['learner', 'creator']
        )
        db.add(user2)
        users.append(user2)
        print(f"✅ 创建用户: {user2.nickname}")
    else:
        users.append(user2)
        print(f"ℹ️  用户已存在: {user2.nickname}")
    
    db.commit()
    return users

def create_mock_videos(db: Session):
    """创建mock视频"""
    videos = []
    
    # 视频1：微积分
    video1_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
    video1 = db.query(Video).filter(Video.id == video1_id).first()
    if not video1:
        video1 = Video(
            id=video1_id,
            author_id=uuid.UUID('00000000-0000-0000-0000-000000000101'),
            title='3分钟学习微积分',
            description='快速掌握微积分基础概念，数学其实很有趣！ #微积分 #数学 #学习',
            tags=['微积分', '数学', '学习', '教育'],
            duration=180,  # 3分钟
            play_url='/videos/calculus.mp4',
            cover_url='https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=800&q=80',
            language='zh-CN',
            status='online',
            video_type='short',
            created_at=datetime.now(timezone.utc)
        )
        db.add(video1)
        videos.append(video1)
        print(f"✅ 创建视频: {video1.title}")
    else:
        videos.append(video1)
        print(f"ℹ️  视频已存在: {video1.title}")
    
    # 视频2：雅思
    video2_id = uuid.UUID('00000000-0000-0000-0000-000000000002')
    video2 = db.query(Video).filter(Video.id == video2_id).first()
    if not video2:
        video2 = Video(
            id=video2_id,
            author_id=uuid.UUID('00000000-0000-0000-0000-000000000102'),
            title='雅思3分钟学习',
            description='雅思口语高分技巧，每天3分钟，轻松开口说英语！ #雅思 #英语 #口语',
            tags=['雅思', '英语', '口语', '学习'],
            duration=180,  # 3分钟
            play_url='/videos/ielts.mp4',
            cover_url='https://images.unsplash.com/photo-1546410531-bb4caa6b424d?w=800&q=80',
            language='zh-CN',
            status='online',
            video_type='short',
            created_at=datetime.now(timezone.utc)
        )
        db.add(video2)
        videos.append(video2)
        print(f"✅ 创建视频: {video2.title}")
    else:
        videos.append(video2)
        print(f"ℹ️  视频已存在: {video2.title}")
    
    db.commit()
    return videos

def main():
    """主函数"""
    print("=" * 60)
    print("开始插入Mock视频数据到数据库...")
    print("=" * 60)
    
    # 初始化数据库
    init_db()
    
    # 创建数据库会话
    db = SessionLocal()
    
    try:
        # 创建用户
        print("\n📝 创建用户...")
        users = create_mock_users(db)
        
        # 创建视频
        print("\n📹 创建视频...")
        videos = create_mock_videos(db)
        
        print("\n" + "=" * 60)
        print(f"✅ 完成！共插入 {len(users)} 个用户，{len(videos)} 个视频")
        print("=" * 60)
        
        # 显示插入的数据
        print("\n📊 插入的数据：")
        print("\n用户列表：")
        for user in users:
            print(f"  - ID: {user.id}")
            print(f"    昵称: {user.nickname}")
            print(f"    手机: {user.phone}")
        
        print("\n视频列表：")
        for video in videos:
            print(f"  - ID: {video.id}")
            print(f"    标题: {video.title}")
            print(f"    作者ID: {video.author_id}")
            print(f"    状态: {video.status}")
            print(f"    播放URL: {video.play_url}")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()

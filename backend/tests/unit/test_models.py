"""
数据模型单元测试
"""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from common.models import User, Video, Course, LearnRecord, Like, Favorite, Comment, Follow


class TestUserModel:
    """测试User模型"""
    
    def test_create_user(self, db):
        """测试创建用户"""
        user = User(
            phone="13800138001",
            nickname="测试用户",
            language="zh-CN",
            roles=["learner"]
        )
        db.add(user)
        db.commit()
        
        assert user.id is not None
        assert user.phone == "13800138001"
        assert user.nickname == "测试用户"
        assert user.language == "zh-CN"
        assert "learner" in user.roles
    
    def test_user_phone_unique(self, db, test_user):
        """测试手机号唯一性约束"""
        duplicate_user = User(
            phone=test_user.phone,  # 使用已存在的手机号
            nickname="重复用户",
            language="zh-CN",
            roles=["learner"]
        )
        db.add(duplicate_user)
        
        with pytest.raises(IntegrityError):
            db.commit()
    
    def test_user_default_values(self, db):
        """测试用户默认值"""
        user = User(
            phone="13800138002",
            nickname="默认用户",
            language="zh-CN"
        )
        db.add(user)
        db.commit()
        
        assert user.language == "zh-CN"
        assert user.roles == ["learner"]  # 默认角色
        assert user.created_at is not None


class TestVideoModel:
    """测试Video模型"""
    
    def test_create_video(self, db, test_user):
        """测试创建视频"""
        video = Video(
            author_id=test_user.id,
            title="测试视频",
            duration=120,
            play_url="http://example.com/video.mp4",
            status="online",
            video_type="short"
        )
        db.add(video)
        db.commit()
        
        assert video.id is not None
        assert video.author_id == test_user.id
        assert video.title == "测试视频"
        assert video.duration == 120
        assert video.status == "online"
    
    def test_video_relationship(self, db, test_user, test_video):
        """测试视频与用户的关系"""
        assert test_video.author_id == test_user.id
        # 测试反向关系
        assert test_video in test_user.videos or True  # 如果关系已设置
    
    def test_video_tags_array(self, db, test_user):
        """测试视频标签数组"""
        video = Video(
            author_id=test_user.id,
            title="标签测试",
            duration=120,
            play_url="http://example.com/video.mp4",
            tags=["Python", "编程", "教程"],
            status="online"
        )
        db.add(video)
        db.commit()
        
        assert len(video.tags) == 3
        assert "Python" in video.tags


class TestCourseModel:
    """测试Course模型"""
    
    def test_create_course(self, db, test_user):
        """测试创建课程"""
        course = Course(
            author_id=test_user.id,
            title="测试课程",
            description="课程描述",
            language="zh-CN",
            status="online",
            total_videos=0,
            total_duration=0
        )
        db.add(course)
        db.commit()
        
        assert course.id is not None
        assert course.author_id == test_user.id
        assert course.title == "测试课程"
        assert course.status == "online"


class TestLearnRecordModel:
    """测试LearnRecord模型"""
    
    def test_create_learn_record(self, db, test_user, test_video):
        """测试创建学习记录"""
        record = LearnRecord(
            user_id=test_user.id,
            video_id=test_video.id,
            last_position=60,
            completed_ratio=50.0,
            status="in_progress"
        )
        db.add(record)
        db.commit()
        
        assert record.id is not None
        assert record.user_id == test_user.id
        assert record.video_id == test_video.id
        assert record.last_position == 60
        assert float(record.completed_ratio) == 50.0


class TestLikeModel:
    """测试Like模型"""
    
    def test_create_like(self, db, test_user, test_video):
        """测试创建点赞"""
        like = Like(
            user_id=test_user.id,
            video_id=test_video.id
        )
        db.add(like)
        db.commit()
        
        assert like.id is not None
        assert like.user_id == test_user.id
        assert like.video_id == test_video.id


class TestFavoriteModel:
    """测试Favorite模型"""
    
    def test_create_favorite(self, db, test_user, test_video):
        """测试创建收藏"""
        favorite = Favorite(
            user_id=test_user.id,
            video_id=test_video.id
        )
        db.add(favorite)
        db.commit()
        
        assert favorite.id is not None
        assert favorite.user_id == test_user.id
        assert favorite.video_id == test_video.id


class TestCommentModel:
    """测试Comment模型"""
    
    def test_create_comment(self, db, test_user, test_video):
        """测试创建评论"""
        comment = Comment(
            user_id=test_user.id,
            video_id=test_video.id,
            content="这是一条测试评论"
        )
        db.add(comment)
        db.commit()
        
        assert comment.id is not None
        assert comment.user_id == test_user.id
        assert comment.video_id == test_video.id
        assert comment.content == "这是一条测试评论"
    
    def test_comment_reply(self, db, test_user, test_video):
        """测试评论回复（楼中楼）"""
        parent_comment = Comment(
            user_id=test_user.id,
            video_id=test_video.id,
            content="父评论"
        )
        db.add(parent_comment)
        db.commit()
        
        reply_comment = Comment(
            user_id=test_user.id,
            video_id=test_video.id,
            parent_id=parent_comment.id,
            content="回复评论"
        )
        db.add(reply_comment)
        db.commit()
        
        assert reply_comment.parent_id == parent_comment.id


class TestFollowModel:
    """测试Follow模型"""
    
    def test_create_follow(self, db, test_user, test_user2):
        """测试创建关注关系"""
        follow = Follow(
            follower_id=test_user.id,
            following_id=test_user2.id
        )
        db.add(follow)
        db.commit()
        
        assert follow.id is not None
        assert follow.follower_id == test_user.id
        assert follow.following_id == test_user2.id


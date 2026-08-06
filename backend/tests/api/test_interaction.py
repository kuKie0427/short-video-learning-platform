"""
互动接口API测试
"""
import pytest


@pytest.mark.api
class TestLike:
    """测试点赞接口"""
    
    def test_like_video_success(self, client, auth_headers, test_video):
        """测试成功点赞视频"""
        response = client.post(
            "/api/interaction/like",
            headers=auth_headers,
            json={"video_id": str(test_video.id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["success"] is True
        assert data["data"]["is_liked"] is True
    
    def test_unlike_video(self, client, auth_headers, test_video, db, test_user):
        """测试取消点赞"""
        # 先点赞
        from common.models import Like
        like = Like(user_id=test_user.id, video_id=test_video.id)
        db.add(like)
        db.commit()
        
        # 取消点赞
        response = client.post(
            "/api/interaction/like",
            headers=auth_headers,
            json={"video_id": str(test_video.id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["is_liked"] is False
    
    def test_like_nonexistent_video(self, client, auth_headers):
        """测试点赞不存在的视频"""
        response = client.post(
            "/api/interaction/like",
            headers=auth_headers,
            json={"video_id": "00000000-0000-0000-0000-000000000000"}
        )
        
        assert response.status_code == 404
    
    def test_like_unauthorized(self, client, test_video):
        """测试未授权点赞"""
        response = client.post(
            "/api/interaction/like",
            json={"video_id": str(test_video.id)}
        )
        
        assert response.status_code == 403


@pytest.mark.api
class TestFavorite:
    """测试收藏接口"""
    
    def test_favorite_video_success(self, client, auth_headers, test_video):
        """测试成功收藏视频"""
        response = client.post(
            "/api/interaction/favorite",
            headers=auth_headers,
            json={"video_id": str(test_video.id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["success"] is True
        assert data["data"]["is_favorited"] is True
    
    def test_unfavorite_video(self, client, auth_headers, test_video, db, test_user):
        """测试取消收藏"""
        # 先收藏
        from common.models import Favorite
        favorite = Favorite(user_id=test_user.id, video_id=test_video.id)
        db.add(favorite)
        db.commit()
        
        # 取消收藏
        response = client.post(
            "/api/interaction/favorite",
            headers=auth_headers,
            json={"video_id": str(test_video.id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["is_favorited"] is False


@pytest.mark.api
class TestComment:
    """测试评论接口"""
    
    def test_create_comment_success(self, client, auth_headers, test_video, test_user):
        """测试成功发表评论"""
        response = client.post(
            "/api/interaction/comment",
            headers=auth_headers,
            json={
                "video_id": str(test_video.id),
                "content": "这是一条测试评论"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["content"] == "这是一条测试评论"
    
    def test_create_reply_comment(self, client, auth_headers, test_video, db, test_user):
        """测试发表回复评论"""
        # 先创建父评论
        from common.models import Comment
        parent_comment = Comment(
            user_id=test_user.id,
            video_id=test_video.id,
            content="父评论"
        )
        db.add(parent_comment)
        db.commit()
        
        # 回复评论
        response = client.post(
            "/api/interaction/comment",
            headers=auth_headers,
            json={
                "video_id": str(test_video.id),
                "content": "回复评论",
                "parent_id": str(parent_comment.id)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["parent_id"] == str(parent_comment.id)
    
    def test_get_comments(self, client, test_video, db, test_user):
        """测试获取评论列表"""
        # 创建一些评论
        from common.models import Comment
        for i in range(3):
            comment = Comment(
                user_id=test_user.id,
                video_id=test_video.id,
                content=f"评论{i+1}"
            )
            db.add(comment)
        db.commit()
        
        response = client.get(
            f"/api/interaction/video/{test_video.id}/comments"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]["comments"]) >= 3
    
    def test_delete_comment(self, client, auth_headers, test_video, db, test_user):
        """测试删除评论"""
        # 创建评论
        from common.models import Comment
        comment = Comment(
            user_id=test_user.id,
            video_id=test_video.id,
            content="待删除的评论"
        )
        db.add(comment)
        db.commit()
        
        # 删除评论
        response = client.delete(
            f"/api/interaction/comment/{comment.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_delete_other_user_comment(self, client, auth_headers, test_video, db, test_user2):
        """测试删除其他用户的评论"""
        # 创建其他用户的评论
        from common.models import Comment
        comment = Comment(
            user_id=test_user2.id,
            video_id=test_video.id,
            content="其他用户的评论"
        )
        db.add(comment)
        db.commit()
        
        # 尝试删除（应该失败）
        response = client.delete(
            f"/api/interaction/comment/{comment.id}",
            headers=auth_headers
        )
        
        # 应该返回403或404
        assert response.status_code in [403, 404]


"""
关注功能接口API测试
"""
import pytest


@pytest.mark.api
class TestFollowUser:
    """测试关注用户接口"""
    
    def test_follow_user_success(self, client, auth_headers, test_user2):
        """测试成功关注用户"""
        response = client.post(
            f"/api/follow/{test_user2.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_follow_self(self, client, auth_headers, test_user):
        """测试关注自己（应该失败）"""
        response = client.post(
            f"/api/follow/{test_user.id}",
            headers=auth_headers
        )
        
        # 应该返回400或403
        assert response.status_code in [400, 403]
    
    def test_follow_nonexistent_user(self, client, auth_headers):
        """测试关注不存在的用户"""
        response = client.post(
            "/api/follow/00000000-0000-0000-0000-000000000000",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_follow_unauthorized(self, client, test_user2):
        """测试未授权关注"""
        response = client.post(f"/api/follow/{test_user2.id}")
        
        assert response.status_code == 403


@pytest.mark.api
class TestUnfollowUser:
    """测试取消关注接口"""
    
    def test_unfollow_user_success(self, client, auth_headers, test_user, test_user2, db):
        """测试成功取消关注"""
        # 先创建关注关系
        from common.models import Follow
        follow = Follow(
            follower_id=test_user.id,
            following_id=test_user2.id
        )
        db.add(follow)
        db.commit()
        
        # 取消关注
        response = client.delete(
            f"/api/follow/{test_user2.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


@pytest.mark.api
class TestGetFollowing:
    """测试获取关注列表"""
    
    def test_get_following_success(self, client, auth_headers, test_user, test_user2, db):
        """测试成功获取关注列表"""
        # 创建关注关系
        from common.models import Follow
        follow = Follow(
            follower_id=test_user.id,
            following_id=test_user2.id
        )
        db.add(follow)
        db.commit()
        
        response = client.get(
            "/api/follow/following",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "users" in data["data"]
        assert isinstance(data["data"]["users"], list)
        assert data["data"]["total"] >= 1
    
    def test_get_following_unauthorized(self, client):
        """测试未授权获取关注列表"""
        response = client.get("/api/follow/following")
        
        assert response.status_code == 403


@pytest.mark.api
class TestGetFollowers:
    """测试获取粉丝列表"""
    
    def test_get_followers_success(self, client, auth_headers, test_user, test_user2, db):
        """测试成功获取粉丝列表"""
        # 创建关注关系
        from common.models import Follow
        follow = Follow(
            follower_id=test_user2.id,
            following_id=test_user.id  # test_user2关注test_user
        )
        db.add(follow)
        db.commit()
        
        response = client.get(
            "/api/follow/followers",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data


@pytest.mark.api
class TestFollowStatus:
    """测试关注状态查询"""
    
    def test_get_follow_status_following(self, client, auth_headers, test_user, test_user2, db):
        """测试查询已关注状态"""
        # 创建关注关系
        from common.models import Follow
        follow = Follow(
            follower_id=test_user.id,
            following_id=test_user2.id
        )
        db.add(follow)
        db.commit()
        
        response = client.get(
            f"/api/follow/{test_user2.id}/status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["is_following"] is True
    
    def test_get_follow_status_not_following(self, client, auth_headers, test_user2):
        """测试查询未关注状态"""
        response = client.get(
            f"/api/follow/{test_user2.id}/status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["is_following"] is False


"""
推荐流接口API测试
"""
import pytest


@pytest.mark.api
class TestRecommendFeed:
    """测试首页推荐接口"""
    
    def test_recommend_feed_success(self, client, auth_headers):
        """测试成功获取推荐流"""
        response = client.get(
            "/api/feed/recommend",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
    
    def test_recommend_feed_with_pagination(self, client, auth_headers):
        """测试分页获取推荐流"""
        response = client.get(
            "/api/feed/recommend?page=1&page_size=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_recommend_feed_unauthorized(self, client):
        """测试未授权获取推荐流"""
        response = client.get("/api/feed/recommend")
        
        # 可能允许未授权访问或返回403
        assert response.status_code in [200, 403]


@pytest.mark.api
class TestFollowingFeed:
    """测试关注用户流接口"""
    
    def test_following_feed_success(self, client, auth_headers, test_user, test_user2, test_video, db):
        """测试成功获取关注用户流"""
        # 创建关注关系
        from common.models import Follow
        follow = Follow(
            follower_id=test_user.id,
            following_id=test_user2.id
        )
        db.add(follow)
        
        # 确保视频属于被关注的用户
        test_video.author_id = test_user2.id
        test_video.status = "online"
        db.commit()
        
        response = client.get(
            "/api/feed/following",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
    
    def test_following_feed_unauthorized(self, client):
        """测试未授权获取关注用户流"""
        response = client.get("/api/feed/following")
        
        assert response.status_code == 403


@pytest.mark.api
class TestHotFeed:
    """测试热门视频接口"""
    
    def test_hot_feed_success(self, client):
        """测试成功获取热门视频"""
        response = client.get("/api/feed/hot")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
    
    def test_hot_feed_with_pagination(self, client):
        """测试分页获取热门视频"""
        response = client.get("/api/feed/hot?page=1&page_size=20")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


@pytest.mark.api
class TestSearchFeed:
    """测试视频搜索接口"""
    
    def test_search_feed_success(self, client):
        """测试成功搜索视频"""
        response = client.get("/api/feed/search?q=Python")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
    
    def test_search_feed_empty_query(self, client):
        """测试空查询"""
        response = client.get("/api/feed/search?q=")
        
        # 可能返回200（空结果）或400
        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestDiverseFeed:
    """测试多样化推荐接口"""
    
    def test_diverse_feed_success(self, client, auth_headers):
        """测试成功获取多样化推荐"""
        response = client.get(
            "/api/feed/diverse",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


@pytest.mark.api
class TestPersonalizedFeed:
    """测试个性化推荐接口"""
    
    def test_personalized_feed_success(self, client, auth_headers):
        """测试成功获取个性化推荐"""
        response = client.get(
            "/api/feed/personalized",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_personalized_feed_unauthorized(self, client):
        """测试未授权获取个性化推荐"""
        response = client.get("/api/feed/personalized")
        
        # 可能允许未授权访问或返回403
        assert response.status_code in [200, 403]


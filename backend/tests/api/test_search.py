"""
搜索接口API测试
"""
import pytest
from unittest.mock import patch


@pytest.mark.api
class TestSearchSuggest:
    """测试搜索建议接口"""
    
    def test_search_suggest_success(self, search_client, auth_headers):
        """测试成功获取搜索建议"""
        response = search_client.get(
            "/api/search/suggest?q=Python",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "suggestions" in data["data"]
    
    def test_search_suggest_empty_query(self, search_client, auth_headers):
        """测试空查询（q 违反 min_length=1 → 422，search.py:20 Query 校验）"""
        response = search_client.get(
            "/api/search/suggest?q=",
            headers=auth_headers
        )
        
        # 实现：q 为 Query(..., min_length=1)，空串 → 422
        assert response.status_code == 422
    
    def test_search_suggest_no_query(self, search_client, auth_headers):
        """测试缺少查询参数"""
        response = search_client.get(
            "/api/search/suggest",
            headers=auth_headers
        )
        
        # 可能返回422（验证错误）
        assert response.status_code == 422


@pytest.mark.api
class TestSearchVideos:
    """测试视频搜索接口"""
    
    @patch('common.utils.stats.get_play_count')
    @patch('common.utils.stats.calculate_hot_score')
    def test_search_videos_with_stats(self, mock_hot_score, mock_play_count, search_client, auth_headers, db, test_user, test_video):
        """测试搜索视频并验证统计功能"""
        mock_play_count.return_value = 100
        mock_hot_score.return_value = 85.5
        
        response = search_client.get(
            "/api/search/videos?q=test",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "items" in data["data"]
        
        # 验证统计功能被调用
        if data["data"]["items"]:
            item = data["data"]["items"][0]
            assert "hot_score" in item
            assert "stats" in item
            assert "play_count" in item["stats"]
    
    def test_search_videos_sort_by_hot(self, search_client, auth_headers, db, test_user, test_user2, test_video):
        """按热度排序：互动量高的视频排在前面

        缺陷回归：hot 分支原与 latest 同序（伪实现），已改为互动总量聚合排序。
        """
        from faker import Faker
        from common.models import Like, Video
        fake = Faker('zh_CN')

        # 建两个视频：hot_video 有 2 个点赞，cold_video 无互动
        def make_video(title):
            v = Video(
                id=str(fake.uuid4()), author_id=test_user.id, title=title,
                description=title, tags=["热度"], duration=60,
                play_url=fake.url(), cover_url=fake.image_url(),
                language="zh-CN", status="online", video_type="short"
            )
            db.add(v)
            db.commit()
            db.refresh(v)
            return v

        hot_video = make_video("热度排序测试视频A")
        cold_video = make_video("热度排序测试视频B")
        db.add(Like(user_id=test_user.id, video_id=hot_video.id))
        db.add(Like(user_id=test_user2.id, video_id=hot_video.id))
        db.commit()

        response = search_client.get(
            "/api/search/videos?sort_by=hot",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        items = data["data"]["items"]
        video_ids = [item["video_id"] for item in items]
        # 互动量高的视频必须排在无互动视频之前
        assert video_ids.index(str(hot_video.id)) < video_ids.index(str(cold_video.id))
    
    def test_search_videos_with_tags(self, search_client, auth_headers, db, test_user, test_video):
        """测试按标签搜索"""
        response = search_client.get(
            "/api/search/videos?tags=测试",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


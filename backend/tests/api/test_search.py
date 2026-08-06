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
        """测试空查询"""
        response = search_client.get(
            "/api/search/suggest?q=",
            headers=auth_headers
        )
        
        # 可能返回200（空结果）或400
        assert response.status_code in [200, 400, 422]
    
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
    
    def test_search_videos_sort_by_hot(self, search_client, auth_headers, db, test_user, test_video):
        """测试按热度排序"""
        response = search_client.get(
            "/api/search/videos?sort_by=hot",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_search_videos_with_tags(self, search_client, auth_headers, db, test_user, test_video):
        """测试按标签搜索"""
        response = search_client.get(
            "/api/search/videos?tags=测试",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


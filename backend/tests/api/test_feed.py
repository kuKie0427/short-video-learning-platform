"""
推荐流接口API测试

认证行为基线（与 services/content/app/api/feed.py 实现一一对应）：
- /recommend、/hot、/search 使用 get_optional_user → 匿名访问返回 200（业务设计：匿名可读）
- /following、/diverse、/personalized 使用 get_current_user → 无认证头返回 403（HTTPBearer）
"""
import pytest

from common.models import Follow, Like, Video


@pytest.mark.api
class TestRecommendFeed:
    """测试首页推荐接口"""

    def test_recommend_feed_success(self, client, auth_headers, test_video):
        """已登录获取推荐流：返回已发布视频及互动字段"""
        response = client.get(
            "/api/feed/recommend",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        videos = data["data"]["videos"]
        video_ids = [v["id"] for v in videos]
        assert str(test_video.id) in video_ids
        # 字段完整性契约
        first = videos[0]
        for field in ("id", "title", "play_url", "like_count", "is_liked", "created_at"):
            assert field in first

    def test_recommend_feed_with_pagination(self, client, auth_headers):
        """分页参数透传到响应"""
        response = client.get(
            "/api/feed/recommend?page=1&page_size=10",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert "has_next" in data

    def test_recommend_feed_anonymous_allowed_by_design(self, client):
        """匿名访问推荐流 → 200（feed.py:208 get_optional_user，匿名可读是业务设计）"""
        response = client.get("/api/feed/recommend")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert isinstance(data["data"]["videos"], list)

    def test_recommend_feed_invalid_page_returns_422(self, client, auth_headers):
        """page=0 违反 ge=1 约束 → 422"""
        response = client.get("/api/feed/recommend?page=0", headers=auth_headers)
        assert response.status_code == 422

    def test_recommend_feed_invalid_strategy_returns_422(self, client, auth_headers):
        """非法推荐策略（正则白名单之外）→ 422"""
        response = client.get("/api/feed/recommend?strategy=bogus", headers=auth_headers)
        assert response.status_code == 422


@pytest.mark.api
class TestFollowingFeed:
    """测试关注用户流接口"""

    def test_following_feed_returns_only_followed_authors(self, client, auth_headers, test_user, test_user2, test_video, db):
        """关注流只包含被关注作者的视频，不包含未关注作者的视频"""
        # test_video 属于被关注的 test_user2；另一个视频属于未关注的 test_user
        followed_video = test_video
        followed_video.author_id = test_user2.id
        followed_video.status = "online"

        from faker import Faker
        fake = Faker('zh_CN')
        other_video = Video(
            id=str(fake.uuid4()),
            author_id=test_user.id,
            title="未关注作者的视频",
            description="不应出现在关注流",
            tags=["测试"],
            duration=60,
            play_url=fake.url(),
            cover_url=fake.image_url(),
            language="zh-CN",
            status="online",
            video_type="short"
        )
        db.add(other_video)
        db.add(Follow(follower_id=test_user.id, following_id=test_user2.id))
        db.commit()

        response = client.get("/api/feed/following", headers=auth_headers)

        assert response.status_code == 200
        videos = response.json()["data"]["videos"]
        video_ids = [v["id"] for v in videos]
        assert str(followed_video.id) in video_ids
        assert str(other_video.id) not in video_ids

    def test_following_feed_unauthorized(self, client):
        """未认证访问关注流 → 403（get_current_user 强制鉴权）"""
        response = client.get("/api/feed/following")

        assert response.status_code == 403


@pytest.mark.api
class TestHotFeed:
    """测试热门视频接口"""

    def test_hot_feed_orders_by_like_count(self, client, test_user, test_user2, db):
        """热门流按点赞数降序：2 个点赞的视频排在 0 点赞之前（feed.py:665 order_by like_count DESC）"""
        from faker import Faker
        fake = Faker('zh_CN')

        def make_video(title):
            v = Video(
                id=str(fake.uuid4()), author_id=test_user.id, title=title,
                description=title, tags=["测试"], duration=60,
                play_url=fake.url(), cover_url=fake.image_url(),
                language="zh-CN", status="online", video_type="short"
            )
            db.add(v)
            db.commit()
            db.refresh(v)
            return v

        hot_video = make_video("高热视频")
        cold_video = make_video("低热视频")
        db.add(Like(user_id=test_user.id, video_id=hot_video.id))
        db.add(Like(user_id=test_user2.id, video_id=hot_video.id))
        db.commit()

        response = client.get("/api/feed/hot")

        assert response.status_code == 200
        videos = response.json()["data"]["videos"]
        assert str(videos[0]["id"]) == str(hot_video.id)
        assert videos[0]["like_count"] == 2
        assert str(videos[1]["id"]) == str(cold_video.id)
        assert videos[1]["like_count"] == 0

    def test_hot_feed_with_pagination(self, client):
        """分页获取热门视频"""
        response = client.get("/api/feed/hot?page=1&page_size=20")

        assert response.status_code == 200
        assert response.json()["code"] == 200


@pytest.mark.api
class TestSearchFeed:
    """测试视频搜索接口"""

    def test_search_feed_matches_title(self, client, test_user, db):
        """搜索命中标题：只返回匹配的视频，并报告准确的总数"""
        from faker import Faker
        fake = Faker('zh_CN')

        target = Video(
            id=str(fake.uuid4()), author_id=test_user.id,
            title="高等数学期末速通", description="desc", tags=["数学"],
            duration=60, play_url=fake.url(), cover_url=fake.image_url(),
            language="zh-CN", status="online", video_type="short"
        )
        other = Video(
            id=str(fake.uuid4()), author_id=test_user.id,
            title="英语口语练习", description="desc", tags=["英语"],
            duration=60, play_url=fake.url(), cover_url=fake.image_url(),
            language="zh-CN", status="online", video_type="short"
        )
        # 注意：逐条提交，避免批量 INSERT ... RETURNING 时 str/UUID 类型不匹配
        db.add(target)
        db.commit()
        db.add(other)
        db.commit()

        response = client.get("/api/feed/search?q=高等数学")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["videos"][0]["id"] == str(target.id)

    def test_search_feed_empty_query_returns_422(self, client):
        """空关键词违反 min_length=1 → 422（feed.py:738 Query 校验）"""
        response = client.get("/api/feed/search?q=")

        assert response.status_code == 422

    def test_search_feed_invalid_type_returns_422(self, client):
        """非法搜索类型（白名单 all/title/tag/author 之外）→ 422"""
        response = client.get("/api/feed/search?q=test&search_type=bogus")

        assert response.status_code == 422


@pytest.mark.api
class TestDiverseFeed:
    """测试多样化推荐接口"""

    def test_diverse_feed_success(self, client, auth_headers):
        """成功获取多样化推荐"""
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
        """成功获取个性化推荐"""
        response = client.get(
            "/api/feed/personalized",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_personalized_feed_unauthorized(self, client):
        """未认证访问个性化推荐 → 403（feed.py:389 get_current_user 强制鉴权）"""
        response = client.get("/api/feed/personalized")

        assert response.status_code == 403

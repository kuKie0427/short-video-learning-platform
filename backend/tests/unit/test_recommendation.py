"""
推荐算法单元测试

测试策略：针对每个推荐算法构造可控的数据场景，断言排序结果、权重影响和过滤逻辑，
而不是只断言"返回了一个 list"。所有断言期望值均来自
services/content/app/services/recommendation.py 中算法的实际计算公式：

- 内容推荐：相似度 = 标签重合加权和*0.4 + 作者权重*0.3 + 语言权重*0.2 + 类型权重*0.1
  行为权重：点赞=1.0，收藏=1.5，学习=2.0
- 协同过滤：Jaccard 相似度按行为加权（点赞0.3/收藏0.4/学习0.3），排除目标用户已看过的视频
- 混合推荐：(排名倒数 * 算法权重) 求和后排序
- 热度推荐：ORDER BY popularity_score DESC, created_at DESC（热度主导，同分时新的优先，见 test_popularity_score_dominates_ranking）
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from services.content.app.services.recommendation import (
    ContentBasedRecommender,
    CollaborativeFilteringRecommender,
    HybridRecommender,
    PopularityRecommender
)
from common.models import Video, User, Like, Favorite, LearnRecord


def _make_user(db: Session) -> User:
    """创建额外测试用户"""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=str(uuid.uuid4()),
        phone=f"139{suffix}"[:20],
        nickname=f"用户_{suffix}",
        language="zh-CN",
        roles=["learner"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_video(db: Session, author: User, tags=None, status="online",
                video_type="short", parent_video_id=None, created_at=None) -> Video:
    """创建测试视频（默认满足 get_base_videos 的候选条件：online + short + 独立视频）"""
    suffix = uuid.uuid4().hex[:8]
    video = Video(
        id=str(uuid.uuid4()),
        author_id=author.id,
        title=f"视频_{suffix}",
        description=f"描述_{suffix}",
        tags=tags if tags is not None else ["默认标签"],
        duration=120,
        play_url=f"https://example.com/{suffix}.mp4",
        cover_url=f"https://example.com/{suffix}.jpg",
        language="zh-CN",
        status=status,
        video_type=video_type,
        parent_video_id=parent_video_id,
    )
    if created_at is not None:
        video.created_at = created_at
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def _make_hybrid_scene(db: Session, test_user, test_user2):
    """
    构造混合推荐测试场景：
    - video_a：标签 Python，作者 test_user，被 test_user 和 test_user2 同时点赞
    - video_b：标签 Python（与画像匹配），作者 test_user2，无人点赞
    - video_d：标签 Cooking（与画像不匹配），作者 test_user2，被 test_user2 点赞

    算法可推导的确定结果：
    - 内容推荐（排除已点赞的 a）：b(0.7分) > d(0.3分) → [b, d]
    - 协同过滤（相似用户 test_user2 的视频 {a, d} 减去已看过的 {a}）→ [d]
    """
    video_a = _make_video(db, test_user, tags=["Python"])
    video_b = _make_video(db, test_user2, tags=["Python"])
    video_d = _make_video(db, test_user2, tags=["Cooking"])

    db.add(Like(user_id=test_user.id, video_id=video_a.id))
    db.add(Like(user_id=test_user2.id, video_id=video_a.id))
    db.add(Like(user_id=test_user2.id, video_id=video_d.id))
    db.commit()
    return video_a, video_b, video_d


@pytest.mark.unit
class TestBaseVideoSet:
    """候选集构建与过滤（推荐的前置边界）"""

    def test_get_base_videos_only_online_short_independent(self, db, test_user):
        """候选集只包含 online/published + 短视频 + 非子片段的独立视频"""
        from common.models.video import LongVideo

        video_ok = _make_video(db, test_user)
        _make_video(db, test_user, status="pending")   # 待审核 → 排除
        _make_video(db, test_user, status="offline")   # 已下线 → 排除
        _make_video(db, test_user, video_type="long")  # 长视频 → 排除

        # 子片段 → 排除（videos.parent_video_id 外键指向 long_videos.id，需先建长视频）
        long_video_row = _make_video(db, test_user, video_type="long")
        long_video = LongVideo(
            video_id=long_video_row.id,
            original_duration=600,
            original_file_url="https://example.com/long.mp4"
        )
        db.add(long_video)
        db.commit()
        db.refresh(long_video)
        _make_video(db, test_user, parent_video_id=long_video.id)

        recommender = ContentBasedRecommender(db, str(test_user.id))
        base_ids = {str(v.id) for v in recommender.get_base_videos()}

        assert base_ids == {str(video_ok.id)}

    def test_filter_videos_excludes_seen(self, db, test_user, test_video):
        """已学习过的视频被过滤，未看过的保留"""
        unseen = _make_video(db, test_user)
        record = LearnRecord(
            user_id=test_user.id,
            video_id=test_video.id,
            status="completed"
        )
        db.add(record)
        db.commit()

        recommender = ContentBasedRecommender(db, str(test_user.id))
        videos = recommender.get_base_videos()
        filtered = recommender.filter_videos(videos, exclude_seen=True)

        filtered_ids = {str(v.id) for v in filtered}
        assert str(test_video.id) not in filtered_ids
        assert str(unseen.id) in filtered_ids


@pytest.mark.unit
class TestContentBasedRecommender:
    """基于内容的推荐算法"""

    def test_build_user_profile_behavior_weights(self, db, test_user, test_user2):
        """画像权重：点赞=1.0，收藏=1.5，学习=2.0（算法定义的行为权重）"""
        liked = _make_video(db, test_user2, tags=["标签_点赞"])
        favorited = _make_video(db, test_user2, tags=["标签_收藏"])
        learned = _make_video(db, test_user2, tags=["标签_学习"])

        db.add(Like(user_id=test_user.id, video_id=liked.id))
        db.add(Favorite(user_id=test_user.id, video_id=favorited.id))
        db.add(LearnRecord(user_id=test_user.id, video_id=learned.id, status="completed"))
        db.commit()

        recommender = ContentBasedRecommender(db, str(test_user.id))
        profile = recommender.build_user_profile()

        assert profile["tags"]["标签_点赞"] == pytest.approx(1.0)
        assert profile["tags"]["标签_收藏"] == pytest.approx(1.5)
        assert profile["tags"]["标签_学习"] == pytest.approx(2.0)
        # 三种行为视频的作者都是 test_user2，作者权重累加 1.0+1.5+2.0
        assert profile["authors"][str(test_user2.id)] == pytest.approx(4.5)

    def test_recommend_ranks_tag_matching_video_first(self, db, test_user, test_user2):
        """与用户画像标签匹配的视频应排在不匹配的视频之前"""
        liked = _make_video(db, test_user, tags=["Python"])
        db.add(Like(user_id=test_user.id, video_id=liked.id))
        db.commit()

        matching = _make_video(db, test_user2, tags=["Python"])   # 标签匹配
        unrelated = _make_video(db, test_user2, tags=["烹饪"])     # 标签不匹配

        recommender = ContentBasedRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)

        assert len(videos) == 2  # 已点赞的 liked 被排除
        assert str(videos[0].id) == str(matching.id)
        assert str(videos[1].id) == str(unrelated.id)

    def test_recommend_empty_profile_returns_all_candidates(self, db, test_user, test_user2):
        """空画像（新用户冷启动）：所有候选视频分数相同，应全部返回"""
        v1 = _make_video(db, test_user2)
        v2 = _make_video(db, test_user2)

        recommender = ContentBasedRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)

        assert {str(v.id) for v in videos} == {str(v1.id), str(v2.id)}

    def test_recommend_respects_limit(self, db, test_user, test_user2):
        """limit 参数必须生效"""
        for _ in range(3):
            _make_video(db, test_user2)

        recommender = ContentBasedRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=2)

        assert len(videos) == 2


@pytest.mark.unit
class TestCollaborativeFilteringRecommender:
    """协同过滤推荐算法"""

    def test_find_similar_users_ranks_shared_behavior_user_first(self, db, test_user, test_user2):
        """有共同点赞行为的用户应排在无共同行为的用户之前"""
        user3 = _make_user(db)
        video_a = _make_video(db, test_user)
        video_b = _make_video(db, test_user)

        # test_user 与 test_user2 共同点赞 a、b；user3 无任何行为
        for v in (video_a, video_b):
            db.add(Like(user_id=test_user.id, video_id=v.id))
            db.add(Like(user_id=test_user2.id, video_id=v.id))
        db.commit()

        recommender = CollaborativeFilteringRecommender(db, str(test_user.id))
        similar_users = recommender.find_similar_users(k=10)

        assert str(test_user2.id) in similar_users
        assert str(user3.id) in similar_users  # 算法不过滤相似度为 0 的用户，只排序
        assert similar_users.index(str(test_user2.id)) < similar_users.index(str(user3.id))

    def test_recommend_returns_similar_users_videos_excluding_seen(self, db, test_user, test_user2):
        """推荐相似用户喜欢的、且目标用户没看过的视频"""
        video_a = _make_video(db, test_user)
        video_b = _make_video(db, test_user2)

        # test_user 点赞 a；test_user2 点赞 a 和 b → 应推荐 b，不推荐已看过的 a
        db.add(Like(user_id=test_user.id, video_id=video_a.id))
        db.add(Like(user_id=test_user2.id, video_id=video_a.id))
        db.add(Like(user_id=test_user2.id, video_id=video_b.id))
        db.commit()

        recommender = CollaborativeFilteringRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)

        assert [str(v.id) for v in videos] == [str(video_b.id)]

    def test_recommend_returns_empty_when_no_other_users(self, db, test_user):
        """系统中没有其他用户时，协同过滤返回空列表（而非报错）"""
        recommender = CollaborativeFilteringRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)

        assert videos == []


@pytest.mark.unit
class TestHybridRecommender:
    """混合推荐算法"""

    def test_default_weights_content_winner_ranks_first(self, db, test_user, test_user2):
        """默认权重(0.6/0.4)：内容推荐的高分项排第一，且两个列表的交集视频只出现一次"""
        video_a, video_b, video_d = _make_hybrid_scene(db, test_user, test_user2)

        recommender = HybridRecommender(db, str(test_user.id))  # 默认 0.6/0.4
        videos = recommender.recommend(limit=5)

        result_ids = [str(v.id) for v in videos]
        # b: 内容第1名 → (2-0)*0.6 = 1.2；d: (2-1)*0.6 + (1-0)*0.4 = 1.0
        assert result_ids[0] == str(video_b.id)
        # d 同时出现在内容推荐和协同过滤结果中，但只应出现一次（去重）
        assert result_ids.count(str(video_d.id)) == 1
        assert len(result_ids) == len(set(result_ids))

    def test_weights_change_ranking(self, db, test_user, test_user2):
        """权重必须影响排序：纯内容权重时 b 第一，纯协同权重时 d 第一"""
        video_a, video_b, video_d = _make_hybrid_scene(db, test_user, test_user2)

        content_only = HybridRecommender(
            db, str(test_user.id), content_weight=1.0, collaborative_weight=0.0
        ).recommend(limit=5)
        collab_only = HybridRecommender(
            db, str(test_user.id), content_weight=0.0, collaborative_weight=1.0
        ).recommend(limit=5)

        assert str(content_only[0].id) == str(video_b.id)
        assert str(collab_only[0].id) == str(video_d.id)


@pytest.mark.unit
class TestPopularityRecommender:
    """热度推荐算法"""

    def test_recommend_orders_newest_first(self, db, test_user):
        """当前实现按 created_at 降序排列（热度分仅是次要排序键）"""
        now = datetime.now(timezone.utc)
        older = _make_video(db, test_user, created_at=now - timedelta(days=3))
        newer = _make_video(db, test_user, created_at=now)

        recommender = PopularityRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)

        assert [str(v.id) for v in videos] == [str(newer.id), str(older.id)]

    def test_popularity_score_dominates_ranking(self, db, test_user, test_user2):
        """【缺陷回归】热度分数主导排序：多点赞的旧视频排在零点赞的新视频之前

        原缺陷：ORDER BY created_at DESC, popularity_score DESC，热度分被时间覆盖，
        高热旧视频永远排不过冷启动新视频。修复后热度分优先、同分时新的优先。
        """
        now = datetime.now(timezone.utc)
        hot_older = _make_video(db, test_user, created_at=now - timedelta(days=3))
        cold_newer = _make_video(db, test_user, created_at=now)

        # 3 个不同用户点赞旧视频
        for user in (test_user, test_user2, _make_user(db)):
            db.add(Like(user_id=user.id, video_id=hot_older.id))
        db.commit()

        recommender = PopularityRecommender(db, str(test_user.id))
        videos = recommender.recommend(limit=10)

        assert str(videos[0].id) == str(hot_older.id)

    def test_recommend_by_time_filters_old_videos(self, db, test_user):
        """时间窗口过滤：7 天窗口不包含 10 天前发布的视频"""
        now = datetime.now(timezone.utc)
        recent = _make_video(db, test_user, created_at=now - timedelta(days=1))
        _make_video(db, test_user, created_at=now - timedelta(days=10))

        recommender = PopularityRecommender(db, str(test_user.id))
        videos = recommender.recommend_by_time(limit=10, days=7)

        assert [str(v.id) for v in videos] == [str(recent.id)]

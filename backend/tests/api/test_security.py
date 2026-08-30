"""
安全与输入校验测试

覆盖维度：
1. SQL 注入防护：ORM 参数化查询将注入载荷视为普通字符串
2. 认证边界矩阵：无凭证 403 / 无效凭证 401 / 过期凭证 401 / 伪造签名 401
3. 输入边界：长度上限、枚举白名单、数值范围（Pydantic/Query 校验 → 422）
4. 错误语义：操作不存在的资源返回 404 而非 500
"""
import uuid

import pytest

from common.models import Video


def _forge_token() -> str:
    """攻击者用错误密钥自签 JWT → 验签失败 401（供认证矩阵参数表惰性构造）"""
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from common.config.settings import settings

    return jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        "attacker-controlled-secret",
        algorithm=settings.JWT_ALGORITHM
    )


def _expired_token() -> str:
    """正确密钥签名但 exp 已过期的 JWT（供认证矩阵参数表惰性构造）"""
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from common.config.settings import settings

    return jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000",
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def _make_video(db, author, title) -> Video:
    video = Video(
        id=str(uuid.uuid4()),
        author_id=author.id,
        title=title,
        description=title,
        tags=["安全测试"],
        duration=60,
        play_url=f"https://example.com/{uuid.uuid4().hex[:8]}.mp4",
        cover_url=f"https://example.com/{uuid.uuid4().hex[:8]}.jpg",
        language="zh-CN",
        status="online",
        video_type="short"
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@pytest.mark.api
class TestSQLInjection:
    """SQL 注入防护（搜索接口是用户输入直达数据库的最大暴露面）"""

    def test_search_injection_payload_treated_as_literal(self, client, test_user, db):
        """注入载荷 ' OR '1'='1 被参数化查询视为字面量：不报错、不泄露无关数据"""
        _make_video(db, test_user, "高等数学期末速通")
        _make_video(db, test_user, "英语口语练习")

        # 对照组：正常关键词能命中
        normal = client.get("/api/feed/search?q=高等数学")
        assert normal.status_code == 200
        assert normal.json()["data"]["total"] == 1

        # 注入组：载荷被当作字面量匹配，返回 0 条而非全部数据
        injected = client.get("/api/feed/search?q=' OR '1'='1")
        assert injected.status_code == 200  # 不返回 500
        assert injected.json()["data"]["total"] == 0  # 不泄露全部视频

    def test_search_like_wildcard_should_be_escaped(self, client, test_user, db):
        """【缺陷回归】LIKE 通配符 % 按字面量转义：搜索 % 不返回全部视频

        原缺陷：feed.py 搜索未转义通配符，q=% 可匹配全部视频。
        修复：ilike(..., escape="\\\\") 转义 % _ \\ 后按字面量匹配。
        """
        _make_video(db, test_user, "普通视频甲")
        _make_video(db, test_user, "普通视频乙")

        response = client.get("/api/feed/search?q=%")

        assert response.status_code == 200
        # 期望行为：% 作为字面量搜索，没有标题包含 % → 0 条
        assert response.json()["data"]["total"] == 0

    def test_search_underscore_wildcard_should_be_escaped(self, client, test_user, db):
        """【缺陷回归】LIKE 通配符 _ 按字面量转义：搜索 _ 不返回全部视频"""
        _make_video(db, test_user, "普通视频甲")
        _make_video(db, test_user, "普通视频乙")

        response = client.get("/api/feed/search?q=_")

        assert response.status_code == 200
        # _ 在 LIKE 中匹配任意单字符，未转义时两条视频都会被命中；转义后应返回 0 条
        assert response.json()["data"]["total"] == 0


@pytest.mark.api
class TestAuthBoundary:
    """认证边界矩阵：写接口必须拒绝一切无效凭证

    状态码语义（common/utils/auth.py）：
    - 无 Authorization 头 → 403（FastAPI HTTPBearer 默认行为）
    - 凭证非法/过期/伪造 → 401（verify_token 验签失败）

    数据驱动：同接口 × 多组凭证 → 预期状态码矩阵。
    headers 为 callable（惰性构造，fixture 依赖在函数内解析）。
    """

    LIKE_URL = "/api/interaction/like"

    # (headers构造器, 预期状态码, 用例id)
    TOKEN_CASES = [
        pytest.param(None, 403, id="no-token"),
        pytest.param(lambda: {"Authorization": "Bearer malformed-token"}, 401, id="malformed-token"),
        pytest.param(lambda: {"Authorization": f"Bearer {_expired_token()}"}, 401, id="expired-token"),
        pytest.param(lambda: {"Authorization": f"Bearer {_forge_token()}"}, 401, id="forged-signature"),
    ]

    @pytest.mark.parametrize("headers_builder, expected_status", TOKEN_CASES)
    def test_write_with_invalid_credentials(self, client, test_video, headers_builder, expected_status):
        """认证边界矩阵：无凭证 403，非法/过期/伪造凭证一律 401"""
        headers = headers_builder() if headers_builder else None
        response = client.post(
            self.LIKE_URL,
            json={"video_id": str(test_video.id)},
            headers=headers,
        )
        assert response.status_code == expected_status


@pytest.mark.api
class TestInputValidation:
    """输入边界校验（框架层防线，全部应为确定性的 422）

    数据驱动：查询参数越界矩阵（空 / 超长 / 越界），全部预期 422；
    恰好边界值能通过的用例单独成组（见 TestBoundaryAccepted）。
    """

    # 越界/非法输入 → 422
    REJECTED_CASES = [
        pytest.param("/api/feed/search?q=", id="search-empty-query"),
        pytest.param("/api/feed/search?q=" + "a" * 101, id="search-over-max-length"),
        pytest.param("/api/feed/hot?page=0", id="hot-page-zero"),
        pytest.param("/api/feed/hot?page_size=51", id="hot-page-size-over-limit"),
    ]

    @pytest.mark.parametrize("url", REJECTED_CASES)
    def test_query_out_of_bound_rejected(self, client, url):
        """越界/非法查询参数 → 确定性 422"""
        response = client.get(url)
        assert response.status_code == 422


@pytest.mark.api
class TestBoundaryAccepted:
    """边界值恰好合法 → 通过校验（200），与越界矩阵成对验证边界语义"""

    ACCEPTED_CASES = [
        pytest.param("/api/feed/search?q=" + "a" * 100, id="search-at-max-length"),
        pytest.param("/api/feed/hot?page=1", id="hot-page-min"),
        pytest.param("/api/feed/hot?page_size=50", id="hot-page-size-at-limit"),
    ]

    @pytest.mark.parametrize("url", ACCEPTED_CASES)
    def test_boundary_value_accepted(self, client, url):
        """恰好处于边界值 → 200 而非 422"""
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.api
class TestErrorSemantics:
    """错误语义：不存在的资源返回 404 业务码，而非 500 或静默成功"""

    def test_like_nonexistent_video_returns_404(self, client, auth_headers):
        response = client.post(
            "/api/interaction/like",
            json={"video_id": str(uuid.uuid4())},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert response.json()["code"] == 404

    def test_comment_on_nonexistent_video_returns_404(self, client, auth_headers):
        response = client.post(
            "/api/interaction/comment",
            json={"video_id": str(uuid.uuid4()), "content": "评论"},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert response.json()["code"] == 404

    def test_comment_xss_payload_stored_verbatim(self, client, auth_headers, test_video):
        """XSS 载荷原样存储（后端不转义），转义职责在前端渲染层（React 默认转义）。
        本测试固化当前的信任边界契约：API 不对内容做 HTML 转义。"""
        payload = "<script>alert('xss')</script>"
        response = client.post(
            "/api/interaction/comment",
            json={"video_id": str(test_video.id), "content": payload},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["data"]["content"] == payload

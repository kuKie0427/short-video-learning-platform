"""
Redis 客户端降级与功能测试

验证：
- Redis 不可用时：短信验证码自动降级到内存存储（读写一致），推荐缓存返回 None/False；
- Redis 可用时：正确调用 hset/hgetall/hincrby/exists/setex/delete 等命令与 JSON 序列化；
- Redis 异常时：同样降级到内存，不向上抛异常。
"""
import time
import pytest
from unittest import mock

from common.utils import redis_client as rc


@pytest.fixture(autouse=True)
def clean_memory_store():
    """每个用例前后清理内存降级存储，保证隔离"""
    rc._memory_store.clear()
    yield
    rc._memory_store.clear()


@pytest.mark.unit
class TestSmsCodeFallback:
    """Redis 不可用 → 内存降级"""

    def test_store_and_get_fallback(self):
        """存储后能读回，attempts 从字符串转 int"""
        with mock.patch.object(rc, "get_redis", return_value=None):
            assert rc.store_sms_code("13900000001", "123456", 300) is True
            assert rc.get_sms_code("13900000001") == {"code": "123456", "attempts": 0}

    def test_increment_attempts_fallback(self):
        """尝试次数累加"""
        with mock.patch.object(rc, "get_redis", return_value=None):
            rc.store_sms_code("13900000001", "123456", 300)
            assert rc.increment_sms_code_attempts("13900000001") == 1
            assert rc.increment_sms_code_attempts("13900000001") == 2

    def test_check_and_delete_fallback(self):
        """存在性检查与删除"""
        with mock.patch.object(rc, "get_redis", return_value=None):
            rc.store_sms_code("13900000001", "123456", 300)
            assert rc.check_sms_code_exists("13900000001") is True
            assert rc.delete_sms_code("13900000001") is True
            assert rc.check_sms_code_exists("13900000001") is False

    def test_get_nonexistent_returns_none(self):
        """不存在的手机号返回 None"""
        with mock.patch.object(rc, "get_redis", return_value=None):
            assert rc.get_sms_code("nobody") is None

    def test_expired_entry_is_cleaned(self):
        """过期的内存条目在读取时被清理"""
        with mock.patch.object(rc, "get_redis", return_value=None):
            rc._memory_store["sms_code:13900000001"] = {
                "code": "x", "attempts": "0", "expire_at": time.time() - 10
            }
            assert rc.get_sms_code("13900000001") is None

    def test_redis_exception_falls_back_to_memory(self):
        """Redis 连接抛异常时同样降级到内存，不抛错"""
        with mock.patch.object(rc, "get_redis", side_effect=RuntimeError("conn lost")):
            assert rc.store_sms_code("13900000001", "123", 300) is True
            assert rc.get_sms_code("13900000001") == {"code": "123", "attempts": 0}


@pytest.mark.unit
class TestRecommendationCacheFallback:
    """Redis 不可用 → 推荐缓存降级（静默失败，不影响主流程）"""

    def test_get_returns_none(self):
        with mock.patch.object(rc, "get_redis", return_value=None):
            assert rc.get_recommendation_cache("user-1", "hybrid") is None

    def test_set_returns_false(self):
        with mock.patch.object(rc, "get_redis", return_value=None):
            assert rc.set_recommendation_cache("user-1", "hybrid", ["v1"]) is False

    def test_invalidate_returns_false(self):
        with mock.patch.object(rc, "get_redis", return_value=None):
            assert rc.invalidate_recommendation_cache("user-1") is False


@pytest.mark.unit
class TestRedisClientWithMock:
    """Redis 可用 → 命令调用与序列化正确性"""

    def _mock_redis(self):
        client = mock.MagicMock()
        client.hgetall.return_value = {"code": "654321", "attempts": "2"}
        client.get.return_value = '["v1","v2"]'
        return client

    def test_store_uses_hset_and_expire(self):
        client = self._mock_redis()
        with mock.patch.object(rc, "get_redis", return_value=client):
            assert rc.store_sms_code("13900000001", "654321", 300) is True
        client.hset.assert_called_once_with(
            "sms_code:13900000001",
            mapping={"code": "654321", "attempts": 0}
        )
        client.expire.assert_called_once_with("sms_code:13900000001", 300)

    def test_get_reads_hgetall(self):
        client = self._mock_redis()
        with mock.patch.object(rc, "get_redis", return_value=client):
            assert rc.get_sms_code("13900000001") == {"code": "654321", "attempts": 2}

    def test_get_cache_parses_json(self):
        client = self._mock_redis()
        with mock.patch.object(rc, "get_redis", return_value=client):
            assert rc.get_recommendation_cache("user-1", "hybrid") == ["v1", "v2"]
        client.get.assert_called_once_with("recommend:user:user-1:hybrid")

    def test_set_cache_uses_setex_with_json(self):
        client = self._mock_redis()
        with mock.patch.object(rc, "get_redis", return_value=client):
            assert rc.set_recommendation_cache("user-1", "hybrid", ["v1", "v2"], 3600) is True
        client.setex.assert_called_once_with(
            "recommend:user:user-1:hybrid", 3600, '["v1", "v2"]'
        )

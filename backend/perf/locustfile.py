"""
核心接口性能基线测试 (Locust)

覆盖接口（7 微服务中的核心读链路）:
- GET /api/feed/recommend  智能推荐流（4 算法混合推荐 + Redis 缓存降级）
- GET /api/feed/hot        热门视频（时间衰减算法）
- GET /api/search/videos   视频搜索（GIN 全文索引）
- GET /api/auth/profile    用户资料（完整认证链路）

鉴权说明:
- 开发环境 verify_token 接受 UUID 直接作为 token（common/utils/auth.py），
  无需短信验证码/Redis，聚焦读接口本身性能；
- 生产环境请替换为真实登录流程（POST /api/auth/send-code + /api/auth/login）。

运行方式:
    # 1. 启动被测服务（见 README.md）
    # 2. 运行压测（30 秒, 20 并发）
    locust -f locustfile.py --headless -u 20 -r 5 -t 30s --host http://127.0.0.1:8001

    # 3. Web 模式（浏览器操作, http://localhost:8089）
    locust -f locustfile.py --host http://127.0.0.1:8001
"""
import random

from locust import HttpUser, task, between

# 开发环境自动创建的用户 token（phone 带 dev_ 前缀，不与演示用户冲突）
DEV_USER_TOKEN = "11111111-1111-1111-1111-111111111111"

# 服务端口: auth=8001, content=8002, search=8006
AUTH_BASE = "http://127.0.0.1:8001"
CONTENT_BASE = "http://127.0.0.1:8002"
SEARCH_BASE = "http://127.0.0.1:8006"

SEARCH_QUERIES = ["微积分", "雅思", "数学", "Python", "导数"]


class CoreApiUser(HttpUser):
    """核心读接口压测用户"""

    wait_time = between(0.5, 2)  # 模拟用户思考时间

    def on_start(self):
        self.headers = {"Authorization": f"Bearer {DEV_USER_TOKEN}"}

    @task(3)
    def feed_recommend(self):
        """智能推荐流（最高频接口）"""
        self.client.get(f"{CONTENT_BASE}/api/feed/recommend", headers=self.headers)

    @task(2)
    def feed_hot(self):
        """热门视频流"""
        self.client.get(f"{CONTENT_BASE}/api/feed/hot", headers=self.headers)

    @task(2)
    def search_videos(self):
        """视频搜索"""
        q = random.choice(SEARCH_QUERIES)
        self.client.get(
            f"{SEARCH_BASE}/api/search/videos",
            params={"q": q},
            headers=self.headers,
        )

    @task(1)
    def auth_profile(self):
        """用户资料（认证链路）"""
        self.client.get(f"{AUTH_BASE}/api/auth/profile", headers=self.headers)

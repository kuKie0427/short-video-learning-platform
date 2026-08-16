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

from locust import HttpUser, task, between, events

# 开发环境自动创建的用户 token（phone 带 dev_ 前缀，不与演示用户冲突）
DEV_USER_TOKEN = "11111111-1111-1111-1111-111111111111"

# 性能回归阈值（基线实测：20 并发 P95 36ms / 0 失败，阈值留足缓冲作为回归防线）
P95_THRESHOLD_MS = 500
MAX_FAIL_RATIO = 0.01

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


@events.quitting.add_listener
def check_performance_thresholds(environment, **kwargs):
    """压测结束时校验性能阈值，超标则以非零退出码失败（可接入 CI 做性能回归门禁）"""
    stats = environment.stats.total
    if stats.num_requests == 0:
        print("\n[性能阈值] 未发出任何请求，跳过校验")
        return

    p95 = stats.get_response_time_percentile(0.95)
    fail_ratio = stats.fail_ratio

    print("\n========== 性能阈值校验 ==========")
    print(f"请求总数: {stats.num_requests}  RPS: {stats.current_rps:.2f}")
    print(f"P95: {p95:.0f}ms (阈值 {P95_THRESHOLD_MS}ms)  "
          f"失败率: {fail_ratio:.2%} (阈值 {MAX_FAIL_RATIO:.2%})")

    failures = []
    if p95 > P95_THRESHOLD_MS:
        failures.append(f"P95 {p95:.0f}ms 超过阈值 {P95_THRESHOLD_MS}ms")
    if fail_ratio > MAX_FAIL_RATIO:
        failures.append(f"失败率 {fail_ratio:.2%} 超过阈值 {MAX_FAIL_RATIO:.2%}")

    if failures:
        for f in failures:
            print(f"[性能阈值] 不达标: {f}")
        environment.process_exit_code = 1
    else:
        print("[性能阈值] 全部达标 ✅")

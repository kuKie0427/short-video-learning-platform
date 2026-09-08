"""
容器化整链路性能基线测试 (Locust) — Docker Compose 全栈 + Nginx 网关

被测对象（与 perf/locustfile.py 的本机直连微基准互补，二者结果不可直接对比）:
- 流量入口: Nginx 网关 :80（docker-compose 的 gateway 服务）
- 后端: 7 个微服务容器 + PostgreSQL 14 容器 + Redis 7 容器（缓存启用）+ Kafka
- 与本机基线的差异: 经网关转发 / Docker PG / Redis 缓存命中路径 / 容器网络

覆盖接口（同 locustfile.py，经网关寻址）:
- GET /api/feed/recommend  智能推荐流（Redis 缓存命中路径）
- GET /api/feed/hot        热门视频（时间衰减算法）
- GET /api/search/videos   视频搜索
- GET /api/auth/profile    用户资料（完整认证链路）

运行方式:
    # 1. 全套容器运行中（docker-compose up -d）
    # 2. 压测（30 秒, 20 并发, 打网关 80 端口）
    locust -f locustfile_gateway.py --headless -u 20 -r 5 -t 30s --host http://127.0.0.1

    # 3. Web 模式
    locust -f locustfile_gateway.py --host http://127.0.0.1
"""
import random

from locust import HttpUser, task, between, events

# 开发环境自动创建的用户 token（ENVIRONMENT=development 时 UUID 直通，
# common/utils/auth.py 首次请求自动建 dev 用户，与 locustfile.py 一致）
DEV_USER_TOKEN = "11111111-1111-1111-1111-111111111111"

# 性能回归阈值（网关整链路基线，独立于本机直连基线；按 2026-09-05 实测校准：
# 基线轮聚合 P95 19ms → 阈值 200ms ≈ 10x 余量；200 并发实测 P95 47ms 亦有 >4x 余量，
# 详见 BASELINE.md 网关章节）
GATEWAY_P95_THRESHOLD_MS = 200
GATEWAY_MAX_FAIL_RATIO = 0.01

SEARCH_QUERIES = ["微积分", "雅思", "数学", "Python", "导数"]


class GatewayApiUser(HttpUser):
    """网关整链路压测用户（全部走相对路径，由 --host 统一寻址）"""

    wait_time = between(0.5, 2)  # 模拟用户思考时间

    def on_start(self):
        self.headers = {"Authorization": f"Bearer {DEV_USER_TOKEN}"}

    @task(3)
    def feed_recommend(self):
        """智能推荐流（最高频接口，Redis 缓存命中路径）"""
        self.client.get("/api/feed/recommend", headers=self.headers)

    @task(2)
    def feed_hot(self):
        """热门视频流"""
        self.client.get("/api/feed/hot", headers=self.headers)

    @task(2)
    def search_videos(self):
        """视频搜索"""
        q = random.choice(SEARCH_QUERIES)
        self.client.get(
            "/api/search/videos",
            params={"q": q},
            headers=self.headers,
        )

    @task(1)
    def auth_profile(self):
        """用户资料（认证链路）"""
        self.client.get("/api/auth/profile", headers=self.headers)


@events.quitting.add_listener
def check_performance_thresholds(environment, **kwargs):
    """压测结束时校验性能阈值，超标则以非零退出码失败（可接入 CI 做性能回归门禁）"""
    stats = environment.stats.total
    if stats.num_requests == 0:
        print("\n[网关性能阈值] 未发出任何请求，跳过校验")
        return

    p95 = stats.get_response_time_percentile(0.95)
    fail_ratio = stats.fail_ratio

    print("\n========== 网关整链路性能阈值校验 ==========")
    print(f"请求总数: {stats.num_requests}  RPS: {stats.current_rps:.2f}")
    print(f"P95: {p95:.0f}ms (阈值 {GATEWAY_P95_THRESHOLD_MS}ms)  "
          f"失败率: {fail_ratio:.2%} (阈值 {GATEWAY_MAX_FAIL_RATIO:.2%})")

    failures = []
    if p95 > GATEWAY_P95_THRESHOLD_MS:
        failures.append(f"P95 {p95:.0f}ms 超过阈值 {GATEWAY_P95_THRESHOLD_MS}ms")
    if fail_ratio > GATEWAY_MAX_FAIL_RATIO:
        failures.append(f"失败率 {fail_ratio:.2%} 超过阈值 {GATEWAY_MAX_FAIL_RATIO:.2%}")

    if failures:
        for f in failures:
            print(f"[网关性能阈值] 不达标: {f}")
        environment.process_exit_code = 1
    else:
        print("[网关性能阈值] 全部达标 ✅")

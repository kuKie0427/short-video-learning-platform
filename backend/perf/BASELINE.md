# 性能基线（Locust）

> 核心读接口的性能回归基线。**每次性能相关改动后重跑本基线**，数据追加到下方历史表，
> P95/失败率超标时 `locustfile.py` 的阈值校验会以非零退出码失败（可接入 CI 做性能门禁）。

## 测试环境

| 项 | 值 |
|---|---|
| 测试日期 | 2026-08-13 |
| 机器 | macOS (Apple Silicon arm64)，本机开发环境 |
| Locust | 2.31.5（`backend/perf/requirements.txt`） |
| 被测服务 | auth:8001 / content:8002 / search:8006（本机直连，不经网关） |
| 数据库 | PostgreSQL 15（本机，mock 数据 8 条视频） |
| Redis | 未启用（推荐流走缓存降级路径） |
| 压测参数 | 20 并发，ramp 5/s，持续 30s |

## 基线结果（2026-08-13，20 并发）

| 接口 | 请求数 | 失败 | Avg | Min | Max | Med | P95 | req/s |
|------|-------:|-----:|----:|----:|----:|----:|----:|------:|
| GET /api/feed/recommend（推荐流） | 162 | 0 | 38ms | 14ms | 98ms | 36ms | 74ms | 5.44 |
| GET /api/feed/hot（热门流） | 101 | 0 | 18ms | 5ms | 81ms | 16ms | 36ms | 3.39 |
| GET /api/search/videos（搜索） | 124 | 0 | 13ms | 4ms | 29ms | 15ms | 22ms | 4.16 |
| GET /api/auth/profile（认证链路） | 60 | 0 | 6ms | 2ms | 14ms | 6ms | 11ms | 2.02 |
| **聚合** | **447** | **0** | **22ms** | 2ms | 98ms | 17ms | **53ms** | **15.50** |

- 失败率 0.00%，全部接口达标
- 原始数据：`results/locust_baseline_stats.csv` / `locust_baseline_history.csv`（每 1s 采样）

## 阈值门禁（locustfile.py 内建）

| 指标 | 阈值 | 基线实测 | 余量 |
|------|------|---------|------|
| 聚合 P95 | 500ms | 53ms | ~10x |
| 失败率 | 1% | 0.00% | 满余量 |

超标时 `environment.process_exit_code = 1`，压测进程以失败退出 → 可接入 CI。

## 复现命令

```bash
# 1. 启动被测服务（3 个终端）
cd backend
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.auth.app.main:app --port 8001
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.content.app.main:app --port 8002
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.search.app.main:app --port 8006

# 2. 跑压测（30s, 20 并发）
cd backend/perf
../.venv/bin/locust -f locustfile.py --headless -u 20 -r 5 -t 30s --host http://127.0.0.1:8001
```

> 鉴权说明：开发环境 `verify_token` 接受 UUID 作为 token（`common/utils/auth.py`），
> 压测无需短信/Redis，聚焦读接口本身性能；生产环境应替换为真实登录链路。

## 历史基线

| 日期 | 并发 | 聚合 P95 | 聚合 RPS | 失败率 | 备注 |
|------|------|---------|---------|--------|------|
| 2026-08-13 | 20 | 53ms | 15.50 | 0% | 首次入库（2026-08-13 实测） |

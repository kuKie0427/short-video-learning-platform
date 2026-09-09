# 性能基准测试（Locust）

对平台**核心读接口**建立性能基线，用于容量评估与回归对比。

## 覆盖接口

| 接口 | 说明 | 服务 |
| ------ | ------ | ------ |
| `GET /api/feed/recommend` | 智能推荐流（4 算法混合，Redis 缓存） | content :8002 |
| `GET /api/feed/hot` | 热门视频（时间衰减） | content :8002 |
| `GET /api/search/videos` | 视频搜索（ilike，tags ARRAY 列 GIN 索引） | search :8006 |
| `GET /api/auth/profile` | 用户资料（完整认证链路） | auth :8001 |

## 环境准备

```bash
# 1. 启动 PostgreSQL（本机）
/opt/homebrew/opt/postgresql@15/bin/pg_ctl -D /opt/homebrew/var/postgresql@15 -l /tmp/pg15.log start

# 2. 创建开发库并造数据（幂等，可重复执行）
cd backend
psql -h 127.0.0.1 -U app_user -d postgres -c "CREATE DATABASE short_video_platform OWNER app_user;"  # 首次
DB_HOST=127.0.0.1 .venv/bin/python scripts/insert_mock_videos.py

# 3. 启动被测服务（各自终端）
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.auth.app.main:app --port 8001
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.content.app.main:app --port 8002
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.search.app.main:app --port 8006

# 4. 安装 Locust
pip install -r perf/requirements.txt
```

## 运行

```bash
# 冒烟基线（30 秒，20 并发）—— 推荐
locust -f perf/locustfile.py --headless -u 20 -r 5 -t 30s --host http://127.0.0.1:8001

# 负载测试（3 分钟，50 并发）
locust -f perf/locustfile.py --headless -u 50 -r 10 -t 3m --host http://127.0.0.1:8001

# Web 模式（交互操作，图表展示）
locust -f perf/locustfile.py --host http://127.0.0.1:8001
# 浏览器打开 http://localhost:8089
```

### 网关整链路（Docker 全栈运行时）

```bash
# 前提：docker-compose up -d 全栈运行（7 服务 + 网关 + PG/Redis），打网关 80 端口
locust -f perf/locustfile_gateway.py --headless -u 20 -r 5 -t 30s --host http://127.0.0.1
```

结果与本机直连基线**不可直接对比**，历史数据见 [BASELINE.md](./BASELINE.md) 网关专节。

## 2026-08-05 实测基线（本机 M 系列芯片, 单进程 uvicorn）

**命令**: `locust -f perf/locustfile.py --headless -u 20 -r 5 -t 30s --host http://127.0.0.1:8001`

```
Type     Name                                # reqs  # fails |  Avg  Med   P95  P99 |  req/s
--------|-----------------------------------|-------|-------|-----|-----|-----|-----|--------
GET      /api/auth/profile                        63  0(0%) |    4    4     9   11 |   2.11
GET      /api/feed/hot                           130  0(0%) |   13   11    32   50 |   4.36
GET      /api/feed/recommend                     161  0(0%) |   24   23    39   46 |   5.40
GET      /api/search/videos (5 个关键词合计)     108  0(0%) |   11   10    28   37 |   3.62
--------|-----------------------------------|-------|-------|-----|-----|-----|-----|--------
Aggregated                                       462  0(0%) |   15   14    36   49 |  15.50
```

**结论**: 20 并发下全链路 P95 ≈ 36ms（远低于 500ms 目标）、0 失败；
`feed/recommend`（混合推荐 + Redis 缓存降级）为最重接口（avg 24ms）。
后续版本改动后可重跑本命令，与本表对比做回归判断（数值变化 >30% 需关注）。

## 结果解读

- **RPS（每秒请求数）**：吞吐能力
- **P95 / P99 响应时间**：长尾体验（目标 < 500ms）
- **失败率**：必须为 0；出现失败优先查数据库连接池、Redis 降级日志
- 注意：本机开发环境为单进程 uvicorn + SQLite/本地 PG，数值只用于**相对回归**；
  生产形态（Docker Compose 全栈 + 网关）基线已于 2026-09-05 采集，见上方网关小节与
  [BASELINE.md](./BASELINE.md) 网关专节，两层数据不可直接对比。

## 说明

- 开发环境 `verify_token` 接受 UUID 直接作为 token（`common/utils/auth.py`），
  性能脚本用固定 UUID 走完整认证依赖链，无需短信验证码与 Redis；
- 生产环境若要压登录链路，替换为 `POST /api/auth/send-code` + `/api/auth/login` 流程。

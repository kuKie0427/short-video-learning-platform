# 短视频学习平台 - 后端服务

短视频学习平台后端，基于 FastAPI + PostgreSQL + Redis + Kafka 构建的微服务架构。

## 定位

本 README 只说明项目定位、结构速览与就近入口。启动、测试、部署等明细见对应文档，避免多份文档重复维护。

## 架构速览

7 个微服务 + Nginx 网关，端口与职责如下（端口以 `docker-compose.yml` 为准）：

| 服务 | 端口 | 说明 |
|------|------|------|
| Auth | 8001 | 认证授权（手机号验证码登录、JWT） |
| Content | 8002 | 信息流、推荐、互动、关注、学习进度 |
| Upload | 8003 | 视频上传（分片、合并） |
| Split | 8004 | 视频拆分（含 Celery worker） |
| Course | 8005 | 课程管理 |
| Search | 8006 | 搜索 |
| Notification | 8007 | 消息通知 |
| API Gateway | 80 | Nginx 统一入口 |

服务间通过 Kafka 消息队列通信，共享代码在 `common/`。

## 结构速览

```
backend/
├── common/       # 共享库（模型、配置、数据库、消息、工具）
├── services/     # 7 个微服务
├── gateway/      # Nginx 网关配置
├── alembic/      # 数据库迁移
├── tests/        # 测试套件（api/ + unit/）
├── perf/         # 性能测试（Locust）
├── scripts/      # 工具脚本
├── docs/         # 文档
└── docker-compose.yml
```

完整目录树与逐节点说明见 [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)。

## 就近入口

| 需求 | 入口 |
|------|------|
| 快速启动 | [QUICK_START.md](./QUICK_START.md) |
| 完整启动与环境变量 | [docs/启动指南.md](./docs/启动指南.md) |
| 数据库本地部署 | [docs/数据库本地部署.md](./docs/数据库本地部署.md) |
| 运行测试 | [docs/运行测试.md](./docs/运行测试.md) |
| 故障排查 | [docs/故障排查指南.md](./docs/故障排查指南.md) |
| 文档总索引 | [DOCUMENTATION.md](./DOCUMENTATION.md) |

## 技术栈

- **框架**: FastAPI
- **数据库**: PostgreSQL 14+
- **缓存**: Redis 7+
- **消息队列**: Kafka
- **ORM**: SQLAlchemy + Alembic
- **认证**: JWT
- **API 网关**: Nginx
- **异步任务**: Celery

## 测试

- **用例数**: 315（`pytest --collect-only` 实测，含参数化展开）
- **覆盖率门禁**: `pytest.ini` 配置 `--cov-fail-under=70`，另有核心模块分级门禁 `scripts/check_coverage_gates.py`
- **运行方式**: 见 [docs/运行测试.md](./docs/运行测试.md)

## 环境变量

环境变量清单见 [env.example](./env.example) 与 [docs/启动指南.md](./docs/启动指南.md)，此处不再重复。

# 快速启动

Docker Compose 一键启动全部服务（7 个微服务 + API 网关 + PostgreSQL/Redis/Kafka）。

完整开发环境说明见[启动指南](docs/启动指南.md)，数据库专项见[数据库本地部署](docs/数据库本地部署.md)。

## 前置条件

- Docker 与 Docker Compose

## 一键启动

```bash
# 1. 进入 backend 目录
cd backend

# 2. 容器名冲突时清理，正常可跳过
./scripts/cleanup_docker.sh

# 3. 启动所有服务（首次构建镜像耗时较长）
docker-compose up -d

# 4. 查看状态，全部服务应为 Up
docker-compose ps
```

## 验证启动

```bash
# 一键诊断：容器状态、基础设施、各服务健康检查
./scripts/diagnose.sh

# 健康检查
curl http://localhost:8001/health    # Auth
curl http://localhost:8002/health    # Content
curl http://localhost/health         # 网关，返回 healthy

# 访问 API 文档
open http://localhost:8001/docs     # Auth 服务
open http://localhost:8002/docs     # Content 服务
```

健康检查返回形如 `{"status":"healthy","service":"auth","timestamp":"...","version":"1.0.0"}`。

## 失败时

```bash
./scripts/diagnose.sh                 # 定位问题
docker-compose logs --tail=50         # 最近日志
docker-compose logs -f auth-service   # 跟踪单个服务
```

详细排查步骤见[故障排查指南](docs/故障排查指南.md)。

## 相关文档

- [完整启动指南](docs/启动指南.md)：Docker 与本地开发两种方式、环境变量、数据存储
- [数据库本地部署](docs/数据库本地部署.md)：连接信息、表结构、备份恢复
- [故障排查指南](docs/故障排查指南.md)：常见问题与处理
- [项目结构说明](PROJECT_STRUCTURE.md)

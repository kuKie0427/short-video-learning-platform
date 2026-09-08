# 脚本目录

`scripts/` 下的工具脚本，按用途分类。每个脚本的用法以脚本本身为准。

## 测试相关

### manual_smoke_upload.py
发布冒烟 U01/U02 的一手执行脚本（测试负责人留痕用）。对真实网关跑完整分片上传链路（init → 逐片 PUT → complete），并按"状态码 + 响应体业务字段 + 数据库最终态"三位一体断言，专门防 BUG-004 那类"200 但未落库"的静默失败。退出码 0 即可直接把输出抄进手工用例的"实际结果"列。

```bash
# 前置：docker-compose up -d 全栈已运行
cd backend && .venv/bin/python scripts/manual_smoke_upload.py
# 可用环境变量覆盖：SMOKE_GATEWAY / SMOKE_DEV_USER / SMOKE_PG_CONTAINER / SMOKE_PG_DB / SMOKE_PG_USER
```

### check_tests.py
测试代码结构验证脚本。检查测试目录、关键测试文件是否存在且语法正确，并核对 `pytest.ini` 与 `requirements.txt` 中的测试依赖。

```bash
python scripts/check_tests.py
```

### check_coverage_gates.py
覆盖率分级门禁。对关键业务模块（智能拆分管线等）设置独立覆盖率底线，防止被总量掩盖。需在跑完 pytest（生成 `.coverage` 数据）后执行，返回码非 0 即门禁失败（供 CI 使用）。

```bash
python scripts/check_coverage_gates.py
```

### create_test_db.py
创建测试数据库。测试库名为 `${DB_NAME}_test`，自动检测 Docker 容器名与 localhost 环境。

```bash
python scripts/create_test_db.py
```

### test_connection.py
数据库连接诊断。依次测试 PostgreSQL 连接、测试数据库连接与 SQLAlchemy 连接，测试库不存在时尝试自动创建。

```bash
python scripts/test_connection.py
```

### insert_mock_videos.py
向数据库插入 Mock 用户与视频数据（幂等，已存在则跳过）。

```bash
python scripts/insert_mock_videos.py
```

## Docker 相关

### cleanup_docker.sh
清理旧的 Docker 容器，解决容器名称冲突。停止并删除全部相关容器后执行 `docker-compose down`。

```bash
./scripts/cleanup_docker.sh
```

### diagnose.sh
服务诊断脚本。依次检查 Docker 与 Docker Compose 版本、容器状态、基础设施（PostgreSQL、Redis）、各服务健康检查（8001-8007）、最近错误日志与端口占用。

```bash
./scripts/diagnose.sh
```

## 使用说明

- Python 脚本需在 `backend/` 目录下运行，依赖见根目录 `requirements.txt`
- Shell 脚本需有执行权限（`chmod +x`），在 `backend/` 目录下运行
- 数据库相关脚本依赖环境变量配置，见 `env.example` 与 [docs/启动指南.md](../docs/启动指南.md)
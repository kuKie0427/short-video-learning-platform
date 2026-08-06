# 脚本目录

## 测试脚本
- `check_tests.py` - 测试代码验证脚本

## Docker脚本
- `cleanup_docker.sh` - Docker容器清理脚本
- `diagnose.sh` - 服务诊断脚本（检查服务状态和常见问题）

## 使用说明

### 测试验证脚本
```bash
# 运行测试验证脚本
python scripts/check_tests.py
```

### Docker清理脚本
```bash
# 清理旧的Docker容器（解决容器名称冲突）
./scripts/cleanup_docker.sh

# 然后重新启动服务
docker-compose up -d
```

### 服务诊断脚本
```bash
# 诊断服务状态和常见问题
./scripts/diagnose.sh

# 脚本会检查：
# - Docker和Docker Compose版本
# - 容器状态
# - 基础设施服务（PostgreSQL、Redis）
# - 应用服务健康状态
# - 最近错误日志
# - 端口占用情况
```


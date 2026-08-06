# 快速启动指南

## 🚀 一键启动（Docker Compose）

```bash
# 1. 进入backend目录
cd backend

# 2. 清理旧容器（如果有）
./scripts/cleanup_docker.sh

# 3. 启动所有服务
docker-compose up -d

# 4. 等待服务启动（约30秒）
sleep 30

# 5. 运行诊断检查
./scripts/diagnose.sh

# 6. 验证服务
curl http://localhost:8001/health
curl http://localhost:8002/health

# 7. 访问API文档
open http://localhost:8001/docs
```

## ✅ 验证成功标志

启动成功后，应该看到：

1. ✅ 所有服务状态为 "Up"
   ```bash
   docker-compose ps
   ```

2. ✅ 健康检查返回正常
   ```bash
   curl http://localhost:8001/health
   # 返回: {"status":"healthy","service":"auth",...}
   ```

3. ✅ API文档可访问
   - http://localhost:8001/docs (Auth服务)
   - http://localhost:8002/docs (Content服务)

## ❌ 如果验证失败

### 快速诊断
```bash
./scripts/diagnose.sh
```

### 查看日志
```bash
# 查看所有服务日志
docker-compose logs --tail=50

# 查看特定服务日志
docker-compose logs -f auth-service
```

### 常见问题

1. **容器未启动**：查看日志找出原因
2. **数据库连接失败**：确保PostgreSQL容器运行
3. **端口被占用**：检查端口占用情况
4. **代码错误**：查看服务日志中的错误信息

**详细排查**：查看 [docs/故障排查指南.md](./docs/故障排查指南.md)

## 📚 更多信息

- [完整启动指南](./docs/启动指南.md)
- [故障排查指南](./docs/故障排查指南.md)
- [项目结构说明](./PROJECT_STRUCTURE.md)


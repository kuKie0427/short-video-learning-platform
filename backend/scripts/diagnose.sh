#!/bin/bash
# 服务诊断脚本
# 用于快速诊断服务启动问题

echo "=========================================="
echo "服务诊断脚本"
echo "=========================================="
echo ""

cd "$(dirname "$0")/.."

echo "1. 检查Docker和Docker Compose版本"
echo "----------------------------------------"
docker --version 2>/dev/null || echo "❌ Docker未安装或无法访问"
docker-compose --version 2>/dev/null || echo "❌ Docker Compose未安装或无法访问"
echo ""

echo "2. 检查容器状态"
echo "----------------------------------------"
docker-compose ps 2>/dev/null || echo "❌ 无法获取容器状态（可能需要权限）"
echo ""

echo "3. 检查基础设施服务"
echo "----------------------------------------"
echo "PostgreSQL:"
docker-compose exec -T postgres pg_isready -U app_user 2>/dev/null && echo "✅ PostgreSQL运行正常" || echo "❌ PostgreSQL未就绪或未运行"
echo ""

echo "Redis:"
docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && echo "✅ Redis运行正常" || echo "❌ Redis未就绪或未运行"
echo ""

echo "4. 检查应用服务健康状态"
echo "----------------------------------------"
services=("auth-service:8001" "content-service:8002" "upload-service:8003" "split-service:8004" "course-service:8005" "search-service:8006" "notification-service:8007")

for service_info in "${services[@]}"; do
    IFS=':' read -r service port <<< "$service_info"
    echo -n "$service (端口$port): "
    if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
        echo "✅ 健康检查通过"
    else
        echo "❌ 健康检查失败或服务未运行"
    fi
done
echo ""

echo "5. 检查最近错误日志"
echo "----------------------------------------"
echo "最近20条错误日志："
docker-compose logs --tail=100 2>/dev/null | grep -i error | tail -5 || echo "无错误日志或无法访问"
echo ""

echo "6. 检查端口占用"
echo "----------------------------------------"
ports=(8001 8002 8003 8004 8005 8006 8007)
for port in "${ports[@]}"; do
    if lsof -i :$port > /dev/null 2>&1; then
        echo "✅ 端口 $port 已被占用（正常）"
    else
        echo "⚠️  端口 $port 未被占用（服务可能未启动）"
    fi
done
echo ""

echo "=========================================="
echo "诊断完成"
echo "=========================================="
echo ""
echo "如果发现问题，请查看详细日志："
echo "  docker-compose logs -f [service_name]"
echo ""
echo "更多帮助请参考：docs/故障排查指南.md"



#!/bin/bash
# Docker容器清理脚本
# 用于清理旧的Docker容器，解决容器名称冲突问题

echo "正在清理旧的Docker容器..."

# 停止并删除所有相关容器
docker rm -f short_video_redis short_video_postgres short_video_zookeeper short_video_kafka 2>/dev/null || true
docker rm -f auth_service content_service upload_service split_service course_service search_service notification_service api_gateway 2>/dev/null || true

# 停止docker-compose服务
cd "$(dirname "$0")/.."
docker-compose down 2>/dev/null || true

echo "清理完成！"
echo ""
echo "现在可以重新运行: docker-compose up -d"


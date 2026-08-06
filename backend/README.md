# 短视频学习平台 - 后端服务

完整的短视频学习平台后端，基于 FastAPI + PostgreSQL + Redis + Kafka 构建的微服务架构。

## 🏗️ 架构说明

本项目采用**微服务架构**，包含以下服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| Auth | 8001 | 认证授权服务 |
| Content | 8002 | 内容管理、推荐、互动服务 |
| Upload | 8003 | 视频上传服务 |
| Split | 8004 | 视频拆分服务 |
| Course | 8005 | 课程管理服务 |
| Search | 8006 | 搜索服务 |
| Notification | 8007 | 消息通知服务 |
| API Gateway | 80 | 统一API入口 |

## 🚀 快速启动

### 前置条件

- Docker 和 Docker Compose（推荐）
- 或 Python 3.11+、PostgreSQL、Redis（本地开发）

### 方式一：Docker Compose（推荐）

```bash
# 1. 进入backend目录
cd backend

# 2. 清理旧容器（如果有冲突）
./scripts/cleanup_docker.sh

# 3. 启动所有服务
docker-compose up -d

# 4. 查看服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f

# 6. 验证服务
curl http://localhost:8001/health  # Auth服务
curl http://localhost:8002/health  # Content服务

# 7. 访问API文档
open http://localhost:8001/docs
```

**详细启动步骤请参考**：[启动指南](./docs/启动指南.md)

### 方式二：本地开发模式

```bash
# 1. 安装依赖（各服务有独立的requirements.txt）
cd services/auth
pip install -r requirements.txt

# 2. 配置环境变量（创建.env文件或设置环境变量）
# 参考README.md中的环境变量配置部分

# 3. 启动基础设施（PostgreSQL、Redis、Kafka）
# 使用Docker Compose启动基础设施
cd ../..
docker-compose up -d postgres redis kafka

# 4. 启动单个服务
cd services/auth
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**详细启动步骤请参考**：[启动指南](./docs/启动指南.md)

## 📁 项目结构

```
backend/
├── common/           # 共享库（所有微服务共享）
├── services/         # 微服务目录
├── gateway/         # API网关配置
├── docs/            # 文档目录
├── scripts/         # 脚本目录
└── docker-compose.yml
```

详细结构说明请参考 [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)

## 🎯 核心功能模块

### 1. 🔐 用户认证系统（Auth服务）
- 手机号验证码登录/注册
- JWT Token 认证
- 用户资料管理
- 角色权限控制

### 2. 📹 视频上传与管理（Upload服务）
- 分片上传（支持大文件）
- 视频元数据管理
- 长视频/短视频分类

### 3. 🧩 智能视频切分（Split服务）
- 场景检测
- 拆分点计算
- 视频切割
- 任务管理

### 4. 📱 内容推荐（Content服务）
- 智能推荐算法（内容推荐、协同过滤、混合推荐）
- 个性化Feed
- 热门视频
- 关注用户流

### 5. ❤️ 用户互动（Content服务）
- 点赞、收藏、评论
- 关注/取消关注
- 评论树结构

### 6. 📚 课程管理（Course服务）
- 课程CRUD
- 视频关联管理
- 学习进度跟踪

### 7. 🔍 搜索功能（Search服务）
- 视频搜索
- 搜索建议

### 8. 📬 消息通知（Notification服务）
- 消息列表
- 标记已读

## 📍 服务信息

- **API网关**: http://localhost
- **Auth服务**: http://localhost:8001
- **Content服务**: http://localhost:8002
- **API文档**: http://localhost:8001/docs（各服务独立文档）

## 🔧 技术栈

- **框架**: FastAPI
- **数据库**: PostgreSQL 14+
- **缓存**: Redis 7+
- **消息队列**: Kafka
- **ORM**: SQLAlchemy
- **认证**: JWT
- **API网关**: Nginx

## 📚 文档

### 核心文档
- [快速启动指南](./QUICK_START.md) - 快速开始使用
- [项目结构说明](./PROJECT_STRUCTURE.md) - 完整项目结构
- [启动指南](./docs/启动指南.md) - 详细启动步骤
- [运行测试](./docs/运行测试.md) - 测试文档

### 设计文档
- [系统架构设计](./docs/系统架构设计文档.md) - 微服务架构设计
- [数据库设计](./docs/数据库设计文档.md) - 数据库表结构设计
- [API设计文档](./docs/API设计文档.md) - 完整API接口文档

### 运维文档
- [数据库本地部署](./docs/数据库本地部署.md) - PostgreSQL部署指南
- [故障排查指南](./docs/故障排查指南.md) - 常见问题解决

## 🧪 测试

### 测试统计
- ✅ **通过测试**: 146/147 (99.3%)
- 📊 **代码覆盖率**: 71%
- 🧪 **测试类型**: 单元测试 + API集成测试

### 运行测试

```bash
# 创建测试数据库
python scripts/create_test_db.py

# 运行所有测试
pytest tests/ -v

# 运行API测试
pytest tests/api/ -v

# 运行单元测试
pytest tests/unit/ -v

# 生成覆盖率报告
pytest --cov=. --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html
```

详细测试文档请参考：[运行测试](./docs/运行测试.md)

## 🔐 环境变量

创建`.env`文件或设置环境变量：

```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/short_video_platform
DB_HOST=postgres
DB_PORT=5432
DB_NAME=short_video_platform
DB_USER=app_user
DB_PASSWORD=app_password_2025

# Redis配置
REDIS_HOST=redis
REDIS_PORT=6379

# Kafka配置
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# JWT配置
JWT_SECRET_KEY=your-secret-key-change-in-production

# 环境
ENVIRONMENT=development
```

## 📝 开发指南

### 添加新服务

1. 在`services/`目录下创建新服务目录
2. 创建`app/main.py`作为服务入口
3. 创建`app/api/`目录存放API路由
4. 创建`Dockerfile`和`requirements.txt`
5. 在`docker-compose.yml`中添加服务配置
6. 在`gateway/nginx.conf`中添加路由配置

### 使用共享库

```python
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.append(project_root)

from common.models import User, Video
from common.database.connection import get_db
from common.utils.auth import get_current_user
from common.utils.response import success_response
```

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。


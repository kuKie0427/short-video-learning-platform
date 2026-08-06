# 项目结构说明

## 目录结构

```
backend/
├── common/                    # 共享库（所有微服务共享）
│   ├── models/               # 数据模型
│   │   ├── base.py          # 基础模型类
│   │   ├── user.py          # 用户模型
│   │   ├── video.py         # 视频模型
│   │   ├── interaction.py   # 互动模型（评论、点赞、收藏、关注）
│   │   ├── course.py        # 课程模型
│   │   ├── split.py         # 拆分任务模型
│   │   ├── upload.py        # 上传任务模型
│   │   └── notification.py  # 通知模型
│   ├── config/               # 配置管理
│   │   └── settings.py      # 统一配置
│   ├── database/             # 数据库连接
│   │   └── connection.py    # PostgreSQL和Redis连接
│   ├── utils/                # 工具函数
│   │   ├── auth.py          # 认证工具
│   │   ├── response.py      # 响应格式工具
│   │   └── redis_client.py  # Redis客户端工具
│   └── messaging/            # 消息队列客户端
│       ├── kafka_client.py  # Kafka客户端
│       └── topics.py         # Topic定义
│
├── services/                 # 微服务目录
│   ├── auth/                 # Auth服务（端口8001）
│   │   ├── app/
│   │   │   ├── main.py      # 服务入口
│   │   │   └── api/
│   │   │       └── auth.py  # 认证API
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── content/              # Content服务（端口8002）
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/         # Feed、互动、关注API
│   │   │   └── services/    # 推荐算法服务
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── upload/               # Upload服务（端口8003）
│   ├── split/                # Split服务（端口8004）
│   ├── course/               # Course服务（端口8005）
│   ├── search/               # Search服务（端口8006）
│   └── notification/         # Notification服务（端口8007）
│
├── gateway/                  # API网关配置
│   └── nginx.conf           # Nginx配置
│
├── docs/                     # 文档目录
│   ├── README.md            # 文档索引
│   ├── 微服务架构重构总结.md
│   ├── PostgreSQL配置说明.md
│   ├── SQLite移除总结.md
│   ├── 测试状态报告.md
│   └── 运行测试.md
│
├── scripts/                  # 脚本目录
│   ├── README.md
│   └── check_tests.py       # 测试验证脚本
│
├── tests/                    # 测试目录（旧版单体应用测试）
│   ├── api/                 # API测试
│   ├── unit/                # 单元测试
│   └── fixtures/            # 测试数据
│
├── alembic/                  # 数据库迁移工具
│   ├── versions/            # 迁移文件
│   └── env.py
│
├── docker-compose.yml        # Docker编排文件
├── .gitignore               # Git忽略文件
├── pytest.ini               # Pytest配置
├── requirements.txt         # 依赖文件（旧版）
└── README.md                # 项目说明
```

## 文件组织原则

### 1. 共享库（common）
- **目的**：避免代码重复，统一管理共享代码
- **内容**：数据模型、配置、数据库连接、工具函数、消息队列客户端
- **使用**：所有微服务通过`sys.path.append`引入

### 2. 微服务（services）
- **结构**：每个服务独立目录，包含`app/`、`Dockerfile`、`requirements.txt`
- **端口**：每个服务使用独立端口（8001-8007）
- **依赖**：通过common库共享代码，通过消息队列通信

### 3. 文档（docs）
- **位置**：所有Markdown文档统一放在`docs/`目录
- **分类**：架构文档、数据库文档、测试文档、API文档、部署文档

### 4. 脚本（scripts）
- **位置**：所有脚本统一放在`scripts/`目录
- **用途**：测试验证、部署脚本、工具脚本


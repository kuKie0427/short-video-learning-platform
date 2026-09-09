# 项目结构说明

本文档以 `backend/` 目录的实际文件为准，逐节点描述目录与文件职责，目录树与注释均与代码现状一致。

## 目录结构

```
backend/
├── common/                    # 共享库（所有微服务共用）
│   ├── config/
│   │   └── settings.py        # 统一配置（数据库、Redis、Kafka、JWT 等）
│   ├── database/
│   │   └── connection.py      # PostgreSQL 连接与会话管理
│   ├── messaging/
│   │   ├── kafka_client.py    # Kafka 生产者/消费者封装
│   │   └── topics.py          # Kafka Topic 定义
│   ├── models/                # SQLAlchemy 数据模型
│   │   ├── base.py            # 模型基类
│   │   ├── user.py            # 用户模型
│   │   ├── video.py           # 视频模型
│   │   ├── interaction.py     # 互动模型（评论、点赞、收藏、关注）
│   │   ├── course.py          # 课程模型
│   │   ├── split.py           # 拆分任务模型
│   │   ├── upload.py          # 上传任务模型
│   │   └── notification.py    # 通知模型
│   └── utils/
│       ├── auth.py            # 认证与鉴权工具
│       ├── redis_client.py    # Redis 客户端封装
│       ├── response.py        # 统一响应格式
│       └── stats.py           # 统计工具
│
├── services/                  # 微服务目录（7 个服务）
│   ├── auth/                  # Auth 服务（端口 8001）
│   │   ├── app/
│   │   │   ├── main.py        # 服务入口
│   │   │   ├── api/
│   │   │   │   └── auth.py    # 认证 API（登录、注册、验证码）
│   │   │   └── services/
│   │   │       └── sms_service.py   # 短信验证码服务
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── content/               # Content 服务（端口 8002）
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   │   ├── feed.py        # 信息流 API
│   │   │   │   ├── follow.py      # 关注 API
│   │   │   │   ├── interaction.py # 互动 API（点赞、收藏、评论）
│   │   │   │   └── learn.py       # 学习进度 API
│   │   │   └── services/
│   │   │       └── recommendation.py  # 推荐算法
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── upload/                # Upload 服务（端口 8003）
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   │   └── upload.py  # 上传 API（分片、合并）
│   │   │   └── services/
│   │   │       └── storage.py # 文件存储
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── split/                 # Split 服务（端口 8004）
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── celery_app.py  # Celery 异步任务
│   │   │   ├── api/
│   │   │   │   └── split.py   # 拆分 API
│   │   │   └── services/
│   │   │       ├── smart_split_service.py   # 智能拆分服务
│   │   │       ├── video_split_service.py   # 视频拆分服务
│   │   │       ├── video_splitter.py        # 视频切割器
│   │   │       └── smart_split/             # 智能拆分管线
│   │   │           ├── keyframe_extractor.py    # 关键帧提取
│   │   │           ├── knowledge_analyzer.py    # 知识点分析
│   │   │           ├── pipeline.py              # 管线编排
│   │   │           ├── speech_to_text.py        # 语音转文字
│   │   │           └── video_splitter.py        # 智能切割
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── course/                # Course 服务（端口 8005）
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   └── api/
│   │   │       └── course.py # 课程 API
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── search/                # Search 服务（端口 8006）
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   └── api/
│   │   │       └── search.py # 搜索 API
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── notification/          # Notification 服务（端口 8007）
│       ├── app/
│       │   ├── main.py
│       │   └── api/
│       │       └── inbox.py  # 消息收件箱 API
│       ├── Dockerfile
│       └── requirements.txt
│
├── gateway/                   # API 网关（Nginx，端口 80）
│   ├── nginx.conf             # 生产网关配置
│   ├── nginx-ci.conf          # CI 环境网关配置
│   └── nginx-local.conf       # 本地开发网关配置
│
├── alembic/                   # 数据库迁移
│   ├── env.py                 # Alembic 环境
│   ├── script.py.mako         # 迁移脚本模板
│   └── versions/              # 迁移版本
│       ├── 001_initial_migration.py
│       ├── 002_add_gin_indexes.py
│       ├── 003_add_triggers.py
│       ├── 004_add_follows_table.py
│       └── 005_add_user_profile_fields.py
│
├── tests/                     # 测试套件
│   ├── conftest.py            # pytest 共享 fixtures
│   ├── api/                   # API 集成测试（17 个测试文件）
│   │   ├── test_auth.py
│   │   ├── test_course.py
│   │   ├── test_feed.py
│   │   ├── test_follow.py
│   │   ├── test_idempotency.py
│   │   ├── test_inbox.py
│   │   ├── test_interaction.py
│   │   ├── test_learn.py
│   │   ├── test_search.py
│   │   ├── test_security.py
│   │   ├── test_split.py
│   │   ├── test_split_advanced.py
│   │   ├── test_split_core.py
│   │   ├── test_upload.py
│   │   ├── test_upload_image.py
│   │   ├── test_upload_merge.py
│   │   └── test_video.py
│   ├── unit/                  # 单元测试（15 个测试文件）
│   │   ├── test_glm_fallback.py
│   │   ├── test_knowledge_analyzer_logic.py
│   │   ├── test_models.py
│   │   ├── test_pipeline_flow.py
│   │   ├── test_recommendation.py
│   │   ├── test_redis_client.py
│   │   ├── test_smart_split_service.py
│   │   ├── test_sms_service.py
│   │   ├── test_speech_to_text.py
│   │   ├── test_stats.py
│   │   ├── test_storage.py
│   │   ├── test_utils_auth.py
│   │   ├── test_utils_response.py
│   │   ├── test_video_split_service.py
│   │   └── test_video_splitter.py
│   ├── fixtures/              # 测试数据
│   ├── utils/                 # 测试工具
│   └── README.md              # 测试说明
│
├── perf/                      # 性能测试
│   ├── BASELINE.md            # 性能基线（本机微基准 + 网关整链路两层）
│   ├── locustfile.py          # Locust 压测脚本（本机直连微基准）
│   ├── locustfile_gateway.py  # Locust 压测脚本（网关整链路，Docker 全栈）
│   ├── README.md              # 性能测试说明
│   ├── requirements.txt
│   └── results/               # 压测结果（locust_* 本机系列 / locust_gateway_20260905_* 网关系列）
│       └── locust_baseline_stats.csv
│
├── scripts/                   # 工具脚本（详见 scripts/README.md）
│   ├── check_coverage_gates.py    # 覆盖率分级门禁
│   ├── check_tests.py             # 测试结构验证
│   ├── cleanup_docker.sh          # Docker 容器清理
│   ├── create_test_db.py          # 创建测试数据库
│   ├── diagnose.sh                # 服务诊断
│   ├── insert_mock_videos.py      # 插入 Mock 数据
│   ├── test_connection.py         # 数据库连接诊断
│   └── README.md
│
├── docs/                      # 文档目录（详见 DOCUMENTATION.md）
│   ├── README.md              # 文档中心索引
│   ├── API设计文档.md
│   ├── 启动指南.md
│   ├── 故障排查指南.md
│   ├── 数据库本地部署.md
│   ├── 数据库设计文档.md
│   ├── 手动测试用例清单.md
│   ├── 测试设计文档.md
│   ├── 系统架构设计文档.md
│   ├── 项目展示讲解内容.md
│   └── 运行测试.md
│
├── data/                      # 运行时数据（上传文件）
│   └── uploads/videos/        # 上传的视频文件
│
├── smart_split_output/        # 智能拆分输出（按任务 ID 分目录）
├── output_splited_videos/     # 拆分输出视频
│
├── alembic.ini                # Alembic 配置
├── docker-compose.yml         # Docker 编排（7 服务 + 网关 + 基础设施 + split-worker）
├── env.example                # 环境变量示例
├── pytest.ini                 # Pytest 配置（含覆盖率门禁）
├── requirements.txt           # 根依赖
├── QUICK_START.md             # 快速启动
├── README.md                  # 项目说明
├── PROJECT_STRUCTURE.md       # 本文档
├── DOCUMENTATION.md           # 文档索引
└── test_video.html            # 测试用视频页面
```

## 文件组织原则

### 1. 共享库（common）
- **目的**：避免代码重复，统一管理共享代码
- **内容**：数据模型、配置、数据库连接、消息队列客户端、工具函数
- **使用**：各微服务通过 `sys.path` 引入 `common` 包

### 2. 微服务（services）
- **结构**：每个服务独立目录，含 `app/`、`Dockerfile`、`requirements.txt`
- **端口**：auth 8001、content 8002、upload 8003、split 8004、course 8005、search 8006、notification 8007
- **依赖**：通过 `common` 共享代码，通过 Kafka 消息队列通信
- **异步**：split 服务含 Celery worker（`split-worker`），处理拆分任务

### 3. 网关（gateway）
- **作用**：Nginx 统一入口（端口 80），按路径路由到各微服务
- **配置**：生产、CI、本地三套配置

### 4. 测试（tests）
- **分类**：`api/` 集成测试、`unit/` 单元测试、`fixtures/` 测试数据、`utils/` 测试工具
- **入口**：`conftest.py` 提供共享 fixtures，`pytest.ini` 配置收集与覆盖率门禁

### 5. 文档（docs）
- **位置**：Markdown 文档统一放在 `docs/` 目录
- **索引**：`DOCUMENTATION.md` 为文档总索引，`docs/README.md` 为文档中心

### 6. 脚本（scripts）
- **位置**：工具脚本统一放在 `scripts/` 目录
- **说明**：每个脚本的用途与用法见 `scripts/README.md`

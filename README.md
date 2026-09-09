# 短视频学习平台

基于 AI 的智能短视频学习平台。集成 SenseVoice 语音识别、GLM 多模态分析与智能推荐系统，采用微服务架构，覆盖视频上传、智能拆分、内容推荐、课程管理全流程。

[![Tests](https://img.shields.io/badge/tests-315%20passed-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-75.4%25-yellow)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688)]()
[![React](https://img.shields.io/badge/React-18.3%2B-61dafb)]()
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178c6)]()
[![Docker](https://img.shields.io/badge/Docker-24%2B-2496ed)]()

[快速开始](#快速开始) · [核心功能](#核心功能) · [架构概览](#架构概览) · [文档导航](#文档导航)

---

## 核心功能

**智能视频拆分（核心亮点）**

SenseVoiceSmall ASR 语音转文字（中日韩英多语种）+ OpenCV 关键帧提取 + GLM 多模态知识点边界识别，三路信号融合后自动切分长视频为独立知识点片段。无 GLM Key 时降级为等长切分。拆分任务经 Celery 异步执行，不阻塞 API 进程。

**视频上传与管理**

分片上传（5MB/片，断点续传）+ FFprobe 格式校验 + 长短视频自动分类。本地磁盘存储，nginx 静态直出，S3 为可选切换。

**内容推荐系统**

四种策略混合：内容相似度（TF-IDF + 余弦）、协同过滤（User-Item CF）、时间衰减热度排序、加权混合推荐。覆盖已发布视频片段，支持 Redis 缓存与冷启动降级。

**用户认证与互动**

手机验证码登录（Redis 存储）+ JWT 双令牌（Access + Refresh）。点赞、收藏、评论（树状结构）、关注，均提供幂等性保证。

**课程管理与搜索**

课程 CRUD、视频关联（多对多）、学习进度追踪。全文搜索 + 搜索建议 + 多维排序筛选。

**消息通知**

系统公告、互动通知，异步推送。

---

## 架构概览

### 服务组成

| 组件 | 端口 | 说明 |
| ------ | ------ | ------ |
| Nginx 网关 | :80 | 统一入口，路由转发，静态文件直出 |
| Auth 服务 | :8001 | 认证授权、用户管理 |
| Content 服务 | :8002 | Feed 推荐、视频信息、互动、学习记录 |
| Upload 服务 | :8003 | 分片上传、文件管理 |
| Split 服务 | :8004 | 视频拆分 API |
| Split Worker | - | Celery worker，消费拆分任务（Redis broker） |
| Course 服务 | :8005 | 课程管理 |
| Search 服务 | :8006 | 搜索与搜索建议 |
| Notification 服务 | :8007 | 消息通知 |
| PostgreSQL | :5432 | 主数据库（14 表） |
| Redis | :6379 | 缓存 / Celery broker / 短信码 / 计数 |
| Kafka | :9092 | 部署于 compose，业务未接入 |

### 架构图

```
                      ┌──────────────────┐
                      │   Nginx Gateway  │
                      │      :80         │
                      └────────┬─────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
    ┌───────▼───────┐  ┌──────▼──────┐  ┌───────▼────────┐
    │ /videos (静态) │  │   /api/*    │  │ /uploads (静态) │
    └───────────────┘  └──────┬──────┘  └────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
  ┌────────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
  │  Auth :8001   │  │Content :8002 │  │Upload :8003  │
  └───────────────┘  └──────────────┘  └──────────────┘
           │                  │                  │
  ┌────────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
  │  Split :8004  │  │Course :8005  │  │Search :8006  │
  └───────┬───────┘  └──────────────┘  └──────────────┘
          │
  ┌───────▼─────────────────────────────┐
  │ Split Worker (Celery, Redis broker) │
  │ SenseVoice + OpenCV + GLM 管线      │
  └─────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │ Notification :8007                  │
  └──────────────────────────────────────┘
            │                │
  ┌─────────▼────┐  ┌───────▼──────┐
  │ PostgreSQL   │  │    Redis     │
  │ :5432 (14表) │  │ :6379       │
  └──────────────┘  └──────────────┘
```

### 存储与基础设施

| 基础设施 | 选型 | 说明 |
| ---------- | ------ | ------ |
| 数据库 | PostgreSQL 14 | 14 张核心表，单库共享，Alembic 迁移 |
| 缓存 / 消息 | Redis 7 | Celery broker、会话、验证码、计数器 |
| 文件存储 | 本地 data/uploads | nginx 静态直出；S3 为可选切换 |
| 容器编排 | Docker Compose | 一键启动全部服务 |

> Kafka 部署于 compose 但业务层未接入，消息通知当前走 Redis 异步。

### 技术栈

| 层次 | 技术 |
| ------ | ------ |
| 后端框架 | FastAPI 0.104.1（`requirements.txt` 锁定版本），Python 3.11+ |
| ORM | SQLAlchemy 2.0+，Alembic |
| AI 模型 | SenseVoiceSmall（ASR）、GLM 多模态（知识点分析）、OpenCV（关键帧） |
| 前端 | React 18.3 + TypeScript 5（声明 `^5.2`，实装 5.9）+ Vite 5.4 |
| 样式 | Tailwind CSS 3.4+ |
| 测试 | pytest（后端）、Vitest + React Testing Library（前端）、Playwright（E2E） |

### 数据库

14 张核心表：users, videos, long_videos, learn_records, comments, likes, favorites, follows, upload_tasks, notifications, split_tasks, split_segments, courses, course_videos。完整字段、索引、关系详见[数据库设计文档](./backend/docs/数据库设计文档.md)。

---

## 快速开始

**一键启动（推荐）**

```bash
# 1. 克隆
git clone https://github.com/kuKie0427/short-video-learning-platform.git
cd short-video-learning-platform


# 2. 启动后端（含数据库、Redis、全部微服务）
cd backend
docker-compose up -d

# 3. 启动前端
cd ../frontend
npm install
npm run dev

# 4. 访问
# 前端:  http://localhost:3000
# API:   http://localhost/docs
# 网关:  http://localhost
```

**验证**

```bash
docker-compose ps                              # 检查容器状态
curl http://localhost/health                   # 网关自身探活，返回 healthy
curl http://localhost:8001/health              # 服务健康检查走各自端口（Auth 示例）
curl http://localhost/api/feed/hot?page=1      # 经网关验业务链路（只转发 /api/* 业务路由）
```

详细启动步骤与环境变量配置：[快速启动指南](./backend/QUICK_START.md) · [后端启动指南](./backend/docs/启动指南.md)

---

## 测试体系

| 类别 | 用例数 | 工具 | 说明 |
| ------ | -------- | ------ | ------ |
| 后端接口集成测试 | 164（17 文件） | pytest | 真实 PostgreSQL；含幂等、安全专项 |
| 后端单元测试 | 151（15 文件） | pytest | 推荐算法、AI 降级、工具函数 |
| └ 其中参数化展开 | 42（13 个 parametrize 块） | pytest `@parametrize` | 认证边界 / 输入校验 / 工厂分支矩阵 |
| 前端单测 | 10 | Vitest + RTL | 登录、上下文、路由守卫 |
| E2E 冒烟 | 6（5 spec 文件） | Playwright | 真实后端链路，进 CI |
| 手工用例 | 56 条编号（附 29 项快查清单） | 测试清单 | 正式版 P0–P2；清单版冒烟13+探索8+视觉8 |

全量回归 315 例：纯用例 ~18s、含覆盖率报告 ~22s（2026-09-09 本机复测；轻负载历史实测 ~13s）。覆盖率 75.4%（总量门禁 70% + 5 模块分级门禁 10/15/45/60/60，当前实测 12/15/45/64/61）。

运行方式与用例设计方法论：[运行测试](./backend/docs/运行测试.md) · [测试设计文档](./backend/docs/测试设计文档.md) · [手动测试用例清单](./backend/docs/手动测试用例清单.md) · [E2E 测试](./e2e/README.md)

---

## 文档导航

### 快速开始

| 文档 | 说明 |
| ------ | ------ |
| [快速启动指南](./backend/QUICK_START.md) | Docker Compose 一键启动 |
| [后端启动指南](./backend/docs/启动指南.md) | 本地开发环境配置 |
| [项目结构](./backend/PROJECT_STRUCTURE.md) | 目录结构与文件说明 |

### 设计文档

| 文档 | 说明 |
| ------ | ------ |
| [系统架构设计](./backend/docs/系统架构设计文档.md) | 微服务架构、技术选型、服务拓扑 |
| [数据库设计](./backend/docs/数据库设计文档.md) | 14 张表结构、关系、索引 |
| [API 设计](./backend/docs/API设计文档.md) | 56 个接口详细文档 |

### 测试文档

| 文档 | 说明 |
| ------ | ------ |
| [测试计划](./backend/docs/测试计划.md) | 范围与不测项、分层、进入/出口准则、风险 |
| [测试设计](./backend/docs/测试设计文档.md) | 用例设计方法论与关键行为锁定 |
| [测试点拆解大纲](./backend/docs/测试点拆解-XMind大纲.md) | 服务→模块→测试点→方法标签（可导入 XMind） |
| [运行测试](./backend/docs/运行测试.md) | 测试环境配置与运行 |
| [手工测试用例-正式版](./backend/docs/手工测试用例-正式版.md) | 56 条编号用例（P0 冒烟 / P1 核心 / 探索 / 兼容） |
| [手动测试用例清单](./backend/docs/手动测试用例清单.md) | 29 项快速执行清单（冒烟/探索/视觉） |
| [缺陷台账](./backend/docs/缺陷台账.md) | 15 条产品缺陷单与定级标准 |
| [测试总结报告](./backend/docs/测试总结报告.md) | 执行统计、缺陷分析、出口判定、遗留风险 |
| [E2E 冒烟测试](./e2e/README.md) | Playwright 端到端测试 |
| [性能基线](./backend/perf/BASELINE.md) | Locust 基线与瓶颈定位实验 |

### 运维与开发

| 文档 | 说明 |
| ------ | ------ |
| [数据库本地部署](./backend/docs/数据库本地部署.md) | PostgreSQL 本地安装配置 |
| [故障排查指南](./backend/docs/故障排查指南.md) | 常见问题解决方案 |
| [项目展示讲解](./backend/docs/项目展示讲解内容.md) | 答辩/演示用内容 |

### 子项目文档

| 文档 | 说明 |
| ------ | ------ |
| [后端 README](./backend/README.md) | 后端开发指南 |
| [前端 README](./frontend/README.md) | 前端开发指南 |
| [E2E README](./e2e/README.md) | 端到端测试说明 |
| [文档中心](./backend/docs/README.md) | 后端文档完整索引 |

---

## 项目性质与分工

本项目为 4 人小组课程设计的**统一归档仓库**：提交历史为交付整理后的归集记录（单作者），不代表实际分工；业务代码由小组成员共同开发。

测试体系（测试计划、用例设计与拆解、56 条手工用例、315 条 pytest + 10 条 Vitest + 6 条 Playwright 自动化套件、覆盖率门禁、CI 合并门禁、Locust 性能基线、缺陷台账与测试报告）由小组**测试负责人**独立负责，入口见[测试计划](./backend/docs/测试计划.md)与[文档索引](./backend/docs/README.md)。

---

## 许可证

MIT 许可证。详见 [LICENSE](LICENSE)。

## 联系方式

**作者**: cherloner

[![GitHub](https://img.shields.io/badge/GitHub-cherloner-181717?logo=github)](https://github.com/cherloner)
[![Email](https://img.shields.io/badge/Email-1844390881@qq.com-D14836?logo=gmail)](mailto:1844390881@qq.com)

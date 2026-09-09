# 短视频学习平台 - 前端需求文档

本文档以 `frontend/` 代码现状为唯一基准，描述已实现功能及其现状。未实现的设计属性统一归入文末「扩展方向」章节。

## 1. 项目概述

移动端优先（Mobile-First）的短视频学习平台 Web 应用（H5）。通过沉浸式短视频流提供知识学习体验，核心特色包括类 TikTok 的交互、分片断点续传上传、基于心跳的学习进度追踪与智能视频切分。

### 1.1 技术栈

- **核心框架**: React 18 + TypeScript
- **构建工具**: Vite（`@vitejs/plugin-react`）
- **样式方案**: Tailwind CSS（移动端适配）
- **路由管理**: React Router v6
- **图标库**: Lucide React
- **HTTP 请求**: Axios（拦截器封装）
- **状态管理**: React Context（`AuthContext`，认证状态）
- **测试**: Vitest + React Testing Library

## 2. 信息架构

采用底部导航栏（Bottom Navigation）模式，包含 5 个核心 Tab（`BottomNav.tsx`）：

1. **首页 (Home)**: 沉浸式视频流
2. **课程 (Courses)**: 课程发现与列表
3. **创作 (Upload)**: 视频上传与智能拆分设置
4. **消息 (Inbox)**: 通知中心
5. **我的 (Profile)**: 个人数据与学习概览

完整路由清单见 `src/App.tsx`：`/`、`/courses`、`/upload`、`/inbox`、`/profile`、`/login`、`/video/:id`、`/search`、`/split`、`/video-split-result/:taskId`。

## 3. 功能模块（已实现）

### 3.1 用户认证模块

- **登录 (Login)**: 手机号 + 验证码登录。当前为前端 mock 实现（`src/pages/Login.tsx`）：验证码固定 `123456`、token 为 `mock-jwt-token`，未调用后端 API。支持 11 位手机号格式校验与验证码输入校验。
- **路由守卫 (ProtectedRoute)**: 未登录用户访问 `/upload`、`/inbox`、`/profile`、`/split`、`/video-split-result/:taskId` 时跳转 `/login`，并记录来源路径供登录后回跳。
- **退出登录 (Logout)**: 个人中心提供退出按钮，清除本地 token 并重置认证状态（`AuthContext.logout`）。
- **开发环境自动登录**: 无 token 时自动注入默认 UUID token（`00000000-0000-0000-0000-000000000001`），未登录也可浏览与上传。

### 3.2 首页视频流 (Home)

- **交互体验**: 全屏垂直滚动，使用 CSS Scroll Snap 实现「一次滑一个」；当前视图中心的视频自动播放，划出视图的视频自动暂停并重置（`VideoPlayer.tsx`）。
- **视频播放器**: 支持点击播放/暂停、底部可拖动进度条、长按 2X 倍速播放。
- **侧边栏**: 展示头像（关注）、点赞、评论、分享。
- **评论区**: 点击评论图标从底部弹出评论面板，支持一级评论展示与发送（当前为前端本地状态，无二级回复）。
- **数据来源**: 优先调用 `GET /feed/recommend`，失败或为空时降级到 `mockData.ts`。

### 3.3 课程与搜索 (Courses & Search)

- **课程 (Courses)**: 静态占位列表（5 个示例课程卡片），暂无真实数据接口。
- **搜索 (Search)**: 关键词搜索（300ms 防抖）、联想词（`GET /search/suggest`）、时长筛选（1 分钟内 / 1-3 分钟）、排序（综合/最新/最热）、标签过滤（编程/英语/健身）。调用 `GET /search/videos`，失败或为空时降级到前端 mock 过滤。

### 3.4 创作中心 (Upload & Creation)

- **文件选择与校验**: 支持选择本地视频文件，读取视频时长。
- **时长约束**: 前端不限制视频时长，允许上传任意时长视频；时长约束交由后端或审核策略处理。
- **分片上传 (useResumableUpload)**: 将文件切分为 2MB/片，调用 `POST /upload/init` 初始化、`PUT <upload_url>` 上传分片、`POST /upload/complete` 合并。
- **断点续传**: 使用 LocalStorage（key 为 `upload_<文件名>_<文件大小>`）记录 `upload_id`、`upload_url` 与已完成的 `chunk_index`；刷新或中断后重新选择同一文件可跳过已上传分片。
- **重试机制**: 单个分片失败触发指数退避重试，最多 3 次。
- **UI 反馈**: 显示精确百分比进度与当前分片状态（预处理 → 上传中 → 转码中 → 完成）。
- **智能拆分设置**: 提供三种模式选择：全自动 (auto)、混合模式 (hybrid)、纯手动 (manual)。上传完成后自动跳转切分页。

### 3.5 消息中心 (Inbox)

- **分类展示**: 顶部「赞 / 评论 / 粉丝」三个分类入口，下方为系统通知列表（当前为静态占位数据）。

### 3.6 学习系统 (Learning System)

- **视频详情页**: 独立页面 `/video/:id` 用于专注学习（`VideoDetail.tsx` + `VideoLearningPlayer.tsx`）。
- **心跳机制**: 视频播放期间每 10 秒发送一次心跳（`POST /learn/heartbeat`），播放开始、暂停、页面隐藏、组件卸载时均触发；上报 `video_id`、`position`、`duration`、`buffered`、`playing`。
- **断点续播**: 从后端获取 `last_position`，自动跳转到上次播放位置；从搜索页进入时弹窗询问是否继续。
- **完成反馈**: 播放进度达到 90% 时自动暂停并弹出模态框，询问「我已学会 (learned)」或「需复习 (review_needed)」，调用 `POST /learn/complete`。

### 3.7 个人中心 (Profile)

- **用户信息**: 展示头像、昵称、简介、关注/粉丝/获赞数。
- **编辑资料 (EditProfileModal)**: 支持修改昵称、简介、性别、所在地、学校与头像（头像经 `POST /upload/image` 上传，资料经 `PUT /auth/profile` 保存）。
- **学习数据看板 (UserProfileStats)**: 展示「累计学习时长」与「已修完课程数」；待复习列表（横向滚动）仅展示 `review_needed` 记录，点击跳转视频详情页复习。
- **作品管理**: 九宫格展示学习记录（含 `learned` / `review_needed` 状态标记）。
- **数据来源**: 学习记录经 `GET /learn/records` 获取。

## 4. API 接口需求

前端通过 `src/services/api.ts` 对接以下 RESTful 接口（`baseURL: '/api'`，经 vite proxy → nginx 网关转发）：

### Auth
- `POST /auth/send_code`: 发送验证码
- `POST /auth/login_by_phone`: 手机号登录
- `GET /user/me`: 获取当前用户信息
- `PUT /auth/profile`: 更新个人资料

### Upload
- `POST /upload/init`: 初始化上传（返回 upload_id 与 upload_url）
- `PUT <upload_url>`: 上传分片（二进制 Body，header 携带 upload_id / chunk_index）
- `POST /upload/complete`: 合并分片
- `POST /upload/image`: 上传图片（Base64）

### Learning
- `POST /learn/heartbeat`: 发送心跳（进度同步）
- `POST /learn/complete`: 标记学习状态（learned / review_needed）
- `GET /learn/records`: 获取学习记录

### Feed / Content
- `GET /feed/recommend`: 获取首页推荐流
- `GET /feed/video/:id`: 获取视频详情
- `GET /feed/my_videos`: 获取我的视频列表

### Split
- `POST /split/analyze`: 智能分析视频（GLM，长耗时）
- `POST /split/direct-split`: 直接切分（基于已有分析结果）
- `POST /split/tasks`: 创建异步切分任务
- `GET /split/tasks`: 获取当前用户切分任务列表
- `GET /split/tasks/:id`: 获取任务状态
- `GET /split/tasks/:id/result`: 获取切分结果
- `POST /split/publish-segments`: 发布选中片段到主页

### Search
- `GET /search/suggest`: 搜索联想词
- `GET /search/videos`: 搜索视频

## 5. 非功能性需求（已实现）

1. **移动端适配**: 禁用视口缩放（`user-scalable=no`）、适配刘海屏（`viewport-fit=cover` 与 `safe-area-inset`）、触摸目标适中。
2. **可靠性**: 分片上传支持断点续传与指数退避重试，弱网环境下不会因网络抖动从头重传。
3. **开发体验**: 开发环境自动注入默认 token，未登录也可浏览与上传；后端不可用时前端有 mock 数据降级。

## 6. 扩展方向（未实现）

以下为设计属性，尚未在代码中实现，供后续迭代参考：

- **本地压缩**: 上传前调用本地压缩逻辑（如 ffmpeg.wasm）减小文件体积。当前仅做 mock 预处理，未接入真实压缩。
- **封面选择**: 从视频中截取帧或上传自定义图片作为封面。当前未实现。
- **二级回复（楼中楼）**: 评论区支持主评论与子评论的层级展示。当前仅支持一级评论。
- **搜索历史记录**: 展示最近搜索历史，支持点击快速搜索与清除。当前未实现。
- **虚拟滚动 / 懒加载**: 视频列表虚拟滚动或懒加载，防止 DOM 节点过多。当前首页一次性渲染全部视频。
- **图片 CDN 缩略图**: 图片使用 CDN 缩略图，非必要不加载原图。当前直接加载原图。
- **真实登录 API 对接**: 登录页当前为前端 mock，未调用后端 `POST /auth/send_code` 与 `POST /auth/login_by_phone`。真实登录链路由后端集成测试覆盖。

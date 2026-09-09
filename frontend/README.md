# 移动端前端项目 (Frontend)

短视频学习平台的移动端 Web 应用（H5），基于 **React 18 + TypeScript + Vite + Tailwind CSS** 构建。

> 技术栈以 `package.json` 为唯一基准：本项目使用 React 18（`react` / `react-dom` / `react-router-dom` / `@vitejs/plugin-react`）。

## 快速开始

```bash
# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev

# 3. 访问
# 本机: http://localhost:3000
# 手机测试: 手机与电脑同一局域网，访问 http://<电脑IP>:3000
```

开发服务器监听 `0.0.0.0:3000`（`vite.config.ts` 中 `server.host = '0.0.0.0'`、`server.port = 3000`）。

## 功能模块

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 (Home) | 沉浸式短视频播放流（仿 TikTok/抖音），全屏垂直滚动 |
| `/courses` | 课程 (Courses) | 课程发现与列表（静态占位数据） |
| `/upload` | 创作 (Upload) | 视频上传与智能拆分设置（需登录） |
| `/inbox` | 消息 (Inbox) | 系统通知与互动消息（静态占位数据） |
| `/profile` | 我的 (Profile) | 个人中心、学习数据看板与作品管理（需登录） |
| `/login` | 登录 (Login) | 手机号 + 验证码登录（前端 mock 实现） |
| `/video/:id` | 视频详情 (VideoDetail) | 专注学习页，含心跳进度与断点续播 |
| `/search` | 搜索 (Search) | 关键词搜索、联想词、筛选与排序 |
| `/split` | 视频切分 (VideoSplit) | 智能拆分任务发起与状态跟踪（需登录） |
| `/video-split-result/:taskId` | 切分结果 (VideoSplitResult) | 切分片段预览、播放、下载与发布（需登录） |

路由定义见 `src/App.tsx`。`/upload`、`/inbox`、`/profile`、`/split`、`/video-split-result/:taskId` 由 `ProtectedRoute` 守卫，未登录跳转 `/login` 并记录来源路径。

## 技术栈

- **React 18**: UI 库
- **TypeScript**: 类型系统
- **Vite**: 构建工具（`@vitejs/plugin-react`）
- **Tailwind CSS**: 样式框架
- **React Router 6**: 路由管理
- **Lucide React**: 图标库
- **Axios**: HTTP 请求（拦截器封装）
- **React Context**: 认证状态管理（`AuthContext`）
- **Vitest + React Testing Library**: 单元测试

## 目录结构

```
src/
├── App.tsx                  # 路由定义
├── main.tsx                 # 入口
├── layouts/MainLayout.tsx   # 主布局（含底部导航）
├── pages/                   # 10 个页面
├── components/              # 7 个组件
├── context/AuthContext.tsx  # 认证状态
├── hooks/useResumableUpload.ts  # 分片断点续传
└── services/
    ├── api.ts               # Axios 实例与 API 封装
    └── mockData.ts          # 前端 mock 视频数据
```

## 后端对接

### 代理配置

`vite.config.ts` 中配置了开发代理，全部转发到本地网关（nginx，端口 80）：

```typescript
server: {
  host: '0.0.0.0',
  port: 3000,
  proxy: {
    '/api':               { target: 'http://localhost', changeOrigin: true },
    '/smart_split_output':{ target: 'http://localhost', changeOrigin: true },
    '/uploads':           { target: 'http://localhost', changeOrigin: true },
    '/videos':            { target: 'http://localhost', changeOrigin: true },
  },
}
```

请求链路：前端 → vite proxy → nginx 网关（`http://localhost`，端口 80）→ 各微服务。启动前端前需确保网关与后端服务已就绪。

### API 封装

`src/services/api.ts` 基于 Axios 实例（`baseURL: '/api'`）封装了各领域接口：

- **authApi**: `POST /auth/send_code`、`POST /auth/login_by_phone`、`GET /user/me`
- **videoApi**: `GET /feed/recommend`、`GET /feed/video/:id`
- **uploadApi**: `POST /upload/init`、`PUT <upload_url>`（分片）、`POST /upload/complete`
- **splitApi**: `POST /split/analyze`、`POST /split/direct-split`、`POST /split/tasks`、`GET /split/tasks`、`GET /split/tasks/:id`、`GET /split/tasks/:id/result`、`POST /split/publish-segments`、`PUT /auth/profile`、`POST /upload/image`
- **contentApi**: `GET /feed/recommend`、`GET /feed/my_videos`
- **learnApi**: `POST /learn/heartbeat`、`POST /learn/complete`、`GET /learn/records`
- **searchApi**: `GET /search/suggest`、`GET /search/videos`

请求拦截器自动附加 `Authorization: Bearer <token>`；开发环境无 token 时自动注入默认 UUID token（`00000000-0000-0000-0000-000000000001`）。响应拦截器仅在非开发环境且收到 401 时跳转登录页。

### 对接现状

- **首页 / 搜索 / 上传 / 切分 / 学习记录** 走真实后端 API（经 vite proxy → nginx 网关 → 微服务）。
- **登录页为前端 mock**（`src/pages/Login.tsx`）：验证码固定 `123456`、token 为 `mock-jwt-token`，未调用后端 API。真实登录链路由后端集成测试覆盖。
- **开发环境自动注入默认 UUID token**（`AuthContext.tsx`），未登录也可浏览与上传。
- 后端不可用时，首页、搜索、视频详情有前端 mock 数据降级（`mockData.ts`）。

## 测试

```bash
npm test          # vitest run（单元测试）
npm run test:watch
npm run lint      # eslint
npm run build     # tsc -b && vite build
```

单元测试位于 `src/__tests__/`（Vitest + React Testing Library + jsdom），覆盖登录页、路由守卫与认证上下文。

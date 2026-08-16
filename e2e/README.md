# E2E 冒烟测试（Playwright）

面向**前端核心业务链路**的端到端冒烟测试，验证"页面能渲染、核心交互可用、前端与后端链路打通"。

## 覆盖用例（5 个文件 6 条用例）

| 文件 | 用例 | 验证内容 |
|------|------|---------|
| `login.spec.ts` | 登录流程 | 手机号+验证码 → 跳转首页；非法手机号被拦截 |
| `home.spec.ts` | 首页推荐流 | 视频流卡片渲染（走真实 feed/recommend 接口） |
| `search.spec.ts` | 搜索 | 关键词输入 → 结果出现（真实 search 接口，失败降级 mock） |
| `upload.spec.ts` | 上传 | 真实视频文件 → 分片上传 → 完成跳转（真实 upload 接口） |
| `split.spec.ts` | 切分全流程 | 上传 → 直连 direct-split（ffmpeg 切分）→ 结果页渲染 → 列表任务状态 → 查看结果 |

> **切分用例说明**：analyze（AI 知识点分析）依赖重型 AI 依赖（torch/opencv + SenseVoice 权重），
> E2E 环境不安装——缺失时明确报错是设计意图（backend/tests/unit/test_pipeline_flow.py），
> GLM 降级路径由后端单测覆盖。因此切分用例经 `direct-split` API 验证 ffmpeg 切分全链路。
> 该用例驱动修复了 3 个缺陷：direct-split 路径硬编码 `/app/data`（本地/CI 部署必失败）、
> "查看结果"按钮死路由、任务状态跨会话不可见（后端 `/api/split/tasks` 补 video_id + 前端对接）。

## 前置条件

```bash
# 1. PostgreSQL（本机）
/opt/homebrew/opt/postgresql@15/bin/pg_ctl -D /opt/homebrew/var/postgresql@15 -l /tmp/pg15.log start

# 2. 后端服务（各终端, 需开发库已有 mock 数据）
cd backend
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.auth.app.main:app --port 8001
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.content.app.main:app --port 8002
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.upload.app.main:app --port 8003
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.search.app.main:app --port 8006
# (可选) course/notification/split: 8005/8007/8004

# 3. 本地网关（nginx, 配置见 gateway/nginx-local.conf）
nginx -c /Volumes/code/testAgent/软件工程课程设计项目/backend/gateway/nginx-local.conf -p /Volumes/code/testAgent/软件工程课程设计项目/backend
# 验证: curl http://localhost/api/feed/recommend

# 4. 前端 dev server
cd frontend && npm run dev   # http://localhost:3000

# 5. 运行 E2E（首次需安装浏览器）
cd e2e
npm install
npx playwright install chromium
npm test
```

## 实测结果（2026-08-13）

```
$ npx playwright test
  6 passed (15.5s)
```

登录 2 条 + 首页 1 条 + 搜索 1 条 + 上传 1 条 + 切分全流程 1 条，全链路通过（真实后端 + 网关）。

## 本地运行注意事项（踩过的坑）

1. **upload 服务必须设置 `UPLOAD_BASE_DIR`**：默认 `/app/data/uploads`（Docker 路径），本机不设会 `Read-only file system: '/app'` 500；
2. **nginx 临时目录权限**：brew nginx 的 `client_body_temp` 属 root，5MB 分片落盘失败 → 本地配置已指定 `client_body_temp_path /tmp/nginx_body_temp`（见 `gateway/nginx-local.conf`）；
3. **前端登录页为 mock**：`frontend/src/pages/Login.tsx` 验证码固定 123456、token 为 mock-jwt-token、未调后端 API——E2E 登录用例验证 UI 流程，真实登录链路由后端集成测试覆盖；开发环境其余页面自动注入默认 UUID token（`AuthContext.tsx`）。
4. **vite 冷编译与并行 worker 竞争**：dev server 首次访问需编译 1500+ 模块，多 worker 并行首访会互相竞争导致超时（实测偶发）。已用 `workers: 1` 串行执行换取确定性（冒烟 6 条用例串行 <20s）；CI 就绪阶段另有路由预热步骤。

## 说明

- **登录页为前端 mock**（`frontend/src/pages/Login.tsx`：验证码固定 123456、token 为 mock-jwt-token、未调后端 API）——本用例验证 UI 流程，真实登录 API 链路由后端集成测试覆盖（`backend/tests/api/test_auth.py`）。
- **开发环境自动注入 UUID token**（`frontend/src/context/AuthContext.tsx`），未登录也可浏览/上传。
- 首页/搜索/上传走真实后端 API（经 vite proxy → nginx 网关 → 微服务），后端不可用时前端有 mock fallback（搜索页）或报错。
- 上传素材使用 `short_video/3分钟学习微积分.mp4`（7.7MB，前端 2MB/片切 4 片，服务端分片上限 5MB，验证分片上传链路）。

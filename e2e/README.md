# E2E 冒烟测试（Playwright）

面向前端核心业务链路的端到端冒烟测试，验证「页面能渲染、核心交互可用、前端与后端链路打通」。

## 覆盖用例（5 个文件 6 条用例）

| 文件 | 用例 | 验证内容 |
| ------ | ------ | --------- |
| `login.spec.ts` | 登录流程 | 手机号+验证码 → 跳转首页；非法手机号被拦截 |
| `login.spec.ts` | 登录页校验 | 非法手机号（10 位）被拦截，不进入验证码阶段 |
| `home.spec.ts` | 首页推荐流 | 视频流卡片渲染（走真实 feed/recommend 接口） |
| `search.spec.ts` | 搜索 | 关键词输入 → 结果出现（真实 search 接口，失败降级 mock） |
| `upload.spec.ts` | 上传 | 真实视频文件 → 分片上传 → 完成跳转（真实 upload 接口） |
| `split.spec.ts` | 切分全流程 | 上传 → 直连 direct-split（ffmpeg 切分）→ 结果页渲染 → 列表任务状态 → 查看结果 |

用例数经 `npx playwright test --list` 核验：6 条用例，分布在 5 个 spec 文件。

> **切分用例说明**：analyze（AI 知识点分析）依赖重型 AI 依赖（torch/opencv + SenseVoice 权重），E2E 环境不安装，缺失时明确报错是设计意图（由后端单测覆盖）。因此切分用例经 `direct-split` API 验证 ffmpeg 切分全链路。该用例驱动修复了 3 个缺陷：direct-split 路径硬编码 `/app/data`（本地/CI 部署必失败）、「查看结果」按钮死路由、任务状态跨会话不可见（后端 `/api/split/tasks` 补 video_id + 前端对接）。

## 前置条件

```bash
# 1. PostgreSQL（本机）
/opt/homebrew/opt/postgresql@15/bin/pg_ctl -D /opt/homebrew/var/postgresql@15 -l /tmp/pg15.log start

# 2. 后端服务（各终端，需开发库已有 mock 数据）
cd backend
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.auth.app.main:app --port 8001
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.content.app.main:app --port 8002
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.upload.app.main:app --port 8003
DB_HOST=127.0.0.1 .venv/bin/uvicorn services.search.app.main:app --port 8006
# (可选) course/notification/split: 8005/8007/8004

# 3. 本地网关（nginx，配置见 gateway/nginx-local.conf）
nginx -c "$PWD/gateway/nginx-local.conf" -p "$PWD"
# 验证: curl http://localhost/api/feed/recommend

# 4. 前端 dev server
cd frontend && npm run dev   # http://localhost:3000

# 5. 运行 E2E（首次需安装浏览器）
cd e2e
npm install
npx playwright install chromium
npm test
```

## 运行命令

```bash
npm test              # playwright test（默认 chromium，串行）
npm run test:headed   # playwright test --headed（有头模式调试）
npm run evidence      # 发布冒烟留痕：逐例截图 + trace 落 backend/docs/manual-evidence/
```

配置见 `playwright.config.ts`：`baseURL` 为 `http://localhost:3000`，`workers: 1` 串行执行，`retries: 0`，超时 60s。

## 本地运行注意事项（踩过的坑）

1. **upload 与 split 服务都必须设置 `UPLOAD_BASE_DIR`**：默认 `/app/data/uploads`（Docker 路径），本机不设 upload 报 `Read-only file system: '/app'` 500；split 更隐蔽——上传正常，但 direct-split 会 `Error opening input file /app/data/uploads/...`（400"视频提取失败"，2026-09-04 实测坐实）。启动示例：`UPLOAD_BASE_DIR=$PWD/data/uploads DB_HOST=127.0.0.1 .venv/bin/uvicorn services.split.app.main:app --port 8004`。
2. **nginx 临时目录权限**：brew nginx 的 `client_body_temp` 属 root，5MB 分片落盘失败 → 本地配置已指定 `client_body_temp_path /tmp/nginx_body_temp`（见 `gateway/nginx-local.conf`）。
3. **前端登录页为 mock**：`frontend/src/pages/Login.tsx` 验证码固定 123456、token 为 mock-jwt-token、未调后端 API。E2E 登录用例验证 UI 流程，真实登录链路由后端集成测试覆盖。
4. **vite 冷编译与并行 worker 竞争**：dev server 首次访问需编译 1500+ 模块，多 worker 并行首访会互相竞争导致超时。已用 `workers: 1` 串行执行换取确定性（冒烟 6 条用例串行 <20s）。
5. **重启/重建后端容器后，网关会把 `split` 链路整体打成 502**（BUG-016，2026-09-09 E2E 首跑坐实）：nginx 在配置加载时一次性解析 `upstream { server split_service:8004; }` 并缓存容器 IP，容器重建拿到新 IP 后 nginx 仍用旧地址——网关日志 `connect() failed (111: Connection refused) upstream: "http://172.19.0.10:8004/..."`，而容器内按服务名直连 `/health` 当时就是 200（以这一定界分清“产品挂”还是“网关没跟上”）。
   - 临时恢复：`docker exec api_gateway nginx -s reload`（已写进本仓运行手册）
   - 根治建议（挂起）：`gateway/nginx.conf` 加 `resolver 127.0.0.11 valid=10s;` 并改用变量 `proxy_pass`，或给网关配置依赖服务重启后的 reload
6. **跑切分/上传用例前确认服务健在**：先 `curl http://localhost/health`（网关）与 `curl http://localhost:8004/health`（split），再跑 `npm test`。服务级健康检查**只在各自端口 `/health`**，网关不转发 `/api/*/health`（拿这个路径验证会得到 404，属文档陷阱，见 BUG-017）。

## 复跑记录

| 日期 | 环境 | 结果 |
| --- | --- | --- |
| 2026-09-04 | Docker 全栈 + 本机 vite dev | 首跑 upload/split 超时/400 → 补 `UPLOAD_BASE_DIR` 后 6/6（15.1s） |
| 2026-09-09 | Docker 全栈 + 本机 vite dev | 首跑 5/6：split 因 `/api/split/*` 502 失败 → 定界为网关上游 IP 陈旧（BUG-016）→ `nginx -s reload` 后 6/6（19.6s）；留痕截图与 trace 已归档 `backend/docs/manual-evidence/` |

## 说明

- **登录页为前端 mock**（`frontend/src/pages/Login.tsx`：验证码固定 123456、token 为 mock-jwt-token、未调后端 API）。本用例验证 UI 流程，真实登录 API 链路由后端集成测试覆盖（`backend/tests/api/test_auth.py`）。
- **开发环境自动注入 UUID token**（`frontend/src/context/AuthContext.tsx`），未登录也可浏览/上传。
- 首页/搜索/上传走真实后端 API（经 vite proxy → nginx 网关 → 微服务），后端不可用时前端有 mock fallback（搜索页）或报错。
- 上传素材使用 `short_video/3分钟学习微积分.mp4`（7.7MB，前端 2MB/片切 4 片，服务端分片上限 5MB，验证分片上传链路）。

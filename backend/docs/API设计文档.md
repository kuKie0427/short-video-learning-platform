# 短视频学习平台 - API接口设计文档

本文档描述后端各微服务对外提供的全部 HTTP 接口。接口以各服务 `services/*/app/api/` 下的路由实现为准，共 7 个业务微服务、56 个业务端点，另含网关、健康检查与文档端点。

---

## 一、接口设计规范

### 1.1 基础规范

- **调用协议**：HTTP + RESTful 风格。本地与容器部署经 Nginx 网关（监听 80）按路径前缀转发到各服务；各服务直接暴露时监听 8001–8007。
- **路由前缀**：所有业务端点统一使用 `/api/<域>` 前缀（如 `/api/auth`、`/api/feed`），不含 `/api/v1` 版本段。各服务的路由前缀即最终路径前缀，网关转发时按前缀透传。
- **数据格式**：请求体与响应体统一为 JSON；分片上传的请求体为二进制流；图片上传请求体为 Base64 字符串。
- **字符编码**：UTF-8。
- **鉴权方式**：JWT。受保护接口在请求头携带 `Authorization: Bearer <token>`，由 `HTTPBearer` 解析。JWT 采用 `HS256` 签名，访问令牌有效期由 `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` 配置（默认 30 分钟，登录响应 `expires_in` 即返回 1800 秒）。系统不设独立刷新令牌：`POST /api/auth/refresh` 以仍在有效期内的访问令牌签发新令牌。

### 1.2 鉴权分级

各端点按路由实现分三级：

| 级别 | 依赖 | 缺少请求头 | Token 无效/过期 |
|------|------|-----------|----------------|
| 强制鉴权 | `get_current_user` | 403（Not authenticated） | 401（认证凭证已过期） |
| 可选鉴权 | `get_optional_user` | 以匿名身份继续处理 | 以匿名身份继续处理 |
| 免鉴权 | 无 | 直接处理 | 直接处理 |

免鉴权端点：验证码发送、手机号登录、简化视频分割。可选鉴权端点：Feed 列表、视频详情、Feed 内搜索、图片上传等，未登录时可访问、登录后额外返回个性化字段（`is_liked`、`is_favorited`、`last_position`）。

开发环境（`ENVIRONMENT=development`）下，`get_current_user` / `verify_token` 允许直接把 36 位 UUID 字符串（含 4 个连字符）当作 `user_id` 传入（跳过 JWT 校验），用于本地联调；用户不存在时自动创建（`phone=dev_<前8位>`、`nickname=测试用户`）。生产环境强制走 JWT 校验。

### 1.3 统一响应格式

绝大多数业务端点通过 `common/utils/response.py` 的 `success_response` / `error_response` 返回统一信封：

```json
{
  "code": 200,
  "message": "success",
  "data": { }
}
```

- 成功：HTTP 状态恒为 200，`code` 为 200，业务数据在 `data`。
- 失败：`error_response` 使 HTTP 状态等于 `code`（限 400–599），`code`、`message`、`data` 同步返回。

以下端点直接返回裸对象，不加信封，按各自接口说明为准：`POST /api/feed/feedback`、`GET /api/interaction/user/likes`、`GET /api/interaction/user/favorites`、`POST /api/split/tasks/{task_id}/confirm`、`POST /api/split/simple-split`。

各服务根路径 `GET /` 与 `GET /health` 返回服务信息对象，同样不经业务信封。

异常处理按服务存在差异（详见 13.9）：Auth 服务对全部异常（含 `HTTPException`）做全局包装；Content 服务包装参数校验、数据库与未捕获异常，但 `HTTPException` 原样返回 `{"detail": ...}`；其余服务无全局处理器，返回 FastAPI 默认形态。

### 1.4 分页与列表响应

列表类接口接受 `page`（默认 1，`ge=1`）、`page_size`（默认 20）查询参数，`page_size` 上限按端点为 50 或 100（各接口处标注）。学习记录接口不分页。响应存在三种列表形态，按端点标注为准：

**形态一：`items` + `pagination`**（课程列表、视频搜索、消息列表）：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [],
    "pagination": { "page": 1, "page_size": 20, "total": 100, "has_more": true }
  }
}
```

**形态二：扁平字段**（Feed 各列表、关注/粉丝列表、评论列表、学习记录）：

- Feed 列表：`data` 内放 `videos` 数组，同级给 `total`、`page`、`page_size`、`has_next`，推荐流、关注流、热门另含 `next_cursor`（随机生成的占位 UUID，无真实游标语义；`my_videos` 不含该字段）。
- 关注/粉丝列表：`data` 内放 `users` 数组，同级给 `total`、`page`、`page_size`。
- 评论列表：`data` 内放 `comments` 数组，同级给 `total`（仅统计顶级评论）、`page`、`page_size`。
- 学习记录：`data` 内放 `records` 数组，同级给 `total`。

**形态三：裸数组**（`GET /api/split/tasks`、`GET /api/interaction/user/likes`、`GET /api/interaction/user/favorites`）：`data` 直接是数组，无分页元数据。

`GET /api/feed/search` 的 `data` 为 `{ "videos": [...], "total": n, "query": "q", "search_type": "all" }`，不含分页字段。

### 1.5 状态码约定

| HTTP 状态 | 含义 | 触发场景 |
|-----------|------|----------|
| 200 | 处理完成 | 所有成功响应；业务失败经信封 `code` 表达时 HTTP 仍可能为 200 |
| 400 | 请求参数/状态错误 | 验证码错误、分片缺参、任务状态不允许操作、时间范围越界等 |
| 401 | 认证失败 | JWT 无效或过期（`verify_token` 抛出）；`my_videos` 未登录 |
| 403 | 未认证或无权限 | 缺少 `Authorization` 请求头（`HTTPBearer` 默认）；越权操作他人视频/课程/评论 |
| 404 | 资源不存在 | 视频、课程、任务、上传、用户、评论不存在 |
| 422 | 请求体校验失败 | Pydantic 校验不通过；Auth/Content 服务返回 `data.errors` 字段级错误列表，其余服务返回 FastAPI 默认形态 |
| 500 | 服务器内部错误 | 未捕获异常、数据库异常、分片合并失败 |

### 1.6 网关路由

Nginx 网关（`gateway/nginx.conf`，监听 80）按前缀转发，未配置任何限流规则。上传接口透传自定义请求头 `upload_id`、`chunk_index`，请求体上限 `client_max_body_size 10G`；拆分接口因可能调用 GLM 分析，超时放宽到 900 秒。静态资源 `/uploads/`、`/videos/`、`/smart_split_output/` 由网关直出；`/health` 由网关直接返回 `healthy`。

| 前缀 | 转发目标 |
|------|----------|
| `/api/auth` | Auth 服务 :8001 |
| `/api/feed`、`/api/interaction`、`/api/follow`、`/api/learn` | Content 服务 :8002 |
| `/api/upload`、`/api/videos/upload` | Upload 服务 :8003 |
| `/api/split` | Split 服务 :8004 |
| `/api/courses` | Course 服务 :8005 |
| `/api/search` | Search 服务 :8006 |
| `/api/inbox` | Notification 服务 :8007 |

`/api/video`、`/api/videos/upload` 为兼容旧路径预留的转发规则，服务端未定义对应路由。

---

## 二、认证与用户资料（Auth 服务 :8001）

路由前缀 `/api/auth`。

### 2.1 发送验证码

`POST /api/auth/send-code` ｜ 免鉴权

请求体：

```json
{ "phone": "13800138000" }
```

`phone` 长度需 ≥ 10，否则 422。验证码为 6 位数字，写入 Redis（键 `sms_code:{phone}`，含错误次数计数），有效期 `SMS_CODE_EXPIRE_SECONDS`（默认 300 秒）。开发环境默认使用模拟短信服务（`SMS_PROVIDER=mock`），并在响应 `data.code` 回显验证码便于联调；生产环境需在 `SMS_PROVIDER` 配置 aliyun/tencent，对应密钥缺失时回退模拟服务。

响应 `data`：

```json
{ "success": true, "expires_in": 300, "code": "123456" }
```

`code` 仅在开发环境返回。成功 `message="验证码已发送"`；Redis 存储失败或短信发送失败返回 500。

### 2.2 手机号验证码登录

`POST /api/auth/login` ｜ 免鉴权

请求体：

```json
{ "phone": "13800138000", "code": "123456" }
```

校验 Redis 中的验证码。验证码缺失（未发送或已过期）返回 `code=400`、`message="验证码已过期或未发送"`；验证码错误返回 `message="验证码错误"`；连续错误达 `SMS_CODE_MAX_ATTEMPTS`（默认 5）次后该验证码作废，返回 `message="验证码错误次数过多，请重新获取"`。手机号无对应账户时自动注册，默认昵称 `用户<手机号后4位>`、语言 `zh-CN`、角色 `["learner"]`。

响应 `data`：

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "phone": "13800138000",
    "nickname": "张三",
    "avatar": "https://example.com/avatar.jpg",
    "roles": ["learner"]
  }
}
```

成功 `message="登录成功"`。

### 2.3 获取用户资料

`GET /api/auth/profile` ｜ 强制鉴权

响应 `data`：

```json
{
  "id": "uuid",
  "phone": "13800138000",
  "nickname": "张三",
  "avatar": "https://example.com/avatar.jpg",
  "bio": "学习爱好者",
  "gender": "male",
  "location": "杭州",
  "school": "示例大学",
  "language": "zh-CN",
  "roles": ["learner"],
  "created_at": "2025-01-01T00:00:00+00:00"
}
```

### 2.4 更新用户资料

`PUT /api/auth/profile` ｜ 强制鉴权

请求体（字段均可选，仅更新传入字段）：

```json
{
  "nickname": "张三",
  "avatar_url": "https://example.com/avatar.jpg",
  "bio": "学习爱好者",
  "gender": "female",
  "location": "杭州",
  "school": "示例大学",
  "language": "zh-CN"
}
```

请求字段名为 `avatar_url`；响应 `data` 结构同 2.3，其中头像字段名为 `avatar`，`message="用户资料已更新"`。

### 2.5 刷新访问令牌

`POST /api/auth/refresh` ｜ 强制鉴权

用当前有效令牌换取新令牌，签发逻辑同登录。响应 `data`：

```json
{ "token": "<新JWT>", "token_type": "bearer", "expires_in": 1800, "user_id": "uuid" }
```

成功 `message="令牌已刷新"`。

---

## 三、内容与推荐（Content 服务 :8002 · Feed）

路由前缀 `/api/feed`。Feed 列表项统一为以下结构（`author` 信息平铺为 `author_id` / `author_nickname` / `author_avatar`）：

```json
{
  "id": "uuid",
  "title": "Python快速入门",
  "description": "Python 入门教程",
  "tags": ["Python", "编程"],
  "duration": 120,
  "play_url": "https://example.com/video.mp4",
  "cover_url": "https://example.com/cover.jpg",
  "language": "zh-CN",
  "status": "online",
  "video_type": "short",
  "author_id": "uuid",
  "author_nickname": "张三",
  "author_avatar": "https://example.com/avatar.jpg",
  "like_count": 50,
  "comment_count": 20,
  "favorite_count": 30,
  "is_liked": false,
  "is_favorited": false,
  "created_at": "2025-01-01T00:00:00+00:00"
}
```

Feed 列表响应统一为 `data.videos`（上述项数组）+ `total` + `page` + `page_size` + `has_next` + `next_cursor`（`my_videos` 除外，见 3.7）。

### 3.1 智能推荐视频流

`GET /api/feed/recommend` ｜ 可选鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页数量，默认 20，最大 50 |
| strategy | string | 否 | 推荐策略，默认 `hybrid`，取 `hybrid`/`content`/`collaborative`/`popularity` |

返回 `status` 为 `online` 或 `published` 的短视频。未登录时按匿名策略推荐；登录时结合用户互动记录。

### 3.2 多样化推荐

`GET /api/feed/diverse` ｜ 强制鉴权

参数 `page`、`page_size`（最大 50）。多算法混合召回，响应为 Feed 列表结构。

### 3.3 个性化推荐

`GET /api/feed/personalized` ｜ 强制鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量，最大 50 |
| tags | string | 否 | 标签，逗号分隔，命中任一即保留 |
| language | string | 否 | 语言过滤 |

基于内容推荐召回后按 `tags`、`language` 过滤，响应为 Feed 列表结构。

### 3.4 关注用户视频流

`GET /api/feed/following` ｜ 强制鉴权

参数 `page`、`page_size`（最大 50）。返回当前用户关注对象发布的 `online` 短视频；无关注对象时返回空数组。响应为 Feed 列表结构。

### 3.5 热门视频

`GET /api/feed/hot` ｜ 可选鉴权

参数 `page`、`page_size`（最大 50）。按点赞数降序返回 `online` 短视频，响应为 Feed 列表结构。

### 3.6 搜索视频（Feed 内搜索）

`GET /api/feed/search` ｜ 可选鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | 是 | 关键词，长度 1–100 |
| search_type | string | 否 | 搜索范围，默认 `all`，取 `all`/`title`/`tag`/`author` |
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量，最大 50 |

`q` 中的 `%`、`_`、`\` 按字面量转义匹配。响应 `data` 为 `{ "videos": [...], "total": n, "query": "q", "search_type": "all" }`，不含分页字段。

### 3.7 我的视频列表

`GET /api/feed/my_videos` ｜ 可选鉴权（未登录返回 401）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量，最大 50 |
| days | integer | 否 | 仅返回最近 N 天，范围 1–30 |

未登录时返回 `code=401`、`message="需要登录"`。返回当前用户上传的视频（含各状态），按创建时间倒序。列表项在标准 Feed 结构上追加 `long_video_id`（长视频对应记录，否则为 null），`is_liked`/`is_favorited` 恒为 `false`。响应为 `videos` + `total` + `page` + `page_size` + `has_next`（不含 `next_cursor`）。

### 3.8 推荐反馈

`POST /api/feed/feedback` ｜ 强制鉴权

请求体：

```json
{ "video_id": "uuid", "action_type": "like", "feedback_value": 1.0 }
```

`action_type` 取 `like`/`favorite`/`watch`/`skip`，`feedback_value` 默认 1.0。视频不存在返回 404（`{"detail": "视频不存在"}`）。成功返回裸对象 `{ "message": "反馈已接收，将用于优化推荐效果" }`（不经信封）。

### 3.9 视频详情

`GET /api/feed/video/{video_id}` ｜ 可选鉴权

仅返回 `status=online` 的视频，否则 404（`message="视频不存在或已被删除"`）。响应 `data` 为单个视频对象：

```json
{
  "id": "uuid",
  "title": "Python快速入门",
  "description": "Python 入门教程",
  "tags": ["Python", "编程"],
  "duration": 120,
  "play_url": "https://example.com/video.mp4",
  "cover_url": "https://example.com/cover.jpg",
  "language": "zh-CN",
  "status": "online",
  "video_type": "short",
  "author_id": "uuid",
  "author_nickname": "张三",
  "author_avatar": "https://example.com/avatar.jpg",
  "like_count": 50,
  "comment_count": 20,
  "favorite_count": 30,
  "is_liked": false,
  "is_favorited": false,
  "last_position": 0,
  "created_at": "2025-01-01T00:00:00+00:00"
}
```

`last_position` 仅此接口返回。登录用户访问时，若无该视频的学习记录会自动创建一条（状态 `not_started`），`last_position` 回填上次播放位置。

---

## 四、用户互动（Content 服务 :8002 · Interaction）

路由前缀 `/api/interaction`。点赞、收藏通过请求体传 `video_id`，为切换语义（重复调用即撤销）。

### 4.1 点赞 / 取消点赞

`POST /api/interaction/like` ｜ 强制鉴权

请求体 `{ "video_id": "uuid" }`。视频需存在且 `status=online`，否则 404（`message="视频不存在"`）。

响应 `data`：

```json
{ "success": true, "like_count": 51, "is_liked": true }
```

### 4.2 收藏 / 取消收藏

`POST /api/interaction/favorite` ｜ 强制鉴权

请求体 `{ "video_id": "uuid" }`。校验同 4.1。响应 `data`：

```json
{ "success": true, "favorite_count": 31, "is_favorited": true }
```

### 4.3 发表评论

`POST /api/interaction/comment` ｜ 强制鉴权

请求体：

```json
{ "video_id": "uuid", "content": "讲得很好！", "parent_id": null }
```

`parent_id` 为空表示顶级评论，非空表示回复（父评论不存在返回 404，`message="父评论不存在"`）。响应 `data` 为评论对象：

```json
{
  "id": "uuid",
  "video_id": "uuid",
  "user_id": "uuid",
  "user_nickname": "张三",
  "user_avatar": "https://example.com/avatar.jpg",
  "parent_id": null,
  "content": "讲得很好！",
  "like_count": 0,
  "created_at": "2025-01-01T00:00:00+00:00",
  "replies": []
}
```

### 4.4 视频评论列表

`GET /api/interaction/video/{video_id}/comments` ｜ 可选鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页数量，默认 20 |

按创建时间倒序分页返回顶级评论，回复嵌套在各顶级评论的 `replies` 中。响应 `data`：`{ "comments": [...], "total": n, "page": p, "page_size": s }`，`total` 仅统计顶级评论。视频不存在返回 404（`message="视频不存在"`）。

### 4.5 删除评论

`DELETE /api/interaction/comment/{comment_id}` ｜ 强制鉴权

仅允许删除本人评论，否则 403（`message="无权删除此评论"`）；评论不存在返回 404（`message="评论不存在"`）。删除时级联移除其回复。响应 `data`：`{ "success": true, "message": "评论删除成功" }`。

### 4.6 我点赞的视频

`GET /api/interaction/user/likes` ｜ 强制鉴权

参数 `page`、`page_size`（默认 20）。返回当前用户点赞、且视频状态为 `approved` 的记录。响应为裸数组（不经信封，无分页元数据），每项为评论对象结构：`id` 为视频 ID，`content` 为 `"用户点赞的视频: <标题>"`，`like_count` 为该视频点赞数，`created_at` 为点赞时间。

### 4.7 我收藏的视频

`GET /api/interaction/user/favorites` ｜ 强制鉴权

参数与响应同 4.6，`content` 为 `"用户收藏的视频: <标题>"`，`created_at` 为收藏时间。

---

## 五、用户关注（Content 服务 :8002 · Follow）

路由前缀 `/api/follow`，全部强制鉴权。

### 5.1 关注用户

`POST /api/follow/{user_id}` ｜ 强制鉴权

不能关注自己（400，`message="不能关注自己"`）；目标用户不存在 404（`message="用户不存在"`）；已关注返回 400（`message="已关注该用户"`）。响应 `data`：`{ "follow_id": "uuid", "message": "关注成功" }`。

### 5.2 取消关注

`DELETE /api/follow/{user_id}` ｜ 强制鉴权

未关注该用户返回 404（`message="未关注该用户"`）。响应 `data`：`{ "message": "取消关注成功" }`。

### 5.3 关注列表

`GET /api/follow/following` ｜ 强制鉴权

参数 `page`、`page_size`（最大 50）。返回当前用户关注的用户，响应 `data`：`{ "users": [...], "total": n, "page": p, "page_size": s }`，每项含 `id`、`follower_id`、`following_id`、`follower_nickname`、`follower_avatar`、`following_nickname`、`following_avatar`、`created_at`。

### 5.4 粉丝列表

`GET /api/follow/followers` ｜ 强制鉴权

参数与响应结构同 5.3，返回关注当前用户的用户。

### 5.5 关注状态

`GET /api/follow/{user_id}/status` ｜ 强制鉴权

响应 `data`：`{ "user_id": "uuid", "is_following": true }`。

---

## 六、学习进度（Content 服务 :8002 · Learn）

路由前缀 `/api/learn`，全部强制鉴权。

### 6.1 学习心跳上报

`POST /api/learn/heartbeat` ｜ 强制鉴权

请求体：

```json
{ "video_id": "uuid", "position": 60, "duration": 120 }
```

`position` 为当前播放位置（秒），`duration` 为视频总时长（秒）。视频需 `status=online`，否则 404（`message="视频不存在"`）。记录不存在时自动创建。进度按 `min(position / duration * 100, 100)` 计算，达 90% 及以上自动置为 `completed`，否则 `in_progress`。

响应 `data`：

```json
{ "video_id": "uuid", "progress": 50.0, "status": "in_progress", "last_position": 60 }
```

成功 `message="学习进度已更新"`。

### 6.2 完成学习

`POST /api/learn/complete` ｜ 强制鉴权

请求体：

```json
{ "video_id": "uuid", "completion_rate": 100.0 }
```

`completion_rate` 为完成率百分比，缺省按 100.0。视频需 `status=online`，否则 404（`message="视频不存在"`）。记录不存在时自动创建。响应 `data`：`{ "video_id": "uuid", "status": "completed", "progress": 100.0, "completed_at": "..." }`，成功 `message="学习已完成"`。

### 6.3 学习记录

`GET /api/learn/records` ｜ 强制鉴权

按最近观看时间倒序返回当前用户全部学习记录，不分页。响应 `data`：

```json
{
  "records": [
    {
      "id": "uuid",
      "video_id": "uuid",
      "title": "Python快速入门",
      "cover": "https://example.com/cover.jpg",
      "status": "completed",
      "progress": 100.0,
      "last_watch_time": "2025-01-01T00:15:00+00:00"
    }
  ],
  "total": 1
}
```

学习记录 `status` 取 `not_started` / `in_progress` / `completed`。成功 `message="获取学习记录成功"`。

---

## 七、视频上传（Upload 服务 :8003）

路由前缀 `/api/upload`。上传任务状态流转：`initialized` → `uploading`（收到首个分片）→ `uploaded`（合并完成）。完成上传时创建视频记录，初始状态 `transcoding`（上传任务本身无 `transcoding` 状态）。

### 7.1 初始化上传任务

`POST /api/upload/init` ｜ 强制鉴权

请求体：

```json
{
  "file_name": "video.mp4",
  "file_size": 104857600,
  "duration": 180,
  "mime_type": "video/mp4",
  "video_type": "short"
}
```

`video_type` 约定取 `short`（≤3 分钟）或 `long`（>3 分钟），服务端不强制校验枚举。创建上传任务（状态 `initialized`），生成 `upload_id`（形如 `UP_xxxxxxxx`）。

响应 `data`：

```json
{
  "upload_id": "UP_a1b2c3d4",
  "upload_url": "upload/chunk",
  "chunk_size": 5242880,
  "expires_in": 3600
}
```

`upload_url` 为相对路径 `upload/chunk`，前端需拼接为完整的 `PUT /api/upload/chunk`；`chunk_size` 固定 5MB，`expires_in` 固定 3600。成功 `message="上传任务初始化成功"`。

### 7.2 分片上传

`PUT /api/upload/chunk` ｜ 强制鉴权

分片索引与任务标识通过请求头传递：

| 请求头 | 说明 |
|--------|------|
| upload_id | 7.1 返回的上传任务 ID |
| chunk_index | 分片索引，从 0 开始的整数 |

请求体为分片二进制内容。缺失请求头返回 400（`message="缺少必要参数"`）；`chunk_index` 非整数返回 400（`message="chunk_index必须是整数"`）；任务不存在返回 404（`message="上传任务不存在"`）；任务状态非 `initialized`/`uploading` 返回 400（`message="上传任务状态不正确"`）。首个分片会把任务状态推进为 `uploading`。

响应 `data`：`{ "chunk_index": 0, "chunk_size": 5242880, "uploaded": true }`，成功 `message="分片上传成功"`。

### 7.3 完成上传并发起转码

`POST /api/upload/complete` ｜ 强制鉴权

请求体：

```json
{
  "upload_id": "UP_a1b2c3d4",
  "title": "Python快速入门",
  "description": "这是一个Python入门教程",
  "tags": ["Python", "编程"],
  "language": "zh-CN",
  "is_public": true
}
```

除 `upload_id` 外字段可选，`language` 默认 `zh-CN`、`is_public` 默认 `true`（`is_public` 不落库）。任务不存在返回 404（`message="上传任务不存在"`）；状态非 `uploading`/`uploaded` 返回 400（`message="上传任务状态不正确，请先完成所有分片上传"`）。合并分片后创建视频记录，初始状态 `transcoding`；无分片文件时（测试模式）生成 `/test/videos/<user_id>/<upload_id>.mp4` 模拟 URL。合并失败返回 500（`message="合并分片失败: ..."`）。

短视频响应 `data`：

```json
{ "video_id": "uuid", "status": "transcoding", "file_url": "https://..." }
```

成功 `message="上传完成，转码中"`。

长视频（`video_type=long`）响应额外返回 `long_video_id`（同时创建 LongVideo 记录，`split_enabled=true`）：

```json
{ "video_id": "uuid", "status": "transcoding", "long_video_id": "uuid", "file_url": "https://..." }
```

成功 `message="上传完成，长视频已创建"`。

### 7.4 上传图片

`POST /api/upload/image` ｜ 可选鉴权

请求体 `{ "image": "data:image/png;base64,...." }`，Base64 可带 `data:` 前缀。未登录时归入默认演示用户（固定 ID `00000000-0000-0000-0000-000000000001`）。响应 `data`：`{ "url": "/uploads/avatars/<user_id>/<id>.jpg" }`（相对路径）。Base64 解码失败返回 `code=422`（`message="无效的图片数据（Base64 解码失败）"`）。成功 `message="图片上传成功"`。

---

## 八、长视频拆分（Split 服务 :8004）

路由前缀 `/api/split`。除 `POST /api/split/simple-split` 外均强制鉴权。

拆分任务状态流转：`pending` → `queued`（已投递 Celery）→ `processing` → `completed` → `confirmed`（确认发布），任一环节出错置为 `failed`。删除任务为物理删除记录，无 `cancelled` 状态。

任务对象（`data` 结构）字段：

```json
{
  "id": "uuid",
  "task_id": "split_xxxxxxxx",
  "long_video_id": "uuid",
  "user_id": "uuid",
  "split_mode": "auto",
  "auto_config": {},
  "organization_mode": "course",
  "status": "queued",
  "progress": 0.0,
  "progress_message": "任务初始化中...",
  "error_message": null,
  "created_at": "2025-01-01T00:00:00+00:00",
  "updated_at": "2025-01-01T00:00:00+00:00",
  "completed_at": null
}
```

### 8.1 分析视频（不切割）

`POST /api/split/analyze` ｜ 强制鉴权

请求体 `{ "long_video_id": "uuid" }`。ID 格式错误返回 400（`message="长视频ID格式错误"`）；长视频不存在返回 404（`message="长视频不存在"`）；非本人视频返回 403（`message="无权操作此视频"`）。定位长视频文件后调用 GLM 智能分析，返回建议知识点切分点；文件缺失时返回示例数据并置 `used_fallback=true`、`message="视频文件不存在，使用示例数据演示智能分析功能"`；分析降级或命中缓存时 `message` 分别为 `"智能分析失败，已使用简单切分"`、`"使用缓存的分析结果"`。分析异常返回 400（`message="分析失败: ..."`）。

响应 `data`：

```json
{
  "knowledge_points": [
    { "id": 1, "title": "课程介绍与目标", "start_time": 0, "end_time": 180, "duration": 180 }
  ],
  "used_fallback": true,
  "cached": false,
  "message": "视频文件不存在，使用示例数据演示智能分析功能"
}
```

### 8.2 直接切分视频

`POST /api/split/direct-split` ｜ 强制鉴权

基于已有分析结果同步执行切分（ffmpeg），跳过智能分析。请求体：

```json
{
  "long_video_id": "uuid",
  "organization_mode": "standalone",
  "knowledge_points": [
    { "id": 1, "title": "课程介绍与目标", "start_time": 0, "end_time": 180, "duration": 180 }
  ]
}
```

`organization_mode` 默认 `standalone`。长视频不存在返回 404（`message="长视频不存在"`）；非本人视频返回 403（`message="无权操作此视频"`）；切分失败返回 400（`message="切分失败: ..."`）。切分固定以 `auto` 模式建任务，逐片段生成短视频记录（状态 `published`）与缩略图。成功响应 `data`：`{ "id": "uuid", "task_id": "split_xxxxxxxx", "long_video_id": "uuid", "status": "completed", "progress": 100.0, "progress_message": "切分完成" }`。

### 8.3 创建拆分任务

`POST /api/split/tasks` ｜ 强制鉴权

请求体：

```json
{
  "long_video_id": "uuid",
  "split_mode": "auto",
  "organization_mode": "course",
  "auto_config": { "enable_smart_split": true }
}
```

`split_mode` 取 `auto`/`manual`/`scene`，`organization_mode` 取 `course`/`standalone`，`auto_config` 为可选自由结构（透传给拆分算法）。长视频不存在返回 404（`message="长视频不存在"`），非本人视频返回 403（`message="无权操作此视频"`）。创建后投递 Celery 异步处理，状态转 `queued`；投递失败置 `failed`，`error_message="任务启动失败: ..."`。响应 `data` 为任务对象。

### 8.4 拆分任务列表

`GET /api/split/tasks` ｜ 强制鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页数量，默认 20 |
| status | string | 否 | 按任务状态过滤 |

按创建时间倒序返回当前用户任务。`data` 为任务对象数组（裸数组），每项额外含 `video_id`（该长视频对应的原始视频记录 ID）。

### 8.5 拆分任务详情

`GET /api/split/tasks/{task_id}` ｜ 强制鉴权

按业务 `task_id` 查询，越权或不存在返回 404（`message="任务不存在或无权访问"`）。响应 `data` 为任务对象。用于轮询处理进度（`status`、`progress`、`progress_message`）。

### 8.6 获取拆分段列表

`GET /api/split/tasks/{task_id}/segments` ｜ 强制鉴权

响应 `data` 为片段对象数组（裸数组），每项：

```json
{
  "id": "uuid",
  "segment_index": 0,
  "start_time": 0,
  "end_time": 180,
  "duration": 180,
  "thumbnail_url": "/smart_split_output/.../seg_0.jpg",
  "scene_type": "auto",
  "confidence": 0.95,
  "video_id": "uuid",
  "created_at": "2025-01-01T00:00:00+00:00"
}
```

`scene_type` 为文本标记（`auto`、`manual` 或知识点标题等），`video_id` 在确认后回填。

### 8.7 获取完整拆分结果

`GET /api/split/tasks/{task_id}/result` ｜ 强制鉴权

响应 `data`：`{ "task": {任务对象}, "segments": [片段对象, ...] }`。此接口片段额外附带 `video_url`（相对路径，供播放）。

### 8.8 调整拆分点

`PUT /api/split/tasks/{task_id}/segments` ｜ 强制鉴权

仅更新既有片段的时间点，按片段 `id` 定位（`segment_index` 与增删操作在此接口不接受）。请求体：

```json
{
  "segments": [
    { "segment_id": "uuid", "start_time": 0, "end_time": 130, "scene_type": "manual" }
  ]
}
```

任务状态需为 `completed` 或 `pending`，否则 400（`message="任务状态不允许调整拆分点"`）；片段不存在返回 404（`message="拆分片段 {segment_id} 不存在"`）。开始时间需 `≥ 0` 且 `<` 原视频总时长，结束时间需 `> 0` 且 `≤` 总时长，越界返回 400（`message="开始时间 {value} 超出有效范围"` / `"结束时间 {value} 超出有效范围"`）。调整后重算时长并标记 `scene_type=manual`，随后校验全片段时间递增、无重叠（`message="片段 {index} 的开始时间必须小于结束时间"` / `"片段 {index} 与前一片段时间重叠"`）。响应 `data`：`{ "task": {任务对象}, "segments": [片段对象数组] }`。

### 8.9 确认拆分结果

`POST /api/split/tasks/{task_id}/confirm` ｜ 强制鉴权

请求体为裸的片段 ID 字符串数组（无字段名、不经信封）：

```json
["<segment_id>", "<segment_id>"]
```

错误经 `HTTPException` 直接抛出（`{"detail": ...}`）：任务不存在或越权 404（`"任务不存在或无权访问"`）；任务状态非 `completed` 400（`"任务尚未完成"`）；长视频不存在 404（`"长视频不存在"`）；无匹配片段 400（`"未选择任何片段"`）。为选中片段创建短视频记录（`status=online`、`video_type=short`、`parent_video_id` 指向对应 LongVideo 记录，标题 `{task_id}_segment_{index}`），并回填片段 `video_id`，任务状态转 `confirmed`。响应为裸对象 `{ "task": {...}, "segments": [...] }`（不经信封）。

### 8.10 删除拆分任务

`DELETE /api/split/tasks/{task_id}` ｜ 强制鉴权

删除任务及其关联片段记录，不存在或越权返回 404（`message="任务不存在或无权操作"`）。响应 `data`：`{ "message": "任务删除成功" }`。

### 8.11 简化视频分割（演示）

`POST /api/split/simple-split` ｜ 免鉴权

参数以查询串传递：`video_id`（必填）、`threshold`（可选，默认 0.15）。视频不存在返回 404（`message="视频不存在"`）。固定归属演示用户，直接标记任务 `completed` 并生成 5 个 60 秒示例片段。返回裸对象（不经信封）：

```json
{
  "task_id": "split_xxxxxxxx",
  "segments": [
    { "id": "uuid", "segment_index": 0, "start_time": 0, "end_time": 60, "duration": 60 }
  ],
  "message": "分割完成"
}
```

### 8.12 发布片段到主页

`POST /api/split/publish-segments` ｜ 强制鉴权

请求体 `{ "segment_ids": ["uuid", "uuid"] }`。空列表返回 400（`message="请选择至少一个片段"`）；片段不存在返回 404（`message="未找到指定的片段"`）；越权返回 403（`message="无权操作这些片段"`）。将所选片段对应视频解除父子关系（`parent_video_id=null`）、置 `video_type=short` 与 `status=published`，使其出现在主页，并失效相关推荐缓存。响应 `data`：`{ "published_count": 2, "message": "成功发布 2 个片段到主页" }`。

---

## 九、课程管理（Course 服务 :8005）

路由前缀 `/api/courses`，全部强制鉴权。写操作（增删视频、更新、排序）仅课程作者可执行，否则 403（`message="无权操作此课程"`）。

### 9.1 创建课程

`POST /api/courses` ｜ 强制鉴权

请求体：

```json
{
  "title": "Python基础课程",
  "description": "完整的Python基础教程",
  "tags": ["Python", "编程", "基础"],
  "language": "zh-CN",
  "cover_url": "https://example.com/course_cover.jpg",
  "is_public": true
}
```

仅 `title` 必填，`language` 默认 `zh-CN`、`is_public` 默认 `true`。`is_public=true` 时课程状态置 `pending`，否则 `draft`。响应 `data`：`{ "course_id": "course_xxxxxxxx", "title": "...", "status": "pending", "created_at": "..." }`，成功 `message="课程创建成功"`。

### 9.2 课程详情

`GET /api/courses/{course_id}` ｜ 强制鉴权

按业务 `course_id` 查询，不存在返回 404（`message="课程不存在"`）。响应 `data`：

```json
{
  "course_id": "course_xxxxxxxx",
  "title": "Python基础课程",
  "description": "完整的Python基础教程",
  "tags": ["Python", "编程"],
  "language": "zh-CN",
  "cover_url": "https://example.com/course_cover.jpg",
  "author": { "id": "uuid", "nickname": "张三", "avatar": "https://example.com/avatar.jpg" },
  "status": "online",
  "total_videos": 10,
  "total_duration": 1200,
  "stats": { "play_count": 5000, "like_count": 200, "favorite_count": 150, "student_count": 300 },
  "videos": [
    { "video_id": "uuid", "segment_index": 0, "title": "第1节", "duration": 130, "cover_url": "...", "play_url": "...", "status": "online" }
  ],
  "created_at": "2025-01-01T00:00:00+00:00",
  "updated_at": "2025-01-01T00:15:00+00:00"
}
```

`videos` 按 `segment_index` 升序；`stats` 基于课程内视频聚合（`play_count` 取 Redis 播放计数，`student_count` 为课程内视频的去重学习人数）。

### 9.3 添加视频到课程

`POST /api/courses/{course_id}/videos` ｜ 强制鉴权（作者）

请求体：

```json
{ "video_ids": ["uuid1", "uuid2"], "segment_indexes": [0, 1] }
```

`segment_indexes` 可选，与 `video_ids` 按下标对应指定顺序；缺省时接在现有最大序号后追加。已在课程中的视频跳过。任一视频不存在返回 400（`message="部分视频不存在"`）。响应 `data`：`{ "course_id": "...", "added_count": 2, "total_videos": 12 }`，成功 `message="视频已添加到课程"`。

### 9.4 从课程移除视频

`DELETE /api/courses/{course_id}/videos/{video_id}` ｜ 强制鉴权（作者）

视频不在课程中返回 404（`message="视频不在课程中"`）。响应 `data`：`{ "course_id": "...", "video_id": "...", "total_videos": 11 }`，成功 `message="视频已从课程中移除"`。

### 9.5 更新课程信息

`PUT /api/courses/{course_id}` ｜ 强制鉴权（作者）

请求体（字段均可选，仅更新传入字段；`language`、`is_public` 不可更新）：

```json
{ "title": "...", "description": "...", "tags": ["..."], "cover_url": "..." }
```

响应 `data`：`{ "course_id": "...", "updated_at": "..." }`，`message="课程信息已更新"`。

### 9.6 课程列表

`GET /api/courses` ｜ 强制鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| author_id | string | 否 | 按作者过滤 |
| tags | string | 否 | 标签过滤，逗号分隔，命中任一即保留 |
| status | string | 否 | 按状态过滤 |
| sort_by | string | 否 | `latest`/`hot`/`students`，默认 `latest` |
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量，最大 100 |

`hot`、`students` 目前按 `total_videos` 降序近似排序。响应 `data`：`{ "items": [...], "pagination": { "page", "page_size", "total", "has_more" } }`，`items` 项含 `course_id`、`title`、`cover_url`、`author`（`id`、`nickname`）、`total_videos`、`total_duration`、`stats`、`status`、`created_at`（列表中 `stats` 的 `play_count`、`student_count` 为占位 0）。

### 9.7 调整课程视频顺序

`PUT /api/courses/{course_id}/videos/order` ｜ 强制鉴权（作者）

请求体：

```json
{ "video_orders": [ { "video_id": "uuid", "segment_index": 0 } ] }
```

按 `video_id` 更新对应关联记录的 `segment_index`，未匹配的条目静默跳过。响应 `data`：`{ "course_id": "...", "updated_at": "..." }`，`message="视频顺序已更新"`。

---

## 十、搜索（Search 服务 :8006）

路由前缀 `/api/search`，全部强制鉴权。

### 10.1 搜索建议

`GET /api/search/suggest` ｜ 强制鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | 是 | 关键词前缀，长度 1–100 |
| limit | integer | 否 | 返回数量，默认 10，范围 1–20 |

从在线视频的标题与标签中提取建议词。`history` 字段恒返回空数组（搜索历史功能未启用）。响应 `data`：`{ "suggestions": ["Python", "Python教程"], "history": [] }`。

### 10.2 视频搜索

`GET /api/search/videos` ｜ 强制鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | 否 | 关键字，匹配标题或简介 |
| tags | string | 否 | 标签列表，逗号分隔，须全部包含 |
| duration_range | string | 否 | 时长区间，如 `060`（0–60 秒）、`60180`（60–180 秒） |
| language | string | 否 | 语言 |
| sort_by | string | 否 | `latest`/`hot`/`relevance`，默认 `latest` |
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量，最大 50 |

仅检索 `online` 短视频，`q` 中字面量转义 `%`/`_`/`\`。`hot` 按互动总量（点赞+收藏+评论）降序，`latest`、`relevance` 按创建时间倒序。响应 `data`：`{ "items": [...], "pagination": { "page", "page_size", "total", "has_more" } }`，`items` 项：

```json
{
  "video_id": "uuid",
  "title": "Python快速入门",
  "cover_url": "https://example.com/cover.jpg",
  "duration": 120,
  "author": { "id": "uuid", "nickname": "张三", "avatar": "https://example.com/avatar.jpg" },
  "hot_score": 95.5,
  "stats": { "play_count": 1000, "like_count": 50, "comment_count": 20 }
}
```

`hot_score` =（播放×0.3 + 点赞×0.3 + 评论×0.2 + 收藏×0.2）× 时间衰减，保留两位小数。时间衰减系数按视频年龄：≤24 小时 1.5、≤48 小时 1.2、≤72 小时 1.0、≤7 天 0.8、≤30 天 0.5、更久 0.3。

---

## 十一、消息通知（Notification 服务 :8007）

路由前缀 `/api/inbox`，全部强制鉴权。

### 11.1 消息列表

`GET /api/inbox/messages` ｜ 强制鉴权

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 否 | 消息类型：`comment_reply`/`audit_result`/`system`/`split_completed` |
| is_read | boolean | 否 | 按已读/未读过滤 |
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量，最大 100 |

未读优先、再按时间倒序。响应 `data`：`{ "items": [...], "pagination": { "page", "page_size", "total", "has_more" } }`，`items` 项：`{ "id", "type", "title", "content", "is_read", "related_id", "created_at" }`。

### 11.2 标记消息已读

`POST /api/inbox/read` ｜ 强制鉴权

请求体：

```json
{ "message_ids": ["uuid1", "uuid2"] }
```

`message_ids` 省略或为空时标记当前用户全部未读消息为已读。响应 `data`：`{ "updated_count": 2 }`，成功 `message="消息已标记为已读"`。

---

## 十二、典型调用流程

### 12.1 长视频上传并拆分发布

```javascript
// 1. 初始化上传（长视频）
const init = await fetch('/api/upload/init', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({
    file_name: 'long_video.mp4', file_size: 1048576000,
    duration: 1800, mime_type: 'video/mp4', video_type: 'long'
  })
}).then(r => r.json());
const { upload_id } = init.data;

// 2. 分片上传（参数走请求头）
await fetch('/api/upload/chunk', {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'upload_id': upload_id,
    'chunk_index': 0
  },
  body: chunkBlob
});

// 3. 完成上传，返回长视频ID
const complete = await fetch('/api/upload/complete', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ upload_id, title: 'Python完整教程', tags: ['Python'] })
}).then(r => r.json());
const { long_video_id } = complete.data;

// 4. 分析（可选，得到建议切分点后用户可调整）
const analyze = await fetch('/api/split/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ long_video_id })
}).then(r => r.json());
const points = analyze.data.knowledge_points;

// 5a. 直接切分（同步完成）
await fetch('/api/split/direct-split', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ long_video_id, organization_mode: 'standalone', knowledge_points: points })
});

// 5b. 或走异步任务：创建任务后轮询详情，完成后确认
const task = await fetch('/api/split/tasks', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ long_video_id, split_mode: 'auto', organization_mode: 'course', auto_config: {} })
}).then(r => r.json());
const taskId = task.data.task_id;

const poll = async () => {
  const t = await fetch(`/api/split/tasks/${taskId}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  }).then(r => r.json());
  if (t.data.status === 'completed') {
    const segs = await fetch(`/api/split/tasks/${taskId}/segments`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json());
    // 确认：请求体为裸片段ID数组
    await fetch(`/api/split/tasks/${taskId}/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify(segs.data.map(s => s.id))
    });
  } else if (t.data.status === 'processing' || t.data.status === 'queued') {
    setTimeout(poll, 5000);
  }
};
poll();
```

---

## 十三、附录

### 13.1 视频类型

- `short`：短视频（时长 ≤ 3 分钟）
- `long`：长视频（时长 > 3 分钟）

### 13.2 视频状态（`videos.status`）

默认 `pending`。应用层写入的取值：`pending`、`transcoding`、`online`、`published`。`approved` 无写入路径，仅用于"我点赞/收藏"列表的过滤。各读接口可见范围：推荐流（`recommend`/`diverse`/`personalized`）返回 `online` 与 `published`；关注流、热门、Feed 搜索、视频详情仅返回 `online`；`my_videos` 返回本人全部状态。

### 13.3 上传任务状态（`upload_tasks.status`）

`initialized` → `uploading` → `uploaded`。完成上传时创建的视频记录以 `transcoding` 状态入库。

### 13.4 学习记录状态（`learn_records.status`）

`not_started`、`in_progress`、`completed`。

### 13.5 拆分模式（`split_tasks.split_mode`）

- `auto`：自动拆分
- `manual`：手动指定
- `scene`：场景拆分

### 13.6 组织模式（`split_tasks.organization_mode`）

- `course`：组织成课程
- `standalone`：独立视频

### 13.7 拆分任务状态（`split_tasks.status`）

`pending`、`queued`、`processing`、`completed`、`confirmed`、`failed`。删除任务为物理删除，无 `cancelled` 状态。

### 13.8 消息类型（`notifications.type`）

`comment_reply`、`audit_result`、`system`、`split_completed`。

### 13.9 错误响应形态

**统一信封型**（多数端点，经 `error_response`）：

```json
{ "code": 404, "message": "视频不存在", "data": null }
```

**参数校验失败**（Pydantic 校验不通过，`code=422`）：Auth 与 Content 服务返回信封形态，`data.errors` 为 `"字段: 原因"` 字符串数组：

```json
{
  "code": 422,
  "message": "请求参数验证失败",
  "data": { "errors": ["body.phone: String should have at least 10 characters"] }
}
```

其余服务（Upload、Split、Course、Search、Notification）无全局校验异常处理器，返回 FastAPI 默认形态 `{"detail": [...]}`。

**`HTTPException` 直抛**（`{"detail": "..."}`）：Content 服务的 `get_current_user` 鉴权失败（401/403/404）与 `POST /api/feed/feedback` 的视频不存在 404；Split 服务 `POST /api/split/tasks/{task_id}/confirm` 的全部错误。Auth 服务对 `HTTPException` 做了全局包装，统一为信封形态。
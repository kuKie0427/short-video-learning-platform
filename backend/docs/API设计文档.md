# 短视频学习平台 - API接口设计文档

## 一、接口设计规范

### 1.1 基础规范

- **调用协议**：HTTPS + RESTful风格
- **数据格式**：请求与响应统一使用JSON
- **字符编码**：UTF-8
- **鉴权方式**：基于JWT Token，在请求头中附带 `Authorization: Bearer <token>`

### 1.2 状态码规范

| 状态码 | 说明 | 示例场景 |
|--------|------|----------|
| 200 | 请求成功 | 查询、更新操作成功 |
| 201 | 创建成功 | 资源创建成功 |
| 400 | 客户端错误 | 参数错误、格式不正确 |
| 401 | 未授权 | Token无效或过期 |
| 403 | 无权限 | 权限不足 |
| 404 | 资源不存在 | 请求的资源未找到 |
| 409 | 资源冲突 | 资源已存在 |
| 500 | 服务器错误 | 服务器内部错误 |
| 503 | 服务不可用 | 服务暂时不可用 |

### 1.3 统一响应格式

#### 成功响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    // 具体数据
  }
}
```

#### 错误响应
```json
{
  "code": 400,
  "message": "错误描述",
  "error_code": "ERROR_CODE",
  "data": null
}
```

### 1.4 分页参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| page | integer | 否 | 页码，从1开始，默认1 |
| page_size | integer | 否 | 每页数量，默认20，最大100 |

#### 分页响应格式
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5,
      "has_more": true
    }
  }
}
```

---

## 二、账号与身份相关接口

### 2.1 发送验证码

**接口地址**：`POST /api/auth/send_code`

**请求参数**：
```json
{
  "phone": "13800138000",
  "scene": "register"  // register: 注册, login: 登录
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "验证码已发送",
  "data": {
    "success": true,
    "expires_in": 300  // 过期时间（秒）
  }
}
```

### 2.2 手机号验证码登录

**接口地址**：`POST /api/auth/login_by_phone`

**请求参数**：
```json
{
  "phone": "13800138000",
  "code": "123456"
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "U001",
      "phone": "13800138000",
      "nickname": "张三",
      "avatar": "https://example.com/avatar.jpg",
      "roles": ["learner", "creator"]
    }
  }
}
```

### 2.3 获取当前用户信息

**接口地址**：`GET /api/user/me`

**请求头**：`Authorization: Bearer <token>`

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "U001",
    "phone": "13800138000",
    "nickname": "张三",
    "avatar": "https://example.com/avatar.jpg",
    "bio": "学习爱好者",
    "language": "zh-CN",
    "roles": ["learner", "creator"],
    "created_at": "2025-01-01T00:00:00Z"
  }
}
```

---

## 三、内容与推荐相关接口

### 3.1 首页推荐Feed

**接口地址**：`GET /api/feed/recommend`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |
| tags | string | 否 | 标签筛选（逗号分隔） |

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "video_id": "V001",
        "title": "Python快速入门",
        "cover_url": "https://example.com/cover.jpg",
        "duration": 120,
        "author": {
          "id": "U001",
          "nickname": "张三",
          "avatar": "https://example.com/avatar.jpg"
        },
        "hot_score": 95.5,
        "stats": {
          "play_count": 1000,
          "like_count": 50,
          "comment_count": 20
        }
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "has_more": true
    }
  }
}
```

### 3.2 视频详情

**接口地址**：`GET /api/video/{video_id}`

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "video_id": "V001",
    "title": "Python快速入门",
    "description": "这是一个Python入门教程",
    "tags": ["Python", "编程"],
    "duration": 120,
    "play_url": "https://example.com/video.m3u8",
    "cover_url": "https://example.com/cover.jpg",
    "language": "zh-CN",
    "author_info": {
      "id": "U001",
      "nickname": "张三",
      "avatar": "https://example.com/avatar.jpg"
    },
    "stats": {
      "play_count": 1000,
      "like_count": 50,
      "comment_count": 20,
      "favorite_count": 30
    },
    "user_learn_status": {
      "status": "not_started",  // not_started/learned/review_needed
      "last_position": 0,
      "completed_ratio": 0.0
    },
    "course_info": {  // 如果属于课程
      "course_id": "C001",
      "course_title": "Python基础课程",
      "segment_index": 1,
      "total_segments": 10
    }
  }
}
```

### 3.3 推荐关联视频列表

**接口地址**：`GET /api/video/{video_id}/related`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| limit | integer | 否 | 返回数量，默认10 |

**响应参数**：同首页推荐Feed格式

---

## 四、搜索与筛选接口

### 4.1 搜索建议

**接口地址**：`GET /api/search/suggest`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| q | string | 是 | 搜索关键词前缀 |

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "suggestions": [
      "Python",
      "Python教程",
      "Python基础"
    ],
    "history": [
      "算法",
      "数据结构"
    ]
  }
}
```

### 4.2 视频搜索

**接口地址**：`GET /api/search/videos`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| q | string | 否 | 关键字 |
| tags | string | 否 | 标签列表（逗号分隔） |
| duration_range | string | 否 | 时长范围，如"060"（0-60秒）、"60180"（60-180秒） |
| language | string | 否 | 语言 |
| sort_by | string | 否 | 排序方式：latest/hot/relevance |
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |

**响应参数**：同首页推荐Feed格式

---

## 五、视频播放与学习进度接口

### 5.1 学习心跳上报

**接口地址**：`POST /api/learn/heartbeat`

**请求参数**：
```json
{
  "video_id": "V001",
  "position": 60,  // 当前播放位置（秒）
  "buffered": 120,  // 已缓冲时长（秒）
  "playing": true  // 是否正在播放
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "success": true
  }
}
```

### 5.2 学习完成标记

**接口地址**：`POST /api/learn/complete`

**请求参数**：
```json
{
  "video_id": "V001",
  "status": "learned"  // learned: 已学, review_needed: 需复习
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "success": true
  }
}
```

---

## 六、互动接口（点赞/评论/收藏）

### 6.1 点赞

**接口地址**：`POST /api/video/{video_id}/like`

**请求参数**：
```json
{
  "action": "like"  // like: 点赞, unlike: 取消点赞
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "liked": true,
    "like_count": 51
  }
}
```

### 6.2 评论列表

**接口地址**：`GET /api/video/{video_id}/comments`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "C001",
        "content": "讲得很好！",
        "user": {
          "id": "U002",
          "nickname": "李四",
          "avatar": "https://example.com/avatar.jpg"
        },
        "like_count": 15,
        "created_at": "2025-01-01T00:00:00Z",
        "replies": [
          {
            "id": "C002",
            "content": "谢谢！",
            "user": {
              "id": "U001",
              "nickname": "张三"
            },
            "created_at": "2025-01-01T00:05:00Z"
          }
        ]
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 50,
      "has_more": true
    }
  }
}
```

### 6.3 收藏

**接口地址**：`POST /api/video/{video_id}/favorite`

**请求参数**：
```json
{
  "action": "add"  // add: 收藏, remove: 取消收藏
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "favorited": true,
    "favorite_count": 31
  }
}
```

---

## 七、上传与审核相关接口

### 7.1 初始化上传任务

**接口地址**：`POST /api/upload/init`

**请求参数**：
```json
{
  "file_name": "video.mp4",
  "file_size": 104857600,  // 文件大小（字节）
  "duration": 180,  // 视频时长（秒）
  "mime_type": "video/mp4",
  "video_type": "short"  // short: 短视频(≤3min), long: 长视频(>3min)
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "upload_id": "UP001",
    "upload_url": "https://s3.example.com/upload",
    "chunk_size": 5242880,  // 分片大小（字节）
    "expires_in": 3600  // 上传URL过期时间（秒）
  }
}
```

### 7.2 分片上传

**接口地址**：`PUT {upload_url}`

**请求头**：
- `Content-Type: application/octet-stream`
- `Authorization: Bearer <token>`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| upload_id | string | 是 | 上传任务ID |
| chunk_index | integer | 是 | 分片索引（从0开始） |

**请求体**：二进制数据（分片内容）

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "chunk_index": 0,
    "uploaded": true
  }
}
```

### 7.3 完成上传并发起转码

**接口地址**：`POST /api/upload/complete`

**请求参数**：
```json
{
  "upload_id": "UP001",
  "title": "Python快速入门",
  "description": "这是一个Python入门教程",
  "tags": ["Python", "编程"],
  "language": "zh-CN",
  "is_public": true
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "video_id": "V001",
    "status": "transcoding",  // uploading/uploaded/transcoding/pending/online/rejected
    "long_video_id": "LV001"  // 如果是长视频，返回长视频ID
  }
}
```

### 7.4 查询审核状态

**接口地址**：`GET /api/video/{video_id}/status`

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "video_id": "V001",
    "status": "pending",  // pending/online/rejected
    "reject_reason": null,  // 如果被驳回，返回原因
    "audit_time": null  // 审核时间
  }
}
```

---

## 八、长视频拆分相关接口

### 8.1 创建拆分任务

**接口地址**：`POST /api/split/tasks`

**请求参数**：
```json
{
  "long_video_id": "LV001",
  "split_mode": "hybrid",  // auto: 自动, manual: 手动, hybrid: 混合
  "auto_config": {  // 自动拆分配置（split_mode为auto或hybrid时必填）
    "method": "scene_detection",  // scene_detection: 场景检测, fixed_duration: 固定时长
    "min_segment_duration": 60,  // 最小片段时长（秒）
    "max_segment_duration": 180,  // 最大片段时长（秒）
    "fixed_duration": null  // 固定时长拆分时的时长（秒），method为fixed_duration时必填
  },
  "organization_mode": "course",  // course: 组织成课程, independent: 独立视频, both: 两种模式
  "course_info": {  // 组织成课程时的信息（organization_mode为course或both时必填）
    "title": "Python基础课程",
    "description": "完整的Python基础教程",
    "tags": ["Python", "编程", "基础"]
  }
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "ST001",
    "long_video_id": "LV001",
    "status": "pending",  // pending/processing/completed/failed
    "estimated_time": 300  // 预计处理时间（秒）
  }
}
```

### 8.2 查询拆分任务状态

**接口地址**：`GET /api/split/tasks/{task_id}`

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "ST001",
    "long_video_id": "LV001",
    "status": "processing",  // pending/processing/completed/failed
    "progress": 45.5,  // 处理进度（百分比）
    "split_mode": "hybrid",
    "organization_mode": "course",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:05:00Z",
    "completed_at": null,
    "error_message": null  // 如果失败，返回错误信息
  }
}
```

### 8.3 获取拆分预览（自动拆分结果）

**接口地址**：`GET /api/split/tasks/{task_id}/preview`

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "ST001",
    "segments": [
      {
        "segment_index": 0,
        "start_time": 0,  // 开始时间（秒）
        "end_time": 120,  // 结束时间（秒）
        "duration": 120,
        "thumbnail_url": "https://example.com/thumb1.jpg",  // 缩略图
        "scene_type": "scene_change",  // 拆分原因：scene_change/audio_silence/fixed_duration/manual
        "confidence": 0.95  // 置信度（0-1）
      },
      {
        "segment_index": 1,
        "start_time": 120,
        "end_time": 240,
        "duration": 120,
        "thumbnail_url": "https://example.com/thumb2.jpg",
        "scene_type": "scene_change",
        "confidence": 0.92
      }
    ],
    "total_segments": 10,
    "total_duration": 1200
  }
}
```

### 8.4 更新拆分点（手动调整）

**接口地址**：`PUT /api/split/tasks/{task_id}/segments`

**请求参数**：
```json
{
  "segments": [
    {
      "segment_index": 0,
      "start_time": 0,
      "end_time": 130,  // 调整结束时间
      "action": "update"  // update: 更新, add: 新增, delete: 删除
    },
    {
      "segment_index": 1,
      "start_time": 130,  // 新增拆分点
      "end_time": 250,
      "action": "add"
    },
    {
      "segment_index": 2,
      "action": "delete"  // 删除该片段
    }
  ]
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "ST001",
    "segments": [
      {
        "segment_index": 0,
        "start_time": 0,
        "end_time": 130,
        "duration": 130
      },
      {
        "segment_index": 1,
        "start_time": 130,
        "end_time": 250,
        "duration": 120
      }
    ],
    "total_segments": 9  // 更新后的片段总数
  }
}
```

### 8.5 执行拆分任务

**接口地址**：`POST /api/split/tasks/{task_id}/execute`

**请求参数**：
```json
{
  "confirm": true  // 确认执行拆分
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "拆分任务已提交",
  "data": {
    "task_id": "ST001",
    "status": "processing",
    "estimated_time": 600  // 预计处理时间（秒）
  }
}
```

### 8.6 查询拆分结果

**接口地址**：`GET /api/split/tasks/{task_id}/results`

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "ST001",
    "status": "completed",
    "long_video_id": "LV001",
    "organization_mode": "course",
    "course": {  // 如果组织成课程
      "course_id": "C001",
      "title": "Python基础课程",
      "description": "完整的Python基础教程",
      "total_segments": 10,
      "status": "pending"  // pending/online/rejected
    },
    "videos": [  // 拆分出的短视频列表
      {
        "video_id": "V001",
        "segment_index": 0,
        "title": "Python基础课程 - 第1节",
        "duration": 130,
        "play_url": "https://example.com/video1.m3u8",
        "cover_url": "https://example.com/cover1.jpg",
        "status": "pending"  // pending/online/rejected
      },
      {
        "video_id": "V002",
        "segment_index": 1,
        "title": "Python基础课程 - 第2节",
        "duration": 120,
        "play_url": "https://example.com/video2.m3u8",
        "cover_url": "https://example.com/cover2.jpg",
        "status": "pending"
      }
    ],
    "created_at": "2025-01-01T00:00:00Z",
    "completed_at": "2025-01-01T00:15:00Z"
  }
}
```

### 8.7 取消拆分任务

**接口地址**：`DELETE /api/split/tasks/{task_id}`

**响应参数**：
```json
{
  "code": 200,
  "message": "拆分任务已取消",
  "data": {
    "task_id": "ST001",
    "status": "cancelled"
  }
}
```

### 8.8 查询用户的拆分任务列表

**接口地址**：`GET /api/split/tasks`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| status | string | 否 | 任务状态筛选：pending/processing/completed/failed/cancelled |
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "task_id": "ST001",
        "long_video_id": "LV001",
        "long_video_title": "Python完整教程",
        "status": "completed",
        "progress": 100,
        "total_segments": 10,
        "created_at": "2025-01-01T00:00:00Z",
        "completed_at": "2025-01-01T00:15:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 5,
      "has_more": false
    }
  }
}
```

---

## 九、课程/系列管理接口

### 9.1 创建课程

**接口地址**：`POST /api/courses`

**请求参数**：
```json
{
  "title": "Python基础课程",
  "description": "完整的Python基础教程，从入门到进阶",
  "tags": ["Python", "编程", "基础"],
  "language": "zh-CN",
  "cover_url": "https://example.com/course_cover.jpg",  // 可选
  "is_public": true
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "课程创建成功",
  "data": {
    "course_id": "C001",
    "title": "Python基础课程",
    "status": "draft",  // draft/pending/online/rejected
    "created_at": "2025-01-01T00:00:00Z"
  }
}
```

### 9.2 查询课程详情

**接口地址**：`GET /api/courses/{course_id}`

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "course_id": "C001",
    "title": "Python基础课程",
    "description": "完整的Python基础教程",
    "tags": ["Python", "编程", "基础"],
    "language": "zh-CN",
    "cover_url": "https://example.com/course_cover.jpg",
    "author": {
      "id": "U001",
      "nickname": "张三",
      "avatar": "https://example.com/avatar.jpg"
    },
    "status": "online",
    "total_videos": 10,
    "total_duration": 1200,
    "stats": {
      "play_count": 5000,
      "like_count": 200,
      "favorite_count": 150,
      "student_count": 300  // 学习人数
    },
    "videos": [
      {
        "video_id": "V001",
        "segment_index": 0,
        "title": "Python基础课程 - 第1节",
        "duration": 130,
        "cover_url": "https://example.com/cover1.jpg",
        "play_url": "https://example.com/video1.m3u8",
        "status": "online"
      }
    ],
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:15:00Z"
  }
}
```

### 9.3 添加视频到课程

**接口地址**：`POST /api/courses/{course_id}/videos`

**请求参数**：
```json
{
  "video_ids": ["V001", "V002", "V003"],
  "segment_indexes": [0, 1, 2]  // 可选，指定视频在课程中的顺序
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "视频已添加到课程",
  "data": {
    "course_id": "C001",
    "added_count": 3,
    "total_videos": 13
  }
}
```

### 9.4 从课程中移除视频

**接口地址**：`DELETE /api/courses/{course_id}/videos/{video_id}`

**响应参数**：
```json
{
  "code": 200,
  "message": "视频已从课程中移除",
  "data": {
    "course_id": "C001",
    "video_id": "V001",
    "total_videos": 12
  }
}
```

### 9.5 更新课程信息

**接口地址**：`PUT /api/courses/{course_id}`

**请求参数**：
```json
{
  "title": "Python基础课程（更新版）",
  "description": "更新的课程描述",
  "tags": ["Python", "编程", "基础", "进阶"],
  "cover_url": "https://example.com/new_cover.jpg"
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "课程信息已更新",
  "data": {
    "course_id": "C001",
    "updated_at": "2025-01-01T01:00:00Z"
  }
}
```

### 9.6 查询课程列表

**接口地址**：`GET /api/courses`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| author_id | string | 否 | 作者ID |
| tags | string | 否 | 标签筛选（逗号分隔） |
| status | string | 否 | 状态筛选：draft/pending/online/rejected |
| sort_by | string | 否 | 排序：latest/hot/students |
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "course_id": "C001",
        "title": "Python基础课程",
        "cover_url": "https://example.com/course_cover.jpg",
        "author": {
          "id": "U001",
          "nickname": "张三"
        },
        "total_videos": 10,
        "total_duration": 1200,
        "stats": {
          "play_count": 5000,
          "student_count": 300
        },
        "status": "online",
        "created_at": "2025-01-01T00:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 50,
      "has_more": true
    }
  }
}
```

### 9.7 调整课程视频顺序

**接口地址**：`PUT /api/courses/{course_id}/videos/order`

**请求参数**：
```json
{
  "video_orders": [
    {
      "video_id": "V003",
      "segment_index": 0
    },
    {
      "video_id": "V001",
      "segment_index": 1
    },
    {
      "video_id": "V002",
      "segment_index": 2
    }
  ]
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "视频顺序已更新",
  "data": {
    "course_id": "C001",
    "updated_at": "2025-01-01T01:00:00Z"
  }
}
```

---

## 十、消息与通知接口

### 10.1 获取消息列表

**接口地址**：`GET /api/inbox/messages`

**请求参数**（Query）：
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| type | string | 否 | 消息类型：comment_reply/audit_result/system/split_completed |
| is_read | boolean | 否 | 是否已读 |
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页数量 |

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "N001",
        "type": "split_completed",
        "title": "拆分任务完成",
        "content": "您的长视频拆分任务已完成，共生成10个短视频",
        "is_read": false,
        "related_id": "ST001",  // 关联的拆分任务ID
        "created_at": "2025-01-01T00:15:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 10,
      "has_more": false
    }
  }
}
```

### 10.2 标记消息已读

**接口地址**：`POST /api/inbox/read`

**请求参数**：
```json
{
  "message_ids": ["N001", "N002"]  // 消息ID列表，为空则标记全部为已读
}
```

**响应参数**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "updated_count": 2
  }
}
```

---

## 十一、错误码定义

### 11.1 通用错误码

| 错误码 | HTTP状态码 | 说明 |
|--------|-----------|------|
| SUCCESS | 200 | 成功 |
| INVALID_PARAMETER | 400 | 参数错误 |
| UNAUTHORIZED | 401 | 未授权 |
| FORBIDDEN | 403 | 无权限 |
| NOT_FOUND | 404 | 资源不存在 |
| CONFLICT | 409 | 资源冲突 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |
| SERVICE_UNAVAILABLE | 503 | 服务不可用 |

### 11.2 业务错误码

| 错误码 | HTTP状态码 | 说明 |
|--------|-----------|------|
| VIDEO_DURATION_EXCEEDED | 400 | 视频时长超限 |
| VIDEO_TYPE_MISMATCH | 400 | 视频类型不匹配 |
| SPLIT_TASK_NOT_FOUND | 404 | 拆分任务不存在 |
| SPLIT_TASK_ALREADY_COMPLETED | 409 | 拆分任务已完成 |
| SPLIT_TASK_CANNOT_CANCEL | 400 | 拆分任务无法取消（已开始处理） |
| COURSE_NOT_FOUND | 404 | 课程不存在 |
| COURSE_VIDEO_ALREADY_EXISTS | 409 | 视频已在课程中 |
| UPLOAD_TASK_NOT_FOUND | 404 | 上传任务不存在 |
| UPLOAD_TASK_EXPIRED | 400 | 上传任务已过期 |

---

## 十二、接口调用示例

### 12.1 长视频上传并拆分完整流程

```javascript
// 1. 初始化上传（长视频）
const initResponse = await fetch('/api/upload/init', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    file_name: 'long_video.mp4',
    file_size: 1048576000,
    duration: 1800,  // 30分钟
    mime_type: 'video/mp4',
    video_type: 'long'  // 标识为长视频
  })
});

const { upload_id, upload_url, chunk_size } = initResponse.data;

// 2. 分片上传
// ... 分片上传逻辑 ...

// 3. 完成上传
const completeResponse = await fetch('/api/upload/complete', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    upload_id: upload_id,
    title: 'Python完整教程',
    description: '30分钟Python完整教程',
    tags: ['Python', '编程'],
    language: 'zh-CN',
    is_public: true
  })
});

const { long_video_id } = completeResponse.data;

// 4. 创建拆分任务
const splitTaskResponse = await fetch('/api/split/tasks', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    long_video_id: long_video_id,
    split_mode: 'hybrid',
    auto_config: {
      method: 'scene_detection',
      min_segment_duration: 60,
      max_segment_duration: 180
    },
    organization_mode: 'course',
    course_info: {
      title: 'Python基础课程',
      description: '完整的Python基础教程',
      tags: ['Python', '编程', '基础']
    }
  })
});

const { task_id } = splitTaskResponse.data;

// 5. 轮询拆分任务状态
const pollTaskStatus = async () => {
  const statusResponse = await fetch(`/api/split/tasks/${task_id}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const { status, progress } = statusResponse.data;
  
  if (status === 'processing') {
    console.log(`处理中: ${progress}%`);
    setTimeout(pollTaskStatus, 5000);  // 5秒后再次查询
  } else if (status === 'completed') {
    // 6. 获取拆分结果
    const resultsResponse = await fetch(`/api/split/tasks/${task_id}/results`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    const { course, videos } = resultsResponse.data;
    console.log('拆分完成！', { course, videos });
  } else if (status === 'failed') {
    console.error('拆分失败');
  }
};

pollTaskStatus();
```


## 十三、接口限流

| 接口类型 | 限流规则 |
|---------|---------|
| 认证接口 | 10次/分钟/IP |
| 上传接口 | 5次/分钟/用户 |
| 拆分任务创建 | 3次/分钟/用户 |
| 其他接口 | 100次/分钟/用户 |

---

## 十四、附录

### 14.1 视频类型说明

- **short**：短视频，时长≤3分钟（180秒）
- **long**：长视频，时长>3分钟

### 14.2 拆分模式说明

- **auto**：自动拆分，系统根据配置自动检测拆分点
- **manual**：手动拆分，用户手动指定所有拆分点
- **hybrid**：混合模式，系统先自动检测，用户可调整

### 14.3 组织模式说明

- **course**：组织成课程/系列，视频有顺序关系
- **independent**：独立视频，拆分后的视频互不关联
- **both**：两种模式，用户可选择

### 14.4 拆分任务状态说明

- **pending**：待处理，任务已创建但未开始处理
- **processing**：处理中，正在执行拆分
- **completed**：已完成，拆分成功
- **failed**：失败，拆分过程中出错
- **cancelled**：已取消，用户取消任务

---


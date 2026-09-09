# tests/ 目录速查

后端 pytest 套件（**315 条**：API 集成 164 + 单元 151，32 个文件）的就近速查。
策略与用例体系见 [测试设计文档](../docs/测试设计文档.md)，环境与执行手册见 [运行测试](../docs/运行测试.md)，人工验收条目见 [手动测试用例清单](../docs/手动测试用例清单.md)。

## 目录结构

```
tests/
├── conftest.py          # 共享 fixtures 与测试库管理（仓库唯一 conftest）
├── api/                 # API 集成测试（164 条 / 17 文件，连真实 PostgreSQL）
│   ├── test_auth.py     # 认证（验证码登录 / JWT 边界矩阵）
│   ├── test_security.py # 安全（SQL 注入 / 认证边界 / 422 边界 / 404 语义）
│   ├── test_idempotency.py  # 幂等与并发防护（点赞切换 / 重复关注 / 分片重传）
│   ├── test_upload*.py  # 上传（init / chunk / complete / 分片合并 / 图片）
│   ├── test_split*.py   # 智能切分（任务 / 直切 / 发布 / 确认）
│   ├── test_feed.py     # 推荐流（推荐 / 关注流 / 热榜 / 搜索 / 个性化）
│   ├── test_interaction.py / test_follow.py / test_course.py
│   ├── test_learn.py    # 学习进度
│   ├── test_inbox.py    # 消息通知
│   ├── test_search.py   # 搜索（建议 / 排序 / 标签）
│   └── test_video.py    # 视频接口
└── unit/                # 单元测试（151 条 / 15 文件，纯逻辑）
    ├── test_recommendation.py   # 推荐算法
    ├── test_smart_split_service.py / test_video_split_service.py / test_video_splitter.py
    ├── test_knowledge_analyzer_logic.py / test_speech_to_text.py / test_pipeline_flow.py / test_glm_fallback.py
    ├── test_models.py / test_utils_auth.py / test_utils_response.py
    └── test_redis_client.py / test_stats.py / test_storage.py / test_sms_service.py
```

## 快速运行

```bash
cd backend
.venv/bin/python -m pytest tests/ -q          # 全量（含覆盖率与 70% 门禁）
.venv/bin/python -m pytest tests/unit/        # 仅单元
.venv/bin/python -m pytest tests/api/         # 仅 API 集成
.venv/bin/python -m pytest tests/api/test_auth.py::TestLogin   # 单类
```

## 关键 fixtures（conftest.py）

- `db`：每个用例建全部表、用例后 DROP CASCADE 清空，完全隔离
- `client` / `auth_client` / `upload_client` / `split_client` / `course_client` / `search_client` / `notification_client`：各服务 ASGI 直连客户端（`dependency_overrides[get_db]` + TestClient，不走网络）
- `test_user` / `test_user2` / `auth_headers` / `auth_headers_user2` / `test_video` / `test_course`
- `_lock_redis_memory_store`（autouse）：patch 三个 `get_redis` 入口走内存降级，测试与 Redis 是否可用无关

## 门禁

- 总量：`--cov-fail-under=70`（pytest.ini addopts）
- 分级：`scripts/check_coverage_gates.py` 对 5 个智能切分模块设独立底线（10/15/45/60/60%）

## 编写新测试

1. 复用 conftest 夹具，断言三件套：状态码 + 响应体 + 数据库最终态
2. 动态数据用 faker/uuid 生成，用例间不共享数据
3. 多组输入用 `@pytest.mark.parametrize` + `id=` 命名
4. 发现缺陷先写复现用例，修复后转普通用例长期驻留（机制见测试设计文档 §4）
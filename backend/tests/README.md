# 测试文档

## 📊 测试概况

### 当前状态（2026-08）
- ✅ **通过率**: 315 通过（全绿，全量回归 ~13 秒实测）
- 📊 **代码覆盖率**: 75.5%（实测，pytest.ini 配置 `--cov-fail-under=70` 门禁）
- 🧪 **测试用例**: 315 个（API 165 + 单元 151），其中 43 例为参数化（数据驱动）矩阵
- 📁 **测试文件**: 32 个
- 🧹 **warnings**: 220 条 → 1 条（已治理 Pydantic/SQLAlchemy/FastAPI 弃用警告，`-W error::DeprecationWarning` 可安全开启）

### 测试分类
- **API测试**: 15个文件，165 用例（含幂等性 test_idempotency.py、安全 test_security.py 专项）
- **单元测试**: 14个文件，151 用例
- **集成测试**: 覆盖所有微服务
- **数据驱动**: 43 例参数化（认证边界矩阵、输入校验矩阵、登录验证码矩阵、工厂分支矩阵等）

### 缺陷管理闭环（2026-08 完成）
- 原 2 个 `xfail(strict)` 已知缺陷已修复并转正为普通回归用例：
  1. **搜索 LIKE 通配符未转义**（`q=%`/`q=_` 可匹配全部视频）→ `ilike(..., escape='\\')` 转义（`services/content/app/api/feed.py`、`services/search/app/api/search.py`），回归用例见 `tests/api/test_security.py`
  2. **热度推荐排序被时间覆盖**（高热旧视频排不过冷新视频）→ 热度分主导、created_at 仅作同分次要键（`services/content/app/services/recommendation.py`），回归用例见 `tests/unit/test_recommendation.py`
- 2026-08 二轮 review 新增修复：
  3. **learn complete 字段名错配**（`completed_ratio` 被 Pydantic 忽略，断言从未生效）→ 改为 `completion_rate` 并补 DB 落库断言（`tests/api/test_learn.py`）
  4. **search hot 排序伪实现**（与 latest 同序）→ 互动总量聚合排序（`services/search/app/api/search.py`）
  5. **无效 base64 返回 500**（客户端输入错误当服务器错误）→ binascii.Error 单独捕获返回 422（`services/upload/app/api/upload.py`）
- 方法论：复现用例（xfail strict 强制回归）→ 修复 → 移除标记转绿，详见 [测试设计文档](../docs/测试设计文档.md)

## 测试结构

```
tests/
├── conftest.py          # pytest配置和共享fixtures
├── unit/                 # 单元测试
│   ├── test_utils_auth.py
│   ├── test_utils_response.py
│   ├── test_models.py
│   └── test_recommendation.py
├── api/                  # API接口测试
│   ├── test_auth.py      # 认证接口
│   ├── test_video.py     # 视频上传接口
│   ├── test_split.py     # 视频拆分接口
│   ├── test_feed.py      # 推荐流接口
│   ├── test_interaction.py  # 互动接口
│   ├── test_course.py    # 课程管理接口
│   ├── test_learn.py     # 学习进度接口
│   ├── test_inbox.py     # 消息通知接口
│   ├── test_search.py    # 搜索接口
│   ├── test_follow.py    # 关注功能接口
│   ├── test_idempotency.py  # 幂等性与并发防护（点赞切换/重复关注/分片重传/唯一约束）
│   └── test_security.py     # 安全与输入校验（SQL注入/认证边界/422边界/404语义）
└── conftest.py           # 共享 fixtures（test_user/test_video/auth_headers 等）
```

## 运行测试

### 激活虚拟环境

项目使用虚拟环境 `.venv`，首先需要激活：

```bash
# macOS/Linux
source ../.venv/bin/activate

# 或者直接使用虚拟环境中的 Python
# 不需要激活环境，直接使用完整路径
```

### 安装测试依赖

项目使用 `uv` 创建的虚拟环境。推荐使用 `uv` 安装依赖：

```bash
cd backend

# 方法1：使用 uv（推荐）
uv pip install -r requirements.txt

# 方法2：如果已激活虚拟环境
pip install -r requirements.txt

# 方法3：使用虚拟环境的 Python 模块方式
../.venv/bin/python -m pip install -r requirements.txt
```

### 运行所有测试

```bash
# 如果已激活虚拟环境
pytest

# 或者使用虚拟环境的完整路径（推荐）
../.venv/bin/pytest

# 或者使用 Python 模块方式（最推荐）
../.venv/bin/python -m pytest
```

### 运行特定模块测试

```bash
# 运行所有单元测试
pytest tests/unit/

# 运行所有API测试
pytest tests/api/

# 运行特定测试文件
pytest tests/api/test_auth.py

# 运行特定测试类
pytest tests/api/test_auth.py::TestLogin

# 运行特定测试方法
pytest tests/api/test_auth.py::TestLogin::test_login_success
```

### 生成覆盖率报告

```bash
# 生成HTML覆盖率报告（覆盖所有代码）
pytest --cov=. --cov-report=html

# 只覆盖特定模块
pytest --cov=common --cov=services --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html
```

### 详细输出

```bash
# 显示详细输出
pytest -v

# 显示print输出
pytest -s

# 显示最详细的输出
pytest -vv -s
```

## 测试标记

测试使用pytest标记进行分类：

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.api` - API接口测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.slow` - 慢速测试

运行特定类型的测试：

```bash
# 只运行单元测试
pytest -m unit

# 只运行API测试
pytest -m api

# 跳过慢速测试
pytest -m "not slow"
```

## 测试数据库

测试使用PostgreSQL测试数据库，每个测试函数都会：
1. 创建新的数据库表
2. 运行测试
3. 清理数据库表

这确保了测试之间的隔离性。

**重要**：运行测试前需要先启动 PostgreSQL 服务并创建测试数据库。

### 1. 启动 PostgreSQL 服务

```bash
cd backend

# 使用 Docker Compose（推荐）
docker-compose up -d postgres

# 检查服务状态
docker-compose ps
```

### 2. 创建测试数据库

```bash
cd backend

# 方法1：使用脚本自动创建（推荐）
../.venv/bin/python scripts/create_test_db.py

# 方法2：使用 Docker 命令创建（需要指定连接到 postgres 数据库）
docker-compose exec postgres psql -U app_user -d postgres -c "CREATE DATABASE short_video_platform_test;"

# 方法3：手动创建（如果使用本地 PostgreSQL）
psql -h localhost -U app_user -c "CREATE DATABASE short_video_platform_test;"
```

**注意**：
- 测试需要PostgreSQL数据库服务正在运行
- 可以通过环境变量`TEST_DATABASE_URL`指定测试数据库，否则使用默认配置（数据库名后加`_test`后缀）
- `conftest.py` 会自动尝试创建测试数据库，但如果权限不足或服务未运行，仍需要手动创建

## 测试Fixtures

### 常用Fixtures

- `db` - 测试数据库会话（每个用例建表+删表隔离）
- `client` - Content 服务测试客户端
- `auth_client` / `upload_client` / `split_client` / `course_client` / `search_client` / `notification_client` - 各服务测试客户端
- `test_user` / `test_user2` - 测试用户
- `auth_headers` - 认证头（基于test_user）
- `test_video` - 测试视频
- `test_course` - 测试课程
- `_lock_redis_memory_store` - autouse fixture，锁定 Redis 走内存降级路径（测试行为与 Redis 是否可用无关）

### 使用示例

```python
def test_example(client, auth_headers, test_user, test_video):
    response = client.get(
        f"/api/videos/{test_video.id}",
        headers=auth_headers
    )
    assert response.status_code == 200
```

## 注意事项

1. **Redis 已锁定内存路径**：conftest autouse fixture 将三个 get_redis 入口（redis_client/stats/split 模块）patch 为返回 None，短信验证码等走内存降级——**测试行为与 Redis 是否可用完全无关**，无需启动 Redis。
2. **异步测试**：FastAPI的异步路由会自动处理，无需特殊配置。
3. **测试隔离**：每个测试函数使用独立的数据库会话，确保测试之间不会相互影响。
4. **数据清理**：db teardown 会 DROP 全部表（失败会显式 fail，杜绝脏表残留）；短信验证码内存 store 每用例后清空。
5. **celery 已 patch**：split 测试的 `celery_app.send_task` 被 monkeypatch 掉，避免连不可用 Redis 的同步重试（原单用例 19s → 0.9s）。

## 覆盖率分级门禁

总量门禁（`--cov-fail-under=70`）之外，核心业务模块有独立底线（`scripts/check_coverage_gates.py`）：

```bash
../.venv/bin/python scripts/check_coverage_gates.py   # 返回码非 0 即失败
```

| 模块 | 底线 |
|---|---|
| smart_split/keyframe_extractor.py | 10% |
| smart_split/video_splitter.py | 15%（API 层实际调用的 ffmpeg 切分器） |
| smart_split_service.py | 45% |
| smart_split/knowledge_analyzer.py | 60% |
| smart_split/speech_to_text.py | 60% |

> 底线为当前实测值向下取整（防止进一步恶化），提升空间见测试设计文档覆盖率 TODO。

## 编写新测试

### 单元测试示例

```python
import pytest
from app.utils.response import success_response

def test_success_response():
    response = success_response(data={"key": "value"})
    assert response.status_code == 200
```

### API测试示例

```python
import pytest

@pytest.mark.api
def test_get_video(client, test_video):
    response = client.get(f"/api/videos/{test_video.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
```

## 持续集成

可以在CI/CD流程中运行测试：

```yaml
# GitHub Actions示例
- name: Run tests
  run: |
    cd backend
    pip install -r requirements.txt
    pytest --cov=app --cov-report=xml
```


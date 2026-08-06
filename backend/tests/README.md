# 测试文档

## 📊 测试概况

### 当前状态（2025-12）
- ✅ **通过率**: 99.3% (146/147)
- 📊 **代码覆盖率**: 71%
- 🧪 **测试用例**: 200+ 个
- 📁 **测试文件**: 15 个

### 测试分类
- **API测试**: 11个文件，120+用例
- **单元测试**: 5个文件，80+用例
- **集成测试**: 覆盖所有微服务

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
│   └── test_follow.py    # 关注功能接口
└── fixtures/             # 测试数据生成器
    └── sample_data.py
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

- `db` - 测试数据库会话
- `client` - FastAPI测试客户端
- `test_user` - 测试用户
- `test_user2` - 第二个测试用户
- `admin_user` - 管理员用户
- `auth_headers` - 认证头（基于test_user）
- `test_video` - 测试视频
- `test_course` - 测试课程

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

1. **Redis依赖**：部分测试需要Redis连接。如果Redis不可用，相关测试可能会跳过或失败。
2. **异步测试**：FastAPI的异步路由会自动处理，无需特殊配置。
3. **测试隔离**：每个测试函数使用独立的数据库会话，确保测试之间不会相互影响。
4. **数据清理**：测试后会自动清理数据库，但Redis数据可能需要手动清理。

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


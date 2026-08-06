"""
测试配置和共享fixtures
"""
import os
import sys
import pytest
from datetime import datetime, timedelta, timezone
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient
from jose import jwt
from faker import Faker

# 设置测试环境变量（必须在导入其他模块之前）
# 这样 common.database.connection 导入时就能检测到测试环境
os.environ['PYTEST_CURRENT_TEST'] = 'conftest'
os.environ['DB_HOST'] = '127.0.0.1'  # 强制使用127.0.0.1而不是postgres
os.environ['DB_NAME'] = 'short_video_platform_test'  # 使用测试数据库

# 添加项目根目录到路径
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_dir)

# 使用common模块
from common.models.base import Base
from common.models import User, Video, Course, LearnRecord, Like, Favorite, Comment, Follow
from common.config.settings import settings
from common.database.connection import get_db, get_redis
from common.utils.redis_client import store_sms_code, delete_sms_code

fake = Faker('zh_CN')

# 测试数据库URL - 使用PostgreSQL测试数据库
# 优先使用环境变量，否则使用默认配置
import os
# 测试时优先使用127.0.0.1（避免localhost解析为IPv6导致的问题）
# 如果DB_HOST是postgres（Docker环境），则使用127.0.0.1
test_db_host = os.getenv("TEST_DB_HOST") or (settings.DB_HOST if settings.DB_HOST != "postgres" else "127.0.0.1")
# 注意：conftest 上方已将 DB_NAME 强制设为 short_video_platform_test（测试库名），
# 直接复用 settings.DB_NAME，避免重复拼接 _test 产生 short_video_platform_test_test
test_db_name = settings.DB_NAME
# 使用 postgresql+psycopg:// 明确指定使用 psycopg 3.x（支持 Python 3.13）
# 强制使用127.0.0.1而不是localhost，避免IPv6解析问题
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}@{test_db_host}:{settings.DB_PORT}/{test_db_name}"
)


def ensure_test_database_exists():
    """确保测试数据库存在，如果不存在则创建"""
    try:
        # 尝试连接到测试数据库
        test_engine_temp = create_engine(
            TEST_DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5}
        )
        with test_engine_temp.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine_temp.dispose()
        return True
    except Exception:
        # 数据库不存在，尝试创建
        try:
            from psycopg import connect
            admin_conn_string = f"host={test_db_host} port={settings.DB_PORT} user={settings.DB_USER} password={settings.DB_PASSWORD} dbname=postgres"
            admin_conn = connect(admin_conn_string)
            admin_conn.autocommit = True
            
            with admin_conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (test_db_name,)
                )
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{test_db_name}"')
                    print(f"✅ 已自动创建测试数据库: {test_db_name}")
            
            admin_conn.close()
            return True
        except Exception as e:
            print(f"❌ 无法创建测试数据库 '{test_db_name}': {e}")
            print(f"\n请手动创建测试数据库：")
            print(f"  1. 运行脚本：python scripts/create_test_db.py")
            print(f"  2. 或使用 psql（本地环境）：")
            print(f"     psql -h localhost -U {settings.DB_USER} -d postgres -c 'CREATE DATABASE {test_db_name};'")
            print(f"  3. 或使用 Docker 命令：")
            print(f"     docker-compose exec postgres psql -U {settings.DB_USER} -d postgres -c 'CREATE DATABASE {test_db_name};'")
            print(f"  3. 或设置环境变量：")
            print(f"     export DB_HOST=localhost")
            print(f"     python scripts/create_test_db.py")
            return False


# 确保测试数据库存在（延迟检查，避免导入时阻塞）
# 如果连接失败，只发出警告，不阻止测试运行
# 实际连接会在测试运行时进行
try:
    if not ensure_test_database_exists():
        import warnings
        warnings.warn(
            f"测试数据库 '{test_db_name}' 不存在且无法自动创建。"
            f"请运行 'python scripts/create_test_db.py' 创建测试数据库。"
            f"如果数据库已存在，测试仍会尝试连接。",
            UserWarning
        )
except Exception as e:
    # 导入时连接失败不影响测试运行，实际连接会在测试时进行
    import warnings
    warnings.warn(
        f"导入时无法验证测试数据库连接: {e}。"
        f"如果数据库服务正在运行，测试仍会尝试连接。",
        UserWarning
    )

# 延迟创建测试数据库引擎（避免导入时连接失败）
# 使用模块级变量存储，但延迟到第一次使用时才创建
_test_engine = None
_TestingSessionLocal = None


def get_test_engine():
    """获取测试数据库引擎（延迟初始化）"""
    global _test_engine
    if _test_engine is None:
        _test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=2,
    max_overflow=5,
    connect_args={
        "connect_timeout": 10,
                "application_name": "short_video_test",
    }
)
    return _test_engine


def get_testing_session_local():
    """获取测试数据库会话工厂（延迟初始化）"""
    global _TestingSessionLocal
    if _TestingSessionLocal is None:
        _TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_test_engine())
    return _TestingSessionLocal


# 为了向后兼容，提供直接访问的方式
# 但实际使用时会在db fixture中通过函数调用获取
test_engine = None  # 将在db fixture中初始化
TestingSessionLocal = None  # 将在db fixture中初始化


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """创建测试数据库会话"""
    # 延迟初始化engine和session factory
    engine = get_test_engine()
    SessionLocal = get_testing_session_local()
    
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        
        # 创建数据库会话
        session = SessionLocal()
        
        try:
            yield session
        finally:
            session.close()
            # 清理所有表
            # 由于videos和long_videos之间存在循环依赖，直接使用CASCADE删除
            try:
                with engine.begin() as conn:
                    # 获取所有表名
                    table_names = [table.name for table in Base.metadata.sorted_tables]
                    # 使用CASCADE删除所有表，让PostgreSQL自动处理依赖关系
                    for table_name in reversed(table_names):
                        try:
                            conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                        except Exception as e:
                            # 如果表不存在或其他错误，继续删除其他表
                            pass
            except Exception as drop_error:
                # 如果批量删除失败，尝试逐个删除
                try:
                    Base.metadata.drop_all(bind=engine)
                except Exception:
                    # 如果还是失败，至少尝试删除主要表
                    with engine.begin() as conn:
                        conn.execute(text("DROP TABLE IF EXISTS videos CASCADE"))
                        conn.execute(text("DROP TABLE IF EXISTS long_videos CASCADE"))
    except Exception as e:
        # 提供更友好的错误信息
        import pytest
        error_msg = str(e)
        # 检查是否是权限问题
        if "Operation not permitted" in error_msg:
            pytest.fail(
                f"无法连接到测试数据库 '{test_db_name}'。\n"
                f"错误: {e}\n\n"
                f"这可能是macOS权限问题。请尝试：\n"
                f"1. 检查Docker容器是否运行: docker-compose ps\n"
                f"2. 检查端口映射: docker-compose ps postgres\n"
                f"3. 尝试重启Docker: docker-compose restart postgres\n"
                f"4. 检查macOS防火墙设置\n"
                f"5. 尝试使用Unix socket连接（如果PostgreSQL支持）\n\n"
                f"数据库配置：\n"
                f"  主机: {test_db_host}\n"
                f"  端口: {settings.DB_PORT}\n"
                f"  数据库: {test_db_name}\n"
                f"  连接URL: {TEST_DATABASE_URL}"
            )
        else:
            pytest.fail(
                f"无法连接到测试数据库 '{test_db_name}'。\n"
                f"错误: {e}\n\n"
                f"请确保：\n"
                f"1. PostgreSQL 服务正在运行（docker-compose up -d postgres）\n"
                f"2. 测试数据库已创建（python scripts/create_test_db.py）\n"
                f"3. 端口 5432 已正确映射到主机\n\n"
                f"数据库配置：\n"
                f"  主机: {test_db_host}\n"
                f"  端口: {settings.DB_PORT}\n"
                f"  数据库: {test_db_name}"
            )


def create_test_client(service_app, db: Session) -> TestClient:
    """创建测试客户端（通用函数）"""
    # 覆盖get_db依赖
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    # 使用函数对象作为key
    service_app.dependency_overrides[get_db] = override_get_db
    
    return TestClient(service_app)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """创建测试客户端（默认使用Content服务，因为它包含大部分API）"""
    # 导入Content服务的app（包含feed、interaction、follow等API）
    from services.content.app.main import app as content_app
    
    test_client = create_test_client(content_app, db)
    
    try:
        yield test_client
    finally:
        # 清理依赖覆盖
        content_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_client(db: Session) -> Generator[TestClient, None, None]:
    """创建Auth服务测试客户端"""
    from services.auth.app.main import app as auth_app
    
    test_client = create_test_client(auth_app, db)
    
    try:
        yield test_client
    finally:
        auth_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def upload_client(db: Session) -> Generator[TestClient, None, None]:
    """创建Upload服务测试客户端"""
    from services.upload.app.main import app as upload_app
    
    test_client = create_test_client(upload_app, db)
    
    try:
        yield test_client
    finally:
        upload_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def split_client(db: Session) -> Generator[TestClient, None, None]:
    """创建Split服务测试客户端"""
    from services.split.app.main import app as split_app
    
    test_client = create_test_client(split_app, db)
    
    try:
        yield test_client
    finally:
        split_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def course_client(db: Session) -> Generator[TestClient, None, None]:
    """创建Course服务测试客户端"""
    from services.course.app.main import app as course_app
    
    test_client = create_test_client(course_app, db)
    
    try:
        yield test_client
    finally:
        course_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def search_client(db: Session) -> Generator[TestClient, None, None]:
    """创建Search服务测试客户端"""
    from services.search.app.main import app as search_app
    
    test_client = create_test_client(search_app, db)
    
    try:
        yield test_client
    finally:
        search_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def notification_client(db: Session) -> Generator[TestClient, None, None]:
    """创建Notification服务测试客户端"""
    from services.notification.app.main import app as notification_app
    
    test_client = create_test_client(notification_app, db)
    
    try:
        yield test_client
    finally:
        notification_app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session) -> User:
    """创建测试用户"""
    user = User(
        id=str(fake.uuid4()),
        phone=fake.unique.phone_number()[:20],
        nickname=fake.name(),
        avatar_url=fake.image_url(),
        bio=fake.text()[:200],
        language="zh-CN",
        roles=["learner"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_user2(db: Session) -> User:
    """创建第二个测试用户"""
    user = User(
        id=str(fake.uuid4()),
        phone=fake.unique.phone_number()[:20],
        nickname=fake.name(),
        avatar_url=fake.image_url(),
        bio=fake.text()[:200],
        language="zh-CN",
        roles=["learner"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db: Session) -> User:
    """创建管理员用户"""
    user = User(
        id=str(fake.uuid4()),
        phone=fake.unique.phone_number()[:20],
        nickname="管理员",
        avatar_url=fake.image_url(),
        language="zh-CN",
        roles=["admin", "learner"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_access_token(user_id: str, expires_delta: timedelta = None) -> str:
    """创建JWT token（用于测试）"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": user_id, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """生成认证头"""
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user2(test_user2: User) -> dict:
    """生成第二个用户的认证头"""
    token = create_access_token(str(test_user2.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def expired_auth_headers(test_user: User) -> dict:
    """生成过期的认证头"""
    token = create_access_token(str(test_user.id), expires_delta=timedelta(minutes=-1))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_video(db: Session, test_user: User) -> Video:
    """创建测试视频"""
    video = Video(
        id=str(fake.uuid4()),
        author_id=test_user.id,
        title=fake.sentence()[:200],
        description=fake.text()[:500],
        tags=["测试", "视频"],
        duration=120,
        play_url=fake.url(),
        cover_url=fake.image_url(),
        language="zh-CN",
        status="online",
        video_type="short"
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@pytest.fixture
def test_video_pending(db: Session, test_user: User) -> Video:
    """创建待审核的测试视频"""
    video = Video(
        id=str(fake.uuid4()),
        author_id=test_user.id,
        title=fake.sentence()[:200],
        description=fake.text()[:500],
        tags=["测试"],
        duration=120,
        play_url=fake.url(),
        cover_url=fake.image_url(),
        language="zh-CN",
        status="pending",
        video_type="short"
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@pytest.fixture
def test_course(db: Session, test_user: User) -> Course:
    """创建测试课程"""
    import uuid
    course = Course(
        id=str(uuid.uuid4()),
        course_id=f"course_{uuid.uuid4().hex[:8]}",
        author_id=test_user.id,
        title=fake.sentence()[:200],
        description=fake.text()[:500],
        tags=["测试", "课程"],
        cover_url=fake.image_url(),
        language="zh-CN",
        status="online",
        total_videos=0,
        total_duration=0
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@pytest.fixture
def test_sms_code(test_user: User) -> str:
    """创建测试验证码并存储到Redis（模拟）"""
    code = "123456"
    phone = test_user.phone
    # 注意：这里需要实际的Redis连接，测试时可能需要Mock
    # 为了简化，我们假设验证码已存储
    try:
        store_sms_code(phone, code, 300)
    except Exception:
        # Redis不可用时跳过
        pass
    return code


@pytest.fixture(autouse=True)
def cleanup_redis():
    """清理Redis测试数据（如果Redis可用）"""
    yield
    # 测试后清理Redis数据
    try:
        redis_client = get_redis()
        if redis_client:
            # 清理测试相关的key（根据实际情况调整）
            pass
    except Exception:
        pass


#!/usr/bin/env python3
"""
测试数据库连接诊断脚本
"""
import sys
import os

# 添加项目根目录到路径
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_dir)

from common.config.settings import settings
from psycopg import connect


def test_connection():
    """测试数据库连接"""
    print("=" * 60)
    print("数据库连接诊断")
    print("=" * 60)
    
    # 测试数据库配置
    test_db_name = f"{settings.DB_NAME}_test"
    
    # 自动检测数据库主机
    db_host = settings.DB_HOST
    if db_host == "postgres":
        db_host = "localhost"
        print(f"⚠️  检测到 Docker 容器名 'postgres'，使用 'localhost'")
    
    print(f"\n配置信息：")
    print(f"  主机: {db_host}")
    print(f"  端口: {settings.DB_PORT}")
    print(f"  用户: {settings.DB_USER}")
    print(f"  数据库: {test_db_name}")
    
    # 测试连接到 postgres 数据库
    print(f"\n1. 测试连接到 postgres 数据库...")
    try:
        conn_string = f"host={db_host} port={settings.DB_PORT} user={settings.DB_USER} password={settings.DB_PASSWORD} dbname=postgres"
        conn = connect(conn_string)
        print(f"   ✅ 连接成功")
        conn.close()
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        print(f"\n   请检查：")
        print(f"   - Docker 容器是否运行: docker-compose ps")
        print(f"   - 端口是否正确映射: docker-compose ps postgres")
        return False
    
    # 测试连接到测试数据库
    print(f"\n2. 测试连接到测试数据库 '{test_db_name}'...")
    try:
        conn_string = f"host={db_host} port={settings.DB_PORT} user={settings.DB_USER} password={settings.DB_PASSWORD} dbname={test_db_name}"
        conn = connect(conn_string)
        print(f"   ✅ 连接成功")
        conn.close()
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        print(f"\n   测试数据库可能不存在，尝试创建...")
        
        # 尝试创建数据库
        try:
            admin_conn = connect(f"host={db_host} port={settings.DB_PORT} user={settings.DB_USER} password={settings.DB_PASSWORD} dbname=postgres")
            admin_conn.autocommit = True
            
            with admin_conn.cursor() as cur:
                cur.execute(f'CREATE DATABASE "{test_db_name}"')
                print(f"   ✅ 测试数据库创建成功")
            
            admin_conn.close()
            
            # 再次测试连接
            conn = connect(conn_string)
            print(f"   ✅ 连接测试数据库成功")
            conn.close()
        except Exception as e2:
            print(f"   ❌ 创建失败: {e2}")
            print(f"\n   请手动创建测试数据库：")
            print(f"   docker-compose exec postgres psql -U {settings.DB_USER} -d postgres -c 'CREATE DATABASE {test_db_name};'")
            return False
    
    # 测试 SQLAlchemy 连接
    print(f"\n3. 测试 SQLAlchemy 连接...")
    try:
        from sqlalchemy import create_engine, text
        test_db_url = f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}@{db_host}:{settings.DB_PORT}/{test_db_name}"
        engine = create_engine(test_db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"   ✅ SQLAlchemy 连接成功")
        engine.dispose()
    except Exception as e:
        print(f"   ❌ SQLAlchemy 连接失败: {e}")
        return False
    
    print(f"\n" + "=" * 60)
    print("✅ 所有连接测试通过！可以运行测试了。")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)


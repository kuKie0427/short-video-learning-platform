#!/usr/bin/env python3
"""
创建测试数据库脚本
"""
import sys
import os

# 添加项目根目录到路径
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_dir)

from common.config.settings import settings
from sqlalchemy import create_engine, text
from psycopg import connect


def create_test_database():
    """创建测试数据库"""
    # 测试数据库名称
    test_db_name = f"{settings.DB_NAME}_test"
    
    # 自动检测数据库主机：如果配置的是 Docker 容器名但在本地环境，尝试使用 localhost
    db_host = settings.DB_HOST
    if db_host == "postgres":
        # 尝试使用 localhost（本地开发环境）
        print("检测到 Docker 容器名 'postgres'，尝试使用 'localhost'...")
        db_host = "localhost"
    
    print(f"正在连接到 PostgreSQL 服务器: {db_host}:{settings.DB_PORT}")
    print(f"用户: {settings.DB_USER}")
    print(f"目标数据库: {test_db_name}")
    
    # 尝试连接的主机列表（按优先级）
    hosts_to_try = [db_host]
    if db_host == "localhost" and settings.DB_HOST == "postgres":
        # 如果自动切换到 localhost，也保留原配置作为备选
        hosts_to_try.append(settings.DB_HOST)
    
    last_error = None
    for host in hosts_to_try:
        try:
            # 使用 psycopg 直接连接（更简单）
            conn_string = f"host={host} port={settings.DB_PORT} user={settings.DB_USER} password={settings.DB_PASSWORD} dbname=postgres"
            conn = connect(conn_string)
            conn.autocommit = True
            
            with conn.cursor() as cur:
                # 检查数据库是否已存在
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (test_db_name,)
                )
                exists = cur.fetchone()
                
                if exists:
                    print(f"✅ 测试数据库 '{test_db_name}' 已存在")
                else:
                    # 创建数据库
                    print(f"正在创建测试数据库 '{test_db_name}'...")
                    cur.execute(f'CREATE DATABASE "{test_db_name}"')
                    print(f"✅ 测试数据库 '{test_db_name}' 创建成功")
            
            conn.close()
            return True
            
        except Exception as e:
            last_error = e
            if host != hosts_to_try[-1]:
                print(f"⚠️  使用 '{host}' 连接失败，尝试下一个...")
                continue
    
    # 所有尝试都失败了
    print(f"❌ 创建测试数据库失败: {last_error}")
    print("\n可能的解决方案：")
    print("1. 确保 PostgreSQL 服务正在运行")
    print("2. 检查数据库连接配置（DB_HOST, DB_PORT, DB_USER, DB_PASSWORD）")
    print("   - 本地环境：设置 DB_HOST=localhost")
    print("   - Docker 环境：设置 DB_HOST=postgres（容器名）")
    print("3. 确保数据库用户有创建数据库的权限")
    print(f"\n手动创建数据库的命令（本地环境）：")
    print(f"  psql -h localhost -U {settings.DB_USER} -d postgres -c 'CREATE DATABASE {test_db_name};'")
    print(f"\n手动创建数据库的命令（Docker 环境）：")
    print(f"  docker-compose exec postgres psql -U {settings.DB_USER} -d postgres -c 'CREATE DATABASE {test_db_name};'")
    print(f"\n或者设置环境变量：")
    print(f"  export DB_HOST=localhost")
    print(f"  python scripts/create_test_db.py")
    return False


if __name__ == "__main__":
    success = create_test_database()
    sys.exit(0 if success else 1)


#!/usr/bin/env python3
"""
测试代码结构验证脚本
检查测试文件是否存在且语法正确
"""
import os
import sys
import ast
from pathlib import Path

def check_file_syntax(file_path):
    """检查文件语法"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def main():
    """主函数"""
    base_dir = Path(__file__).parent
    tests_dir = base_dir / "tests"
    
    print("=" * 60)
    print("测试代码结构验证")
    print("=" * 60)
    
    # 检查测试目录
    if not tests_dir.exists():
        print(f"❌ 测试目录不存在: {tests_dir}")
        return 1
    
    print(f"✅ 测试目录存在: {tests_dir}")
    
    # 检查关键文件
    key_files = [
        "tests/conftest.py",
        "tests/unit/test_utils_auth.py",
        "tests/unit/test_utils_response.py",
        "tests/unit/test_models.py",
        "tests/unit/test_recommendation.py",
        "tests/api/test_auth.py",
        "tests/api/test_video.py",
        "tests/api/test_split.py",
        "tests/api/test_feed.py",
        "tests/api/test_interaction.py",
        "tests/api/test_course.py",
        "tests/api/test_learn.py",
        "tests/api/test_inbox.py",
        "tests/api/test_search.py",
        "tests/api/test_follow.py",
    ]
    
    print("\n检查测试文件:")
    print("-" * 60)
    
    all_ok = True
    for file_path in key_files:
        full_path = base_dir / file_path
        if full_path.exists():
            ok, error = check_file_syntax(full_path)
            if ok:
                print(f"✅ {file_path}")
            else:
                print(f"❌ {file_path} - 语法错误: {error}")
                all_ok = False
        else:
            print(f"⚠️  {file_path} - 文件不存在")
            all_ok = False
    
    # 检查pytest配置
    print("\n检查配置文件:")
    print("-" * 60)
    pytest_ini = base_dir / "pytest.ini"
    if pytest_ini.exists():
        print(f"✅ pytest.ini 存在")
    else:
        print(f"⚠️  pytest.ini 不存在")
        all_ok = False
    
    # 检查requirements.txt中的测试依赖
    print("\n检查依赖配置:")
    print("-" * 60)
    requirements = base_dir / "requirements.txt"
    if requirements.exists():
        with open(requirements, 'r') as f:
            content = f.read()
            test_deps = ['pytest', 'pytest-asyncio', 'httpx', 'pytest-cov', 'faker', 'freezegun']
            for dep in test_deps:
                if dep in content:
                    print(f"✅ {dep} 在 requirements.txt 中")
                else:
                    print(f"⚠️  {dep} 不在 requirements.txt 中")
                    all_ok = False
    else:
        print("❌ requirements.txt 不存在")
        all_ok = False
    
    # 总结
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ 所有检查通过！")
        print("\n下一步：")
        print("1. 安装测试依赖: pip install -r requirements.txt")
        print("2. 运行测试: pytest")
    else:
        print("⚠️  发现一些问题，请检查上述输出")
    print("=" * 60)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())


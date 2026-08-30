#!/usr/bin/env python3
"""
覆盖率分级门禁：对关键业务模块设置独立覆盖率底线，防止被总量掩盖

背景：pytest.ini 的 --cov-fail-under=70 只看总量，而智能切分管线等核心业务
模块覆盖率远低于总量（keyframe_extractor 11%、video_splitter 15%、
smart_split_service 45%）——哪天删掉几个高覆盖文件，总量跌破 70 也不会提示是哪个模块失守。

用法：在跑完 pytest（生成 .coverage 数据）后执行：
    python scripts/check_coverage_gates.py
返回码非 0 即门禁失败（供 CI 使用）。
"""
import sys
from pathlib import Path

import coverage

# 关键业务模块覆盖率底线（当前实测值向下取整，防止进一步恶化；
# 提升空间见 backend/docs/测试设计文档.md 的覆盖率改进 TODO）
GATES = {
    "services/split/app/services/smart_split/keyframe_extractor.py": 10,
    "services/split/app/services/video_splitter.py": 15,
    "services/split/app/services/smart_split_service.py": 45,
    "services/split/app/services/smart_split/knowledge_analyzer.py": 60,
    "services/split/app/services/smart_split/speech_to_text.py": 60,
}


def main() -> int:
    backend_dir = Path(__file__).resolve().parent.parent
    cov = coverage.Coverage(data_file=str(backend_dir / ".coverage"))
    cov.load()
    data = cov.get_data()

    # measured_files 返回绝对路径，GATES 用相对路径（相对 backend/），按后缀匹配
    failures = []
    for rel_path, threshold in GATES.items():
        abs_path = str(backend_dir / rel_path)
        if abs_path not in data.measured_files():
            failures.append(f"  {rel_path}: 未测量（文件可能已删除或改名）")
            continue
        analysis = cov.analysis2(abs_path)
        # 返回 (filename, executable_lines, excluded_lines, missing_lines, formatted)
        executable = analysis[1]
        missing = analysis[3]
        total = len(executable)
        pct = (total - len(missing)) / total * 100 if total else 100.0
        status = "✅" if pct >= threshold else "❌"
        line = f"  {status} {rel_path}: {pct:.0f}% (底线 {threshold}%)"
        print(line)
        if pct < threshold:
            failures.append(line)

    if failures:
        print(f"\n覆盖率分级门禁失败：{len(failures)} 个模块低于底线")
        return 1
    print("\n覆盖率分级门禁通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

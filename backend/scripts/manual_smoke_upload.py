#!/usr/bin/env python3
"""手工用例 U01 / U02 的真实执行脚本（发布冒烟留痕用）。

链路：init → 真实分片 PUT ×N → complete → 校验响应含 video_id/status/file_url → 查库核对落库。
对应缺陷回归：BUG-004（接口 200 但 data=null 且未落库的"静默失败"）。

用法（前置：docker-compose 全栈已起，见 backend/QUICK_START.md）：
    cd backend && .venv/bin/python scripts/manual_smoke_upload.py
退出码 0 = 用例通过；非 0 = 失败（打印 FAIL 原因，可直接抄进缺陷台账）。

依赖素材：仓库内 short_video/3分钟学习微积分.mp4；开发态鉴权用固定 UUID 直通
（common/utils/auth.py 的 DEV 分支），可用环境变量 SMOKE_DEV_USER 覆盖。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
GW = os.environ.get("SMOKE_GATEWAY", "http://localhost")
DEV_USER = os.environ.get("SMOKE_DEV_USER", "00000000-0000-0000-0000-000000000001")
AUTH = {"Authorization": f"Bearer {DEV_USER}"}
SRC = Path(__file__).resolve().parents[2] / "short_video" / "3分钟学习微积分.mp4"
PG_CONTAINER = os.environ.get("SMOKE_PG_CONTAINER", "short_video_postgres")
PG_DB = os.environ.get("SMOKE_PG_DB", "short_video_platform")
PG_USER = os.environ.get("SMOKE_PG_USER", "app_user")
CHUNK_SIZE = 5 * 1024 * 1024


def check(condition: bool, label: str, detail: str = "") -> None:
    """断言并打印，失败即非零退出（冒烟留痕要的是可抄进台账的结论）。"""
    if not condition:
        raise SystemExit(f"FAIL {label} {detail}")
    print(f"PASS {label} {detail}".rstrip())


def query_video_row(video_id: str) -> str:
    """按主键查 videos 落库结果。

    video_id 先做 UUID 格式校验（不合规直接 FAIL），再以 psql 变量的方式（set + :'vid'）传入，
    避开拼字符串 SQL；psql 的 `:'vid'` 只在脚本模式下展开，所以走 stdin 而非 -c。
    """
    if not UUID_RE.fullmatch(video_id):
        raise SystemExit(f"FAIL 响应返回的 video_id 不是合法 UUID: {video_id!r}")
    script = (
        f"\\set vid '{video_id}'\n"
        "SELECT id, title, status, duration, video_type FROM videos WHERE id = :'vid';\n"
    )
    try:
        proc = subprocess.run(
            ["docker", "exec", "-i", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB,
             "-t", "-A"],
            input=script, capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"FAIL 查库执行异常: {exc}") from exc
    if proc.returncode != 0:
        raise SystemExit(f"FAIL 查库返回非零: {proc.stderr.strip()}")
    return proc.stdout.strip()


def main() -> int:
    if not SRC.is_file():
        raise SystemExit(f"FAIL 缺少冒烟素材: {SRC}")
    payload = SRC.read_bytes()
    parts = [payload[i:i + CHUNK_SIZE] for i in range(0, len(payload), CHUNK_SIZE)]
    print(f"素材 {SRC.name}  {len(payload)} bytes  分片数 {len(parts)}")

    # ① init —— 契约：响应声明 chunk_size=5242880（客户端按此分片）
    init = httpx.post(f"{GW}/api/upload/init", headers=AUTH, json={
        "file_name": "手工用例U01.mp4", "file_size": len(payload), "duration": 180,
        "mime_type": "video/mp4", "video_type": "short",
    }, timeout=60)
    check(init.status_code == 200, "init 返回 200", f"(实际 {init.status_code})")
    init_data = init.json().get("data") or {}
    upload_id = init_data.get("upload_id", "")
    check(bool(upload_id), "init 响应含 upload_id", f"(data={json.dumps(init_data, ensure_ascii=False)})")
    check(init_data.get("chunk_size") == 5242880, "chunk_size 契约 = 5242880",
          f"(实际 {init_data.get('chunk_size')})")

    # ② 逐片 PUT —— 契约：upload_id / chunk_index 走请求头，body 为二进制
    for idx, part in enumerate(parts):
        chunk_resp = httpx.put(
            f"{GW}/api/upload/chunk",
            headers={**AUTH, "upload_id": upload_id, "chunk_index": str(idx)},
            content=part, timeout=120,
        )
        check(chunk_resp.status_code == 200, f"chunk[{idx}] {len(part)}B 上传成功",
              f"(实际 {chunk_resp.status_code} {chunk_resp.text[:120]})")

    # ③ complete
    done = httpx.post(f"{GW}/api/upload/complete", headers=AUTH, json={
        "upload_id": upload_id, "title": "手工用例U01-冒烟留痕",
        "description": "U01/U02 发布冒烟执行记录", "tags": ["手工冒烟"],
        "language": "zh-CN", "is_public": True,
    }, timeout=120)
    check(done.status_code == 200, "complete 返回 200", f"(实际 {done.status_code})")
    body = done.json()
    check(body.get("code") == 200, "业务信封 code=200", f"(实际 {body.get('code')})")

    # ④ BUG-004 三位一体：状态码 + 响应体业务字段 + 数据库最终态
    data = body.get("data")
    check(bool(data), "响应体 data 非空（BUG-004 静默失败防线）")
    for field in ("video_id", "status", "file_url"):
        check(bool((data or {}).get(field)), f"响应含业务字段 {field}",
              f"(data={json.dumps(data, ensure_ascii=False)})")

    row = query_video_row(str((data or {}).get("video_id")))
    check(bool(row), "videos 表存在该记录（落库一致）", f"(查询结果={row!r})")
    print(f"\nU01/U02 通过：upload_id={upload_id} 落库行={row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

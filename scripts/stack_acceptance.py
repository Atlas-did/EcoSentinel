"""整栈自证：一条命令证明"起得来、打得通、字段对"。

给队友 / AI 代理（DSH 等）用的**退出码判据**，不需要硬件、不需要 API key：

    1) 在**空闲端口**上以线程方式启动 FastAPI（不 spawn 子进程 ⇒ 受限沙箱也能跑）
    2) 依次请求 7 个只读端点，要求 200 + 合法 JSON
    3) 校验契约字段（snapshot.schema_version、health.ai_worker 等）
    4) 打印人看得懂的摘要，并以退出码收尾

退出码：
    0 PASS / 1 端点不可用或返回非 JSON / 2 契约字段缺失 / 3 服务器未在限期内起来

用法：
    python scripts/stack_acceptance.py            # 自动挑空闲端口
    python scripts/stack_acceptance.py --port 8099
"""

import argparse
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

if __package__ in (None, ""):  # 允许 `python scripts/stack_acceptance.py` 直接跑
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ENDPOINTS = [
    ("/api/ping", "json-object"),
    ("/api/snapshot", "json-object"),
    ("/api/chart?range=5m", "json"),
    ("/api/ai-candidates", "json"),
    ("/api/resilience", "json"),
    ("/api/energy-summary", "json"),
    ("/api/health", "json-object"),
]

REQUIRED_FIELDS = {
    "/api/snapshot": ("schema_version", "timestamp"),
    "/api/health": ("schema_version", "ai_worker"),
}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def fetch(port: int, path: str, timeout: float = 5.0):
    url = f"http://127.0.0.1:{port}{path}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="EcoSentinel stack acceptance (read-only)")
    parser.add_argument("--port", type=int, default=0, help="0 = 自动挑选空闲端口")
    parser.add_argument("--log-dir", type=str, default=None, help="JSONL 目录（默认仓库 logs/）")
    args = parser.parse_args()

    port = args.port or free_port()

    import uvicorn

    from energy_system.api.app import create_app

    def make_app():
        kwargs = {"log_dir": args.log_dir} if args.log_dir else {}
        return create_app(**kwargs)

    config = uvicorn.Config(make_app(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 20
    started = False
    while time.time() < deadline:
        if getattr(server, "started", False):
            started = True
            break
        time.sleep(0.2)
    if not started:
        print("  [FAIL] 服务器未能在 20s 内启动")
        return 3

    print(f"  EcoSentinel 整栈自证  →  http://127.0.0.1:{port}")
    failures = 0
    for path, kind in ENDPOINTS:
        try:
            status, body = fetch(port, path)
        except urllib.error.HTTPError as exc:
            print(f"  [FAIL] {path:<28} HTTP {exc.code}")
            failures += 1
            continue
        except Exception as exc:  # noqa: BLE001 —— 任何异常都算端点不可用
            print(f"  [FAIL] {path:<28} {type(exc).__name__}: {exc}")
            failures += 1
            continue

        if kind == "json-object" and not isinstance(body, dict):
            print(f"  [FAIL] {path:<28} 期望 JSON 对象，实得 {type(body).__name__}")
            failures += 1
            continue

        missing = [f for f in REQUIRED_FIELDS.get(path, ()) if f not in body]
        if missing:
            print(f"  [FAIL] {path:<28} 缺字段 {missing}")
            failures += 1
            continue

        extra = ""
        if path == "/api/health":
            extra = f"   ai_worker={'已接线' if body.get('ai_worker') else 'null（未接线，符合预期）'}"
        print(f"  [ OK ] {path:<28} HTTP {status}{extra}")

    server.should_exit = True
    time.sleep(0.3)

    if failures:
        print(f"\n  结论：FAIL（{failures}/{len(ENDPOINTS)} 个端点不达标）")
        return 1 if failures else 0
    print(f"\n  结论：PASS（{len(ENDPOINTS)}/{len(ENDPOINTS)} 个只读端点均可用且字段完整）")
    print("  提示：未接硬件时 snapshot 各读数为 null 属**预期**（如实上报，不伪造）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""REST API server for the Environmental Monitoring frontend.

Reads from the same log files written by main.py and exposes structured
JSON endpoints consumed by the React dashboard.

This module is a thin compatibility entry point: it builds the app via
:func:`energy_system.api.app.create_app` so the routing and business logic live
in the API layer and can be tested without starting a server.

Usage:
    python api_server.py              # default: http://0.0.0.0:8080
    python api_server.py --port 8081  # custom port
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on the Python path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from energy_system.api.app import create_app
from energy_system.config.config_loader import load_app_config
from energy_system.config.env import cors_origins_override

# ── Config ─────────────────────────────────────────────────────────
cfg, _warnings = load_app_config()

LOG_DIR = _PROJECT_ROOT / "logs"


def _resolve_cors_origins() -> list[str]:
    """Resolve CORS origins from config, with an explicit env override for prod.

    Defaults are local development frontends only. The wildcard ``*`` is never
    emitted with ``allow_credentials=True`` — the config loader already rejects
    that combination.
    """
    origins = cors_origins_override()
    if origins:
        return origins
    return list(cfg.api.cors_origins)


# ── App ────────────────────────────────────────────────────────────
app = create_app(
    cfg=cfg,
    log_dir=LOG_DIR,
    cors_origins=_resolve_cors_origins(),
    allow_credentials=bool(cfg.api.allow_credentials),
)


# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="Environmental Monitoring API Server")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind address")
    args = parser.parse_args()

    print(f"Starting API server on http://{args.host}:{args.port}")
    print(f"Log directory: {LOG_DIR}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

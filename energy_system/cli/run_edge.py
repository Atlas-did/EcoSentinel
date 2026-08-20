"""Hardware-mode edge runtime entry point.

Replaces the inline ``if __name__ == "__main__"`` block that used to live in
``main.py``. ``python main.py`` remains a thin compatibility shim that calls
:func:`main`.

Usage:
    python -m energy_system.cli.run_edge [--config path] [--api-key-env NAME]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from energy_system.config.config_loader import load_app_config
from energy_system.utils.env_loader import load_dotenv_if_present
from energy_system.utils.logger import setup_logger

logger = setup_logger("Main")

_INSTANCE_LOCK_FH = None


def _acquire_single_instance_lock(
    lock_path: str = os.path.join("logs", "main.lock"),
) -> bool:
    """Best-effort single-instance lock (Windows-friendly)."""
    global _INSTANCE_LOCK_FH
    try:
        from msvcrt import LK_NBLCK, locking  # type: ignore
    except Exception:
        return True  # Non-Windows or unavailable: skip

    try:
        p = Path(lock_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = open(p, "a+", encoding="utf-8")
        try:
            locking(fh.fileno(), LK_NBLCK, 1)
        except OSError:
            try:
                fh.seek(0)
                other = fh.read().strip()
            except Exception:
                other = ""
            try:
                fh.close()
            except Exception:
                pass
            logger.error(
                "Detected another running main.py instance; refusing to start. "
                f"If you are sure it's stale, delete {p} (content={other!r})."
            )
            return False

        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        _INSTANCE_LOCK_FH = fh
        return True
    except Exception:
        return True


def resolve_api_key() -> str | None:
    """Resolve the API key from environment variables (never from config)."""
    return (
        os.getenv("DEEPSEEK_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("AI_API_KEY", "").strip()
        or None
    )


def run_edge(cfg=None, api_key: str | None = None) -> None:
    """Build the edge runtime and run its control loop."""
    from energy_system.application.runtime import EnergySystemApp

    if cfg is None:
        cfg, _warnings = load_app_config()
    app = EnergySystemApp(config=cfg, api_key=api_key)
    app.run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EcoSentinel edge runtime")
    parser.add_argument(
        "--config",
        type=str,
        default="energy_system/config/params.yaml",
        help="Path to the YAML config file.",
    )
    args = parser.parse_args(argv)

    if not _acquire_single_instance_lock():
        return 3

    cfg, warnings = load_app_config(args.config)
    for w in warnings:
        logger.warning(w)

    # Load .env files (including legacy ai_workspace/von.env)
    load_dotenv_if_present(".env", "ai_workspace/von.env")

    api_key = resolve_api_key()

    if os.getenv("DEEPSEEK_API_KEY", "").strip():
        if "openai.com" in (cfg.ai.api_base or "") and (cfg.ai.model or "").startswith("gpt-"):
            logger.warning(
                "Detected DEEPSEEK_API_KEY but ai.api_base/model still look like OpenAI defaults. "
                "For DeepSeek, set ai.api_base=https://api.deepseek.com/v1 and "
                "ai.model=deepseek-chat (see params.yaml example)."
            )

    run_edge(cfg=cfg, api_key=api_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())

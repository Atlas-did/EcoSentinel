"""Environment access: the single place that reads or writes the process environment.

Rule (refactor design §3.1, rule 4): only this module may touch ``os.environ`` /
``os.getenv``. Everything else asks these typed getters — so defaults, accepted
alias names and parsing live in exactly one place instead of being re-derived at
each call site (that duplication was pain point P4).
"""

from __future__ import annotations

import os
from pathlib import Path

from energy_system.utils.env_loader import read_dotenv
from energy_system.utils.logger import setup_logger

logger = setup_logger("ConfigEnv")

#: AI key aliases, in precedence order (all three names appear in real deployments).
AI_API_KEY_ENV_NAMES = ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "AI_API_KEY")

BATTERY_CAPACITY_MAH_DEFAULT = 10000.0
BATTERY_INITIAL_SOC_DEFAULT = 80.0
CORS_ORIGINS_ENV = "ECOSENTINEL_CORS_ORIGINS"


def apply_dotenv(*paths: str) -> dict[str, str]:
    """Load .env files into the process environment (first definition wins).

    Keys already present in ``os.environ`` are never overwritten, matching the
    previous behaviour of ``utils.env_loader.load_dotenv_if_present``.
    Returns the merged values (useful for tests and diagnostics).
    """
    loaded: dict[str, str] = {}
    for path in paths:
        for key, value in read_dotenv(Path(path)).items():
            loaded.setdefault(key, value)
            os.environ.setdefault(key, value)
    return loaded


def env_value(name: str, default: str = "") -> str:
    """Read one variable (stripped) without letting call sites touch ``os``."""
    return (os.getenv(name, default) or "").strip()


def ai_api_key() -> str:
    """First non-empty of DEEPSEEK_API_KEY / OPENAI_API_KEY / AI_API_KEY."""
    for name in AI_API_KEY_ENV_NAMES:
        value = (os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def has_ai_api_key() -> bool:
    return bool(ai_api_key())


def _float_env(name: str, default: float) -> float:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        # 不静默吞掉笔误：给出可搜索的告警，然后退回默认值。
        logger.warning(f"{name}={raw!r} is not a number; falling back to {default}")
        return float(default)


def battery_capacity_mah() -> float:
    return _float_env("BATTERY_CAPACITY_MAH", BATTERY_CAPACITY_MAH_DEFAULT)


def battery_initial_soc() -> float:
    return _float_env("BATTERY_INITIAL_SOC", BATTERY_INITIAL_SOC_DEFAULT)


def cors_origins_override() -> list[str]:
    """``ECOSENTINEL_CORS_ORIGINS="a,b"`` → ``["a", "b"]``; unset ⇒ ``[]``.

    An empty list means "no override": the caller falls back to ``cfg.api.cors_origins``.
    """
    raw = (os.getenv(CORS_ORIGINS_ENV, "") or "").strip()
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

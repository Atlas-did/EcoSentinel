"""Configuration loader with type-safe YAML parsing and validation.

Loads params.yaml into a frozen AppConfig dataclass, with per-field type
checking, range validation, and human-readable warning messages.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import yaml

from energy_system.config.runtime_config import (
    AIConfig,
    AIRequestCandidate,
    ApiConfig,
    AppConfig,
    ControlConfig,
    SelfHealingConfig,
    SerialConfig,
    Thresholds,
)


# -- YAML helpers ---------------------------------------------------------
def _as_dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _get(raw: dict, path: str, default: Any = None) -> Any:
    """Get a nested value from a dict using dot-separated path."""
    cur: Any = raw
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


# -- Generic field parsers ------------------------------------------------
def _parse_bool(
    raw: dict, path: str, current: Any, warnings: list[str],
) -> Any:
    """Parse a boolean field. Returns the dataclass to replace()."""
    val = _get(raw, path, None)
    if val is None:
        return current  # not specified, keep default
    if isinstance(val, bool):
        return val
    warnings.append(f"{path} must be boolean; using default")
    return current


def _parse_str(
    raw: dict, path: str, current: Any, warnings: list[str],
    *,
    choices: list[str] | None = None,
    nonempty: bool = False,
) -> Any:
    """Parse a string field. Returns the dataclass to replace()."""
    val = _get(raw, path, None)
    if val is None:
        return current
    if not isinstance(val, str):
        warnings.append(f"{path} must be string; using default")
        return current
    s = val.strip()
    if nonempty and not s:
        warnings.append(f"{path} must be non-empty; using default")
        return current
    if choices is not None:
        if s.lower() not in {c.lower() for c in choices}:
            warnings.append(f"{path} must be one of {choices}; using default")
            return current
        return s.lower()
    return s


def _parse_float(
    raw: dict, path: str, current: Any, warnings: list[str],
    *,
    min_val: float | None = None,
    max_val: float | None = None,
) -> Any:
    """Parse a numeric field (int or float). Returns the value or default."""
    val = _get(raw, path, None)
    if val is None:
        return current
    if not isinstance(val, (int, float)):
        warnings.append(f"{path} must be a number; using default")
        return current
    f = float(val)
    if min_val is not None and f < min_val:
        warnings.append(f"{path} must be >= {min_val}; using default")
        return current
    if max_val is not None and f > max_val:
        warnings.append(f"{path} must be <= {max_val}; using default")
        return current
    return f


def _parse_int(
    raw: dict, path: str, current: Any, warnings: list[str],
    *,
    min_val: int | None = None,
    max_val: int | None = None,
) -> Any:
    """Parse an integer field. Returns the value or default."""
    val = _get(raw, path, None)
    if val is None:
        return current
    if not isinstance(val, int):
        warnings.append(f"{path} must be an integer; using default")
        return current
    if min_val is not None and val < min_val:
        warnings.append(f"{path} must be >= {min_val}; using default")
        return current
    if max_val is not None and val > max_val:
        warnings.append(f"{path} must be <= {max_val}; using default")
        return current
    return val


def _parse_str_list(
    raw: dict, path: str, current: tuple[str, ...], warnings: list[str],
) -> tuple[str, ...]:
    """Parse a list-of-strings field (e.g. CORS origins)."""
    val = _get(raw, path, None)
    if val is None:
        return current
    if not isinstance(val, list):
        warnings.append(f"{path} must be a list; using default")
        return current
    out: list[str] = []
    for item in val:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    if not out:
        warnings.append(f"{path} must contain at least one non-empty string; using default")
        return current
    return tuple(out)


def _parse_candidates(
    raw: dict, warnings: list[str],
) -> tuple[AIRequestCandidate, ...]:
    """Parse the ai.candidates list into AIRequestCandidate objects."""
    ai_candidates = _get(raw, "ai.candidates", None)
    if ai_candidates is None:
        return ()
    if not isinstance(ai_candidates, list):
        warnings.append("ai.candidates must be a list; ignoring")
        return ()

    parsed: list[AIRequestCandidate] = []
    for i, item in enumerate(ai_candidates):
        if not isinstance(item, dict):
            warnings.append(f"ai.candidates[{i}] must be object; skipping")
            continue
        cid = item.get("id")
        if not isinstance(cid, str) or not cid.strip():
            warnings.append(f"ai.candidates[{i}].id must be non-empty string; skipping")
            continue

        # Validate each field inline
        temp = item.get("temperature", 0.2)
        if not isinstance(temp, (int, float)) or not (0.0 <= float(temp) <= 2.0):
            warnings.append(f"ai.candidates[{i}].temperature invalid; using 0.2")
            temp = 0.2

        max_tokens = item.get("max_tokens", 512)
        if not isinstance(max_tokens, int) or not (64 <= max_tokens <= 8192):
            warnings.append(f"ai.candidates[{i}].max_tokens invalid; using 512")
            max_tokens = 512

        timeout_s = item.get("timeout_s", 10.0)
        if not isinstance(timeout_s, (int, float)) or float(timeout_s) <= 0:
            warnings.append(f"ai.candidates[{i}].timeout_s invalid; using 10")
            timeout_s = 10.0

        max_retries = item.get("max_retries", 2)
        if not isinstance(max_retries, int) or not (0 <= max_retries <= 10):
            warnings.append(f"ai.candidates[{i}].max_retries invalid; using 2")
            max_retries = 2

        model = item.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            warnings.append(f"ai.candidates[{i}].model invalid; ignoring")
            model = None

        api_base2 = item.get("api_base")
        if api_base2 is not None and (not isinstance(api_base2, str) or not api_base2.strip()):
            warnings.append(f"ai.candidates[{i}].api_base invalid; ignoring")
            api_base2 = None

        parsed.append(AIRequestCandidate(
            id=cid.strip(),
            temperature=float(temp),
            max_tokens=int(max_tokens),
            timeout_s=float(timeout_s),
            max_retries=int(max_retries),
            model=model.strip() if isinstance(model, str) else None,
            api_base=api_base2.strip() if isinstance(api_base2, str) else None,
        ))

    return tuple(parsed)


# -- Main loader ----------------------------------------------------------
def load_app_config(
    path: str | Path = "energy_system/config/params.yaml",
) -> tuple[AppConfig, list[str]]:
    """Load and validate the application configuration from YAML.

    Returns:
        (AppConfig, warnings) — warnings is a list of human-readable strings
        describing any fields that were corrected to defaults.
    """
    p = Path(path)
    raw: dict = {}
    warnings: list[str] = []

    if not p.exists():
        warnings.append(f"Config file not found: {p}. Using defaults.")
    else:
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            warnings.append(f"Config file is empty: {p}. Using defaults.")
        else:
            try:
                raw = _as_dict(yaml.safe_load(text))
            except Exception as e:
                warnings.append(f"Failed to parse YAML ({p}): {e}. Using defaults.")
                raw = {}

    cfg = AppConfig()

    # -- app section --
    use_hw = _parse_bool(raw, "app.use_hardware", cfg.use_hardware, warnings)
    cfg = replace(cfg, use_hardware=use_hw)

    run_label = _parse_str(raw, "app.run_label", cfg.run_label, warnings, nonempty=True)
    cfg = replace(cfg, run_label=run_label)

    # -- serial section --
    port = _parse_str(raw, "serial.port", cfg.serial.port, warnings, nonempty=True)
    baudrate = _parse_int(raw, "serial.baudrate", cfg.serial.baudrate, warnings,
                          min_val=1200, max_val=921600)
    timeout_s = _parse_float(raw, "serial.timeout_s", cfg.serial.timeout_s, warnings, min_val=0.1)
    cfg = replace(cfg, serial=replace(cfg.serial, port=port, baudrate=baudrate, timeout_s=timeout_s))

    # -- thresholds section --
    illum = _parse_float(raw, "thresholds.illuminance_min", cfg.thresholds.illuminance_min,
                         warnings, min_val=0)
    cfg = replace(cfg, thresholds=replace(cfg.thresholds, illuminance_min=illum))

    # -- ai section --
    ai_enabled = _parse_bool(raw, "ai.enabled", cfg.ai.enabled, warnings)
    ai_mode = _parse_str(raw, "ai.control_mode", cfg.ai.control_mode, warnings,
                         choices=["suggest", "execute"])
    ai_model = _parse_str(raw, "ai.model", cfg.ai.model, warnings, nonempty=True)
    ai_base = _parse_str(raw, "ai.api_base", cfg.ai.api_base, warnings, nonempty=True)
    ai_explore = _parse_float(raw, "ai.exploration_rate", cfg.ai.exploration_rate, warnings,
                              min_val=0.0, max_val=1.0)
    ai_local = _parse_bool(raw, "ai.enable_local_fallback", cfg.ai.enable_local_fallback, warnings)
    ai_fb_r3 = _parse_bool(raw, "ai.fallback_enable_relay3", cfg.ai.fallback_enable_relay3, warnings)
    ai_fb_curtain = _parse_bool(raw, "ai.fallback_enable_curtain",
                                cfg.ai.fallback_enable_curtain, warnings)

    candidates = _parse_candidates(raw, warnings)
    cfg = replace(cfg, ai=replace(
        cfg.ai,
        enabled=ai_enabled,
        control_mode=ai_mode,
        model=ai_model,
        api_base=ai_base,
        candidates=candidates,
        exploration_rate=ai_explore,
        enable_local_fallback=ai_local,
        fallback_enable_relay3=ai_fb_r3,
        fallback_enable_curtain=ai_fb_curtain,
    ))

    # -- control section --
    enable_rule = _parse_bool(raw, "control.enable_rule_control",
                              cfg.control.enable_rule_control, warnings)
    min_interval = _parse_float(raw, "control.actuate_min_interval_s",
                                cfg.control.actuate_min_interval_s, warnings, min_val=0)
    stale_s = _parse_float(raw, "control.safe_mode_stale_s",
                           cfg.control.safe_mode_stale_s, warnings, min_val=0)
    max_ai_cmds = _parse_int(raw, "control.max_ai_cmds_per_cycle",
                             cfg.control.max_ai_cmds_per_cycle, warnings, min_val=0, max_val=50)
    cfg = replace(cfg, control=replace(
        cfg.control,
        enable_rule_control=enable_rule,
        actuate_min_interval_s=min_interval,
        safe_mode_stale_s=stale_s,
        max_ai_cmds_per_cycle=max_ai_cmds,
    ))

    # -- self_healing section --
    sh = cfg.self_healing
    sh_updates: dict[str, Any] = {}
    for field, parse_fn, args in [
        ("enabled", _parse_bool, ("self_healing.enabled", sh.enabled)),
        ("auto_i2c_recover", _parse_bool, ("self_healing.auto_i2c_recover", sh.auto_i2c_recover)),
        ("auto_reset", _parse_bool, ("self_healing.auto_reset", sh.auto_reset)),
        ("action_cooldown_s", _parse_float,
         ("self_healing.action_cooldown_s", sh.action_cooldown_s, 0.0, None)),
        ("reset_cooldown_s", _parse_float,
         ("self_healing.reset_cooldown_s", sh.reset_cooldown_s, 0.0, None)),
        ("max_resets_per_hour", _parse_int,
         ("self_healing.max_resets_per_hour", sh.max_resets_per_hour, 0, 100)),
        ("require_manual_for_actuator_cutoff", _parse_bool,
         ("self_healing.require_manual_for_actuator_cutoff",
          sh.require_manual_for_actuator_cutoff)),
    ]:
        if parse_fn is _parse_float:
            path, default, min_v, max_v = args
            sh_updates[field] = parse_fn(raw, path, default, warnings, min_val=min_v, max_val=max_v)
        elif parse_fn is _parse_int:
            path, default, min_v, max_v = args
            sh_updates[field] = parse_fn(raw, path, default, warnings, min_val=min_v, max_val=max_v)
        else:
            path, default = args
            sh_updates[field] = parse_fn(raw, path, default, warnings)

    cfg = replace(cfg, self_healing=replace(sh, **sh_updates))

    # -- api section --
    cors_origins = _parse_str_list(raw, "api.cors_origins", cfg.api.cors_origins, warnings)
    allow_credentials = _parse_bool(raw, "api.allow_credentials", cfg.api.allow_credentials, warnings)

    # Cross-field validation: credentials must never be allowed against a wildcard origin.
    if allow_credentials and "*" in cors_origins:
        warnings.append(
            "api.allow_credentials=true is incompatible with cors_origins containing '*'; "
            "disabling credentials."
        )
        allow_credentials = False

    cfg = replace(cfg, api=ApiConfig(cors_origins=cors_origins, allow_credentials=allow_credentials))

    return cfg, warnings

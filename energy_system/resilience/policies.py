"""Pure rate-limit and cooldown policies for self-healing.

Extracted from ``ResilienceOrchestrator`` so the cooldown / reset-limit rules
can be unit-tested without any orchestrator state or wall-clock sleep.
"""

from __future__ import annotations

RESET_HISTORY_WINDOW_S = 3600.0


def prune_reset_history(history: list[float], now: float, window_s: float = RESET_HISTORY_WINDOW_S) -> list[float]:
    """Drop reset timestamps older than ``window_s`` seconds."""
    cutoff = now - window_s
    return [t for t in history if t >= cutoff]


def can_act(last_action_ts: float | None, action_cooldown_s: float, now: float) -> bool:
    """True when enough time has elapsed since the last action (or never acted)."""
    if last_action_ts is None:
        return True
    return (now - last_action_ts) >= float(action_cooldown_s)


def can_auto_reset(
    *,
    auto_reset: bool,
    reset_history: list[float],
    max_resets_per_hour: int,
    last_action,
    last_action_ts: float | None,
    reset_cooldown_s: float,
    now: float,
) -> tuple[bool, str | None]:
    """Decide whether a soft reset may run automatically.

    Returns (allowed, reason_when_blocked). ``last_action`` is compared to
    "RESET" by string value, so both a plain string and the enum work.
    """
    if not auto_reset:
        return False, "auto_reset_disabled"

    pruned = prune_reset_history(reset_history, now)
    if len(pruned) >= int(max_resets_per_hour):
        return False, "reset_rate_limit_manual_required"

    if last_action_ts is not None and str(last_action) == "RESET":
        if now - last_action_ts < float(reset_cooldown_s):
            return False, "reset_cooldown"

    return True, None

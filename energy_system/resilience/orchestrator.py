from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from energy_system.config.runtime_config import AppConfig


@dataclass
class ResilienceAction:
    name: str  # e.g. I2C_RECOVER, RESET
    command: str
    requires_manual: bool = False
    reason: str | None = None


class ResilienceOrchestrator:
    """Minimal self-healing orchestrator (L1).

    Scope (Option B): allow firmware I2C recover + MCU soft reset.
    Dangerous actions (e.g., actuator power cut-off) are intentionally NOT automated.
    """

    def __init__(
        self,
        config: AppConfig,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self.config = config
        self._time = time_fn or time.monotonic

        self.breaker_state: str = "CLOSED"  # CLOSED|OPEN
        self.last_incident_id: str | None = None
        self.last_action: str | None = None
        self.last_action_reason: str | None = None
        self.last_action_ts: float | None = None

        self._incident_started_ts: float | None = None
        self._last_i2c_attempt_ts: float | None = None

        self._reset_history: list[float] = []  # monotonic timestamps

    def _new_incident_id(self) -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]

    def _prune_reset_history(self, now: float) -> None:
        one_hour_ago = now - 3600.0
        self._reset_history = [t for t in self._reset_history if t >= one_hour_ago]

    def _can_auto_reset(self, now: float) -> tuple[bool, str | None]:
        sh = self.config.self_healing
        if not sh.auto_reset:
            return False, "auto_reset_disabled"

        self._prune_reset_history(now)
        if len(self._reset_history) >= int(sh.max_resets_per_hour):
            return False, "reset_rate_limit_manual_required"

        if self.last_action_ts is not None and self.last_action == "RESET":
            if now - self.last_action_ts < float(sh.reset_cooldown_s):
                return False, "reset_cooldown"

        return True, None

    def _can_act(self, now: float) -> bool:
        sh = self.config.self_healing
        if self.last_action_ts is None:
            return True
        return (now - self.last_action_ts) >= float(sh.action_cooldown_s)

    def on_sample_ok(self) -> dict[str, Any]:
        """Called when we successfully received a valid sensor sample."""
        self.breaker_state = "CLOSED"
        # Recovery: close current incident window
        self.last_incident_id = None
        self._incident_started_ts = None
        self._last_i2c_attempt_ts = None
        return {
            "resilience_state": self.breaker_state,
            "incident_id": self.last_incident_id,
            "last_action": self.last_action,
            "last_action_reason": self.last_action_reason,
        }

    def plan_for_stale(self, stale_s: float) -> tuple[list[ResilienceAction], dict[str, Any]]:
        """Return (actions, event_summary).

        This does not execute anything; caller is responsible for dispatch and logging.
        """
        sh = self.config.self_healing
        now = self._time()

        # Default: no action
        if not sh.enabled:
            return [], {
                "resilience_state": self.breaker_state,
                "incident_id": self.last_incident_id,
                "note": "self_healing_disabled",
            }

        # Only start healing when stale is beyond configured safe_mode threshold
        trigger_s = float(self.config.control.safe_mode_stale_s)
        if stale_s < trigger_s:
            return [], {
                "resilience_state": self.breaker_state,
                "incident_id": self.last_incident_id,
                "note": "stale_below_trigger",
                "stale_s": stale_s,
            }

        if not self._can_act(now):
            return [], {
                "resilience_state": self.breaker_state,
                "incident_id": self.last_incident_id,
                "note": "action_cooldown",
                "stale_s": stale_s,
            }

        if self.last_incident_id is None:
            self.last_incident_id = self._new_incident_id()
            self._incident_started_ts = now

        actions: list[ResilienceAction] = []

        # Stage 1: try I2C recover first
        if sh.auto_i2c_recover and self._last_i2c_attempt_ts is None:
            actions.append(
                ResilienceAction(
                    name="I2C_RECOVER",
                    command="I2C_RECOVER",
                    requires_manual=False,
                    reason=f"stale_{stale_s:.1f}s",
                )
            )
        elif sh.auto_i2c_recover and self._last_i2c_attempt_ts is not None:
            # If we already tried I2C recover, allow RESET only after some time has passed.
            if now - self._last_i2c_attempt_ts >= float(sh.action_cooldown_s):
                can_reset, why_not = self._can_auto_reset(now)
                if can_reset:
                    actions.append(
                        ResilienceAction(
                            name="RESET",
                            command="RESET",
                            requires_manual=False,
                            reason=f"stale_{stale_s:.1f}s_after_i2c",
                        )
                    )
                elif why_not == "reset_rate_limit_manual_required":
                    actions.append(
                        ResilienceAction(
                            name="RESET",
                            command="RESET",
                            requires_manual=True,
                            reason=why_not,
                        )
                    )
        else:
            # If I2C recover is disabled, we may go straight to reset (still guarded).
            can_reset, why_not = self._can_auto_reset(now)
            if can_reset:
                actions.append(
                    ResilienceAction(
                        name="RESET",
                        command="RESET",
                        requires_manual=False,
                        reason=f"stale_{stale_s:.1f}s",
                    )
                )
            elif why_not == "reset_rate_limit_manual_required":
                actions.append(
                    ResilienceAction(
                        name="RESET",
                        command="RESET",
                        requires_manual=True,
                        reason=why_not,
                    )
                )

        if not actions:
            return [], {
                "resilience_state": self.breaker_state,
                "incident_id": self.last_incident_id,
                "note": "no_action_available",
                "stale_s": stale_s,
            }

        self.breaker_state = "OPEN"
        return actions, {
            "resilience_state": self.breaker_state,
            "incident_id": self.last_incident_id,
            "stale_s": stale_s,
        }

    def record_action_result(self, action: ResilienceAction, executed: bool, result: Any) -> dict[str, Any]:
        now = self._time()
        self.last_action = action.name
        self.last_action_reason = action.reason
        self.last_action_ts = now

        if action.name == "I2C_RECOVER" and executed:
            self._last_i2c_attempt_ts = now

        if action.name == "RESET" and executed:
            self._reset_history.append(now)
            self._prune_reset_history(now)

        return {
            "ts": datetime.now().isoformat(),
            "incident_id": self.last_incident_id,
            "action": action.name,
            "executed": bool(executed),
            "requires_manual": bool(action.requires_manual),
            "reason": action.reason,
            "result": result,
            "resilience_state": self.breaker_state,
        }

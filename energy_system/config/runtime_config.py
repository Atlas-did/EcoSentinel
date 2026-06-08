from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIRequestCandidate:
    id: str = "default"
    temperature: float = 0.2
    max_tokens: int = 512
    timeout_s: float = 10.0
    max_retries: int = 2
    model: str | None = None
    api_base: str | None = None


@dataclass(frozen=True)
class SerialConfig:
    port: str = "COM3"
    baudrate: int = 115200
    timeout_s: float = 2.0


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    control_mode: str = "suggest"  # suggest | execute
    model: str = "gpt-4o-mini"
    api_base: str = "https://api.openai.com/v1"

    # Multi-layer API + parameter pool
    candidates: tuple[AIRequestCandidate, ...] = ()
    exploration_rate: float = 0.2

    # Local degrade strategy
    enable_local_fallback: bool = True
    fallback_enable_relay3: bool = True
    fallback_enable_curtain: bool = True


@dataclass(frozen=True)
class Thresholds:
    illuminance_min: float = 300.0


@dataclass(frozen=True)
class ControlConfig:
    enable_rule_control: bool = True
    actuate_min_interval_s: float = 2.0
    safe_mode_stale_s: float = 30.0
    max_ai_cmds_per_cycle: int = 5


@dataclass(frozen=True)
class SelfHealingConfig:
    enabled: bool = True
    auto_i2c_recover: bool = True
    auto_reset: bool = True
    action_cooldown_s: float = 10.0
    reset_cooldown_s: float = 120.0
    max_resets_per_hour: int = 3
    require_manual_for_actuator_cutoff: bool = True


@dataclass(frozen=True)
class AppConfig:
    use_hardware: bool = False
    run_label: str = "saving"  # baseline | saving | other
    serial: SerialConfig = SerialConfig()
    ai: AIConfig = AIConfig()
    thresholds: Thresholds = Thresholds()
    control: ControlConfig = ControlConfig()
    self_healing: SelfHealingConfig = SelfHealingConfig()

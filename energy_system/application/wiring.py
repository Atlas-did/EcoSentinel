"""组装根（composition root）：只负责把对象图搭起来，不跑循环。

为什么单独一个模块（M4）：
- ``runtime.py`` 原先在 ``__init__`` 里同时做"装配 + 循环 + 自愈 + 落盘"，扇出 15 个内部依赖；
- 装配**本来就必须**认识具体适配器（``SerialBridge``、``EnvironmentGenerator``…），
  这是hexagonal 架构里组装根的正当职责 —— 与其把它当"待清除的债"，不如把它隔离成
  **一个文件**，并让分层门禁只豁免这一个文件（其余 ``application/*`` 仍禁止 import hardware）。

所有构造都保留原样（含日志文案与异常处理），仅改变位置。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from energy_system.application.ai_worker import AiWorker
from energy_system.application.decision import DecisionService
from energy_system.application.enrichment import TelemetryEnrichmentService
from energy_system.application.scheduler import Scheduler
from energy_system.config.env import battery_capacity_mah, battery_initial_soc
from energy_system.core.command_dispatcher import RuleActuationController
from energy_system.core.controller import RuleBasedController
from energy_system.core.data_acquisition import DataAcquisition
from energy_system.core.log_manager import LogManager
from energy_system.hardware.serial_bridge import SerialBridge
from energy_system.resilience.orchestrator import ResilienceOrchestrator
from energy_system.simulation.data_generator import EnvironmentGenerator
from energy_system.utils.logger import setup_logger

logger = setup_logger("Main")

#: AI 建议的最大时效（秒）：按**发起请求的时刻**计算，超过即丢弃、绝不执行。
#: 取 2× 循环周期（5s）：足够吸收一次慢调用，又不让控制决策基于陈旧快照。
AI_ADVICE_MAX_AGE_S = 10.0


@dataclass
class Services:
    """装配好的服务容器（运行期可变状态不在这里，见 ControlLoop）。"""

    use_hardware: bool
    run_label: str
    enable_ai: bool
    ai_control_mode: str

    serial_bridge: Any
    acquisition: Any
    ai_advisor: Any
    decision: Any
    ai_worker: Any
    enrichment: Any
    log_mgr: Any
    resilience: Any
    rule_controller: Any
    actuation: Any
    scheduler: Any
    start_mono: float


def _build_serial_bridge(config):
    if not bool(config.use_hardware):
        return None
    bridge = SerialBridge(
        port=config.serial.port,
        baudrate=int(config.serial.baudrate),
        timeout=float(config.serial.timeout_s),
    )
    if bridge.connect():
        logger.info("Hardware initialization successful.")
    else:
        logger.warning(
            "Hardware connection failed at startup; will keep retrying. "
            "Make sure no other process is holding the COM port."
        )
    return bridge


def _build_ai_advisor(config, api_key, enable_ai, ai_control_mode):
    if not enable_ai:
        logger.info("AI disabled by config.")
        return None
    try:
        from energy_system.algorithms.ai_advisor import AIAdvisor

        advisor = AIAdvisor(api_key=(api_key or ""), ai_config=config.ai)
        if api_key:
            logger.info(f"AI Advisor initialized (mode={ai_control_mode}).")
        else:
            logger.warning(
                "AI enabled but missing API key env: cloud calls disabled; "
                "using local fallback only."
            )
        return advisor
    except Exception as e:  # 配置或依赖问题不应阻止边缘侧继续跑规则控制
        logger.error(f"AI Advisor unavailable, disabled: {e}")
        return None


def build_services(config, api_key: str | None = None) -> Services:
    """按配置装配全部服务。纯构造，无循环、无阻塞。"""
    use_hardware = bool(config.use_hardware)
    run_label = (config.run_label or "saving").strip() or "saving"
    enable_ai = bool(config.ai.enabled)
    ai_control_mode = (config.ai.control_mode or "suggest").lower()
    if ai_control_mode not in {"suggest", "execute"}:
        ai_control_mode = "suggest"

    serial_bridge = _build_serial_bridge(config)

    acquisition = DataAcquisition(
        use_hardware=use_hardware,
        serial_bridge=serial_bridge,
        # 组装根注入合成数据源：core 不再反向依赖 simulation（test_layering.py）
        mock_generator=None if use_hardware else EnvironmentGenerator(seed=None),
    )

    ai_advisor = _build_ai_advisor(config, api_key, enable_ai, ai_control_mode)

    rule_controller = RuleBasedController(mode=run_label)
    actuation = RuleActuationController(
        serial_bridge=serial_bridge,
        rule_controller=rule_controller,
        actuate_min_interval_s=float(config.control.actuate_min_interval_s),
        illuminance_min=float(config.thresholds.illuminance_min),
        run_label=run_label,
    )

    enrichment = TelemetryEnrichmentService(
        battery_capacity_mah=battery_capacity_mah(),
        battery_initial_soc=battery_initial_soc(),
    )
    decision = DecisionService(
        ai_advisor,
        max_cmds_per_cycle=int(config.control.max_ai_cmds_per_cycle),
    )

    ai_worker = None
    if ai_advisor is not None:
        ai_worker = AiWorker(
            decide_fn=decision.decide,
            max_age_s=AI_ADVICE_MAX_AGE_S,
        )

    return Services(
        use_hardware=use_hardware,
        run_label=run_label,
        enable_ai=enable_ai,
        ai_control_mode=ai_control_mode,
        serial_bridge=serial_bridge,
        acquisition=acquisition,
        ai_advisor=ai_advisor,
        decision=decision,
        ai_worker=ai_worker,
        enrichment=enrichment,
        log_mgr=LogManager(run_label=run_label),
        resilience=ResilienceOrchestrator(config=config),
        rule_controller=rule_controller,
        actuation=actuation,
        scheduler=Scheduler(),
        start_mono=time.monotonic(),
    )

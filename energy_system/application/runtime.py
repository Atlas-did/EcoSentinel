"""Edge runtime —— 门面（M4 拆分后只剩接线）。

职责已委派：
- **装配** → ``application/wiring.py``（组装根，唯一认识具体适配器的地方）
- **用例** → ``application/usecases.py``（无数据/自愈/同步/AI 周期/落盘）
- **主回路** → ``application/loop.py``（节拍）

``EnergySystemApp`` 保留为对外门面：公开属性与拆分前**完全一致**
（``main.py`` re-export 它；测试直接替换 ``app.scheduler`` / ``app.ai_worker`` /
``app.acquisition`` / ``app.loop_interval_s`` 等）。
"""

from __future__ import annotations

from energy_system.application.loop import run_loop
from energy_system.application.wiring import AI_ADVICE_MAX_AGE_S, build_services

__all__ = ["AI_ADVICE_MAX_AGE_S", "EnergySystemApp"]


class EnergySystemApp:
    """控制回路门面（装配 → wiring，用例 → usecases，节拍 → loop）。"""

    def __init__(self, config, api_key: str | None = None):
        self.config = config
        services = build_services(config, api_key)

        # 公开属性保持与拆分前一致（main.py 再导出、测试直接改这些属性）
        self.use_hardware = services.use_hardware
        self.run_label = services.run_label
        self.enable_ai = services.enable_ai
        self.ai_control_mode = services.ai_control_mode

        self.serial_bridge = services.serial_bridge
        self.acquisition = services.acquisition
        self.ai_advisor = services.ai_advisor
        self.decision = services.decision
        self.ai_worker = services.ai_worker
        self.enrichment = services.enrichment
        self.log_mgr = services.log_mgr
        self.resilience = services.resilience
        self.rule_controller = services.rule_controller
        self.actuation = services.actuation
        self.scheduler = services.scheduler
        self._start_mono = services.start_mono

        # ── Resilience / self-healing 运行期状态 ───────────────────
        self.safe_mode = False
        self.safe_reason: str | None = None
        self._last_good_sample_mono: float | None = None
        self._last_ai_exec_mono: float = 0.0
        self._last_no_data_log_mono: float = 0.0

        # running flag
        self.system_running = True

        #: 循环周期（秒）。提成属性以便测试用短周期驱动（真实线程测试）。
        self.loop_interval_s = 5.0

    # ── main loop ──────────────────────────────────────────────────
    def run(self):
        """跑主回路（实现见 ``application/loop.py``）。"""
        run_loop(self)

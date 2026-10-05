"""G3 · 主回路延迟预算：AI 慢不得拖慢采集/控制节拍。

M2 之前：AI 与采集/控制同线程同步执行，10 秒的 AI 让虚拟 60 秒里只跑 7 轮，
且 `Loop overrun` 逐次累积 5→10→…→30s（循环越跑越落后、永不追回，Scheduler 只打印告警）。
M2 之后：AI 交给 `application/ai_worker.py`（非阻塞 + 时效），主回路保持节拍。

两条测试：
  1) 虚拟时钟 + ManualJobRunner ⇒ 确定性断言"节拍不塌陷、零 overrun"；
  2) 真实线程 + 短周期（0.05s）⇒ 端到端证明隔离性（余量约 10 倍，抗 CI 抖动）。
"""

import time
import unittest
from unittest.mock import patch

from energy_system.application import runtime as runtime_mod
from energy_system.application import wiring as wiring_mod
from energy_system.application.ai_worker import AiWorker, ManualJobRunner
from energy_system.application.decision import DecisionResult
from energy_system.application.runtime import EnergySystemApp
from energy_system.application.scheduler import Scheduler
from energy_system.config.config_loader import load_app_config
from energy_system.core.clock import FakeClock
import dataclasses
import logging

INTERVAL_S = 5.0
AI_DELAY_S = 10.0
BUDGET_S = 60.0
EXPECTED_TICKS = int(BUDGET_S / INTERVAL_S)  # 12

SAMPLE = {
    "temperature": 25.0,
    "humidity": 50.0,
    "illuminance": 300.0,
    "eco2": 600,
    "timestamp": "2026-01-01T00:00:00",
}


class _NullLogManager:
    """不落盘的日志桩：测试只关心节拍，不应写真实 logs/（也避开沙箱写权限）。"""

    def __init__(self, run_label="saving", **_kw):
        self.log_path = "unused.jsonl"
        self.samples = 0
        self.ai_rows = 0

    def log_sample(self, data):
        self.samples += 1
        if data.get("ai_reasoning") is not None:
            self.ai_rows += 1

    def log_incident(self, event):
        pass

    def update_daily_energy(self, data):
        pass


class _OverrunCounter(logging.Handler):
    def __init__(self):
        super().__init__()
        self.overruns = 0

    def emit(self, record):
        if "overrun" in record.getMessage().lower():
            self.overruns += 1


class _Acquisition:
    """每轮给一份数据；虚拟时间用完后请求停机，并按 ai_delay 让在途 AI 任务"算完"。"""

    def __init__(self, app, clock, budget, runner=None, ai_delay=None):
        self._app, self._clock, self._budget = app, clock, budget
        self._runner, self._ai_delay = runner, ai_delay
        self._next_ai_at = ai_delay if ai_delay else 0.0
        self.iterations = 0

    def read(self):
        now = self._clock.monotonic()
        if now >= self._budget:
            self._app.system_running = False
        self.iterations += 1
        if self._runner is not None and self._runner.pending and now >= self._next_ai_at:
            self._runner.run_all()  # "AI 此刻算完了"——注意它不占用主回路时间
            self._next_ai_at = now + self._ai_delay
        return dict(SAMPLE)


class _RealClock:
    def monotonic(self):
        return time.monotonic()


def _build_app():
    cfg, _warnings = load_app_config("no-such-config.json")
    cfg = dataclasses.replace(cfg, use_hardware=False, ai=dataclasses.replace(cfg.ai, enabled=False))
    return EnergySystemApp(cfg)


class TestLoopLatencyBudget(unittest.TestCase):
    def _run_virtual(self):
        clock = FakeClock(monotonic_start=0.0)
        runner = ManualJobRunner()
        calls = {"n": 0}

        def decide(_data):
            calls["n"] += 1
            return DecisionResult(reasoning="async-advice", commands=[])

        counter = _OverrunCounter()
        sched_logger = logging.getLogger("Scheduler")
        sched_logger.addHandler(counter)
        try:
            with patch.object(wiring_mod, "LogManager", _NullLogManager), patch.object(
                runtime_mod, "append_jsonl", lambda *a, **k: None
            ):
                app = _build_app()
                app.scheduler = Scheduler(monotonic=clock.monotonic, sleep=clock.advance)
                app.ai_worker = AiWorker(
                    decide_fn=decide,
                    runner=runner,
                    max_age_s=10.0,
                    monotonic=clock.monotonic,
                )
                acq = _Acquisition(app, clock, BUDGET_S, runner=runner, ai_delay=AI_DELAY_S)
                app.acquisition = acq
                real_time = runtime_mod.time
                with patch.object(real_time, "monotonic", clock.monotonic):
                    app.run()
                log = app.log_mgr
        finally:
            sched_logger.removeHandler(counter)
        return acq.iterations, counter.overruns, calls["n"], log

    def test_slow_ai_does_not_stall_the_control_loop(self):
        ticks, overruns, ai_calls, log = self._run_virtual()
        self.assertGreater(
            ai_calls, 0, "AI 未被调用 ⇒ 本测试无意义（防止假绿）"
        )
        self.assertGreaterEqual(
            ticks,
            EXPECTED_TICKS,
            "AI 慢 {:.0f}s 时虚拟 {:.0f}s 内只跑了 {} 轮（应 >= {}）"
            "⇒ AI 仍在主回路上阻塞采集/控制".format(
                AI_DELAY_S, BUDGET_S, ticks, EXPECTED_TICKS
            ),
        )
        self.assertEqual(overruns, 0, "出现 {} 次 Loop overrun ⇒ 节拍被 AI 拖垮".format(overruns))
        # 异步化不等于"把 AI 丢掉"：建议最终必须进入日志管线
        self.assertGreater(
            log.ai_rows, 0, "AI 建议从未落地 ⇒ 异步化把 AI 弄丢了"
        )


class TestRealThreads(unittest.TestCase):
    def test_slow_ai_with_real_threads_keeps_the_cadence(self):
        """端到端：真实线程 + 短周期。同步实现约 1-2 轮，异步实现约 20 轮。"""
        with patch.object(wiring_mod, "LogManager", _NullLogManager), patch.object(
            runtime_mod, "append_jsonl", lambda *a, **k: None
        ):
            app = _build_app()  # 必须在 patch 内构造：LogManager 的 __init__ 会碰文件系统
            app.loop_interval_s = 0.05
            app.ai_worker = AiWorker(
                decide_fn=lambda _d: (time.sleep(0.4), DecisionResult(reasoning="rt"))[1],
                max_age_s=30.0,
            )
            clock = _RealClock()
            acq = _Acquisition(app, clock, time.monotonic() + 1.0)
            app.acquisition = acq
            app.run()
        self.assertGreaterEqual(
            acq.iterations, 4, "真实线程下节拍塌陷（AI 未真正移出主回路）"
        )


if __name__ == "__main__":
    unittest.main()

"""Unit tests for the off-loop AI worker (deterministic, no real threads)."""

import unittest

from energy_system.application.ai_worker import AiWorker, ManualJobRunner
from energy_system.application.decision import DecisionResult


class _Clock:
    def __init__(self, start=1000.0):
        self.t = float(start)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += float(seconds)


class _Decider:
    """Records calls; optionally raises (to prove error containment)."""

    def __init__(self, raise_exc=None):
        self.calls = 0
        self.raise_exc = raise_exc

    def __call__(self, sensor_data):
        self.calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return DecisionResult(reasoning=f"advice-{self.calls}")


def _worker(decider, clock, max_age_s=10.0):
    runner = ManualJobRunner()
    worker = AiWorker(
        decide_fn=decider,
        runner=runner,
        max_age_s=max_age_s,
        monotonic=clock,
    )
    return worker, runner


class TestAiWorkerFreshness(unittest.TestCase):
    def test_poll_is_non_blocking_and_yields_advice_once_computed(self):
        clock, decider = _Clock(), _Decider()
        worker, runner = _worker(decider, clock)

        worker.submit({"temperature": 25.0})
        self.assertEqual(decider.calls, 0, "提交必须是异步的：任务还没跑")
        self.assertIsNone(worker.poll(clock()), "任务未完成时 poll 必须立刻返回 None")

        self.assertTrue(runner.run_next())  # 此刻"AI 算完了"
        advice = worker.poll(clock())
        self.assertIsNotNone(advice)
        self.assertEqual(advice.result.reasoning, "advice-1")
        self.assertIsNone(worker.poll(clock()), "建议只能被取回一次")

    def test_stale_advice_is_dropped_by_request_time(self):
        clock, decider = _Clock(), _Decider()
        worker, runner = _worker(decider, clock, max_age_s=10.0)

        worker.submit({"temperature": 25.0})  # requested_at = 1000.0
        clock.advance(12.0)  # AI 花了 12 秒 ⇒ 快照已过期
        runner.run_next()

        self.assertIsNone(worker.poll(clock()), "过期建议必须被丢弃")
        stats = worker.stats()
        self.assertEqual(stats["dropped_stale"], 1)
        self.assertEqual(stats["completed"], 1)

    def test_fresh_advice_just_under_the_limit_is_kept(self):
        clock, decider = _Clock(), _Decider()
        worker, runner = _worker(decider, clock, max_age_s=10.0)
        worker.submit({})
        clock.advance(9.5)
        runner.run_next()
        self.assertIsNotNone(worker.poll(clock()), "未过期(< max_age)的建议必须保留")


class TestAiWorkerBacklogAndErrors(unittest.TestCase):
    def test_newer_request_supersedes_the_pending_one(self):
        clock, decider = _Clock(), _Decider()
        worker, runner = _worker(decider, clock)

        worker.submit({"n": 1})  # 在途
        worker.submit({"n": 2})  # 进 1 槽信箱
        worker.submit({"n": 3})  # 顶掉 2
        self.assertEqual(worker.stats()["dropped_superseded"], 1)

        runner.run_all()  # 先跑在途的 1，再自动跑信箱里最新的 3（不积压）
        self.assertEqual(decider.calls, 2, "只应执行'在途的'与'最新的'，不执行被顶掉的")
        self.assertFalse(worker.stats()["in_flight"])

    def test_empty_mailbox_means_no_extra_job(self):
        clock, decider = _Clock(), _Decider()
        worker, runner = _worker(decider, clock)
        worker.submit({})
        runner.run_all()
        self.assertEqual(decider.calls, 1)
        self.assertEqual(worker.stats()["submitted"], 1)

    def test_ai_exception_is_contained(self):
        clock = _Clock()
        decider = _Decider(raise_exc=RuntimeError("network down"))
        worker, runner = _worker(decider, clock)

        worker.submit({})
        runner.run_next()  # 不得把异常抛给执行器/主回路

        self.assertIsNone(worker.poll(clock()))
        stats = worker.stats()
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(stats["completed"], 1)
        self.assertFalse(stats["in_flight"], "失败后仍须释放在途标记，否则再也提交不了")

    def test_worker_is_reusable_after_a_failure(self):
        clock, decider = _Clock(), _Decider(raise_exc=RuntimeError("boom"))
        worker, runner = _worker(decider, clock)
        worker.submit({})
        runner.run_next()

        decider.raise_exc = None  # 后端恢复
        worker.submit({})
        runner.run_next()
        self.assertIsNotNone(worker.poll(clock()), "恢复后必须还能拿到建议")


if __name__ == "__main__":
    unittest.main()

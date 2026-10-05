"""Off-loop AI worker: run the (network-bound) advisory call without blocking the loop.

Why this exists: the main loop used to call ``DecisionService.decide()`` inline
(``runtime.py``), so "AI worst-case latency × retries" **became** the loop period and
``Scheduler`` could only log the resulting overruns
(see ``tests/unit/test_loop_latency_budget.py``).

Guarantees:
  * ``submit`` / ``poll`` are non-blocking — the loop never waits for the AI;
  * at most one job in flight, and a newer request supersedes the pending one
    (1-slot mailbox), so a slow AI cannot build an unbounded backlog;
  * advice is aged against the **request** time, not the completion time: advice
    derived from a snapshot older than ``max_age_s`` is dropped and never executed;
  * an exception inside the AI path is contained (logged) and cannot kill the loop.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from energy_system.utils.logger import setup_logger

logger = setup_logger("AIWorker")


@dataclass(frozen=True)
class AiAdvice:
    """One AI result plus the snapshot instant it was based on (for staleness)."""

    result: Any
    requested_at: float
    completed_at: float

    def age_s(self, now: float) -> float:
        return now - self.requested_at


@dataclass(frozen=True)
class _Request:
    data: dict
    requested_at: float


class ThreadJobRunner:
    """Default runner: one daemon thread per job (worker keeps ≤1 job in flight)."""

    def submit(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=fn, daemon=True).start()

    def shutdown(self) -> None:
        return None


class ManualJobRunner:
    """Deterministic runner for tests/replay: jobs run only when told to."""

    def __init__(self) -> None:
        self.pending: list[Callable[[], None]] = []
        self.runs = 0

    def submit(self, fn: Callable[[], None]) -> None:
        self.pending.append(fn)

    def run_next(self) -> bool:
        if not self.pending:
            return False
        self.pending.pop(0)()
        self.runs += 1
        return True

    def run_all(self) -> int:
        n = 0
        while self.run_next():
            n += 1
        return n

    def shutdown(self) -> None:
        self.pending.clear()


class AiWorker:
    def __init__(
        self,
        decide_fn: Callable[[dict], Any],
        runner=None,
        max_age_s: float = 10.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._decide = decide_fn
        self._runner = runner if runner is not None else ThreadJobRunner()
        self._monotonic = monotonic
        self.max_age_s = float(max_age_s)

        self._lock = threading.Lock()
        self._request: _Request | None = None
        self._mailbox: _Request | None = None
        self._advice: AiAdvice | None = None

        self.submitted = 0
        self.completed = 0
        self.errors = 0
        self.dropped_superseded = 0
        self.dropped_stale = 0

    # ── loop side (never blocks) ───────────────────────────────────
    def submit(self, sensor_data: dict) -> None:
        """Ask for one AI computation; keep only the newest request pending."""
        req = _Request(data=dict(sensor_data), requested_at=self._monotonic())
        with self._lock:
            self.submitted += 1
            if self._request is not None:
                if self._mailbox is not None:
                    self.dropped_superseded += 1
                self._mailbox = req
                return
            self._request = req
        self._runner.submit(self._run)

    def poll(self, now: float) -> AiAdvice | None:
        """Return finished, still-fresh advice; None when nothing is ready."""
        with self._lock:
            advice, self._advice = self._advice, None
        if advice is None:
            return None
        age = advice.age_s(now)
        if age > self.max_age_s:
            with self._lock:
                self.dropped_stale += 1
            logger.warning(
                f"Dropped stale AI advice: snapshot was {age:.1f}s old (> {self.max_age_s:.1f}s)"
            )
            return None
        return advice

    def shutdown(self) -> None:
        with self._lock:
            self._mailbox = None
            self._request = None
        self._runner.shutdown()

    def stats(self) -> dict:
        with self._lock:
            return {
                "submitted": self.submitted,
                "completed": self.completed,
                "errors": self.errors,
                "dropped_superseded": self.dropped_superseded,
                "dropped_stale": self.dropped_stale,
                "in_flight": self._request is not None,
            }

    # ── runner side ────────────────────────────────────────────────
    def _run(self) -> None:
        """Executed by the runner; must never raise into the runner's thread."""
        with self._lock:
            req, self._request = self._request, None
        if req is None:
            return
        result = None
        try:
            result = self._decide(req.data)
        except Exception as exc:  # 隔离 AI 侧异常：主回路必须继续跑
            with self._lock:
                self.errors += 1
            logger.error(f"AI worker job failed (loop unaffected): {exc}")
        completed_at = self._monotonic()

        with self._lock:
            if result is not None:
                self._advice = AiAdvice(
                    result=result, requested_at=req.requested_at, completed_at=completed_at
                )
            self.completed += 1
            nxt, self._mailbox = self._mailbox, None
            if nxt is not None:
                self._request = nxt
        if nxt is not None:  # 信箱里还有更新的请求 ⇒ 立刻接着算，不积压
            self._runner.submit(self._run)

"""Per-candidate circuit breaker for the AI provider pool.

Mirrors the semantics previously inlined in ``AIAdvisor``: a candidate opens its
circuit after ``threshold`` consecutive failures and stays open for an
exponentially-backing-off window, with a half-open probe chosen by the caller
when every candidate is open.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CandidateStats:
    n: int = 0
    ema_score: float = 0.0
    success: int = 0
    fail: int = 0
    consecutive_fail: int = 0
    circuit_open_until: float = 0.0
    circuit_open_count: int = 0


class CircuitBreaker:
    def __init__(
        self,
        now_fn: Callable[[], float] | None = None,
        threshold: int = 2,
        base_open_s: float = 20.0,
        max_open_s: float = 600.0,
        ema_alpha: float = 0.2,
    ) -> None:
        self._now = now_fn or time.monotonic
        self.threshold = int(threshold)
        self.base_open_s = float(base_open_s)
        self.max_open_s = float(max_open_s)
        self.ema_alpha = float(ema_alpha)
        self._stats: dict[str, CandidateStats] = {}

    def stats(self, key: str) -> CandidateStats:
        return self._stats.setdefault(key, CandidateStats())

    def record(self, key: str, *, ok: bool, score: float | None = None) -> CandidateStats:
        st = self.stats(key)
        if ok:
            st.success += 1
            st.consecutive_fail = 0
            st.circuit_open_until = 0.0
            st.circuit_open_count = 0
        else:
            st.fail += 1
            st.consecutive_fail += 1
            if st.consecutive_fail >= self.threshold:
                open_s = min(
                    self.base_open_s * (2 ** min(st.circuit_open_count, 4)),
                    self.max_open_s,
                )
                st.circuit_open_until = self._now() + open_s
                st.circuit_open_count += 1

        if score is not None:
            st.n += 1
            a = self.ema_alpha
            st.ema_score = score if st.n == 1 else (a * score + (1 - a) * st.ema_score)
        return st

    def is_open(self, key: str) -> bool:
        st = self._stats.get(key)
        if not st:
            return False
        return st.circuit_open_until > self._now()

    def closed_keys(self, keys: list[str]) -> list[str]:
        return [k for k in keys if not self.is_open(k)]

    def seconds_until_closed(self, key: str) -> float:
        st = self._stats.get(key)
        if not st:
            return 0.0
        return max(0.0, st.circuit_open_until - self._now())

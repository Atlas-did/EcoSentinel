"""Experiment manifest: the reproducible conditions behind every result.

A manifest is the record that turns a set of numbers into defensible evidence —
experiment id, control mode, time bounds, hardware/simulator version, a config
hash, the raw JSONL path and the summary path. It is written alongside the result
so a reviewer can reproduce the run or trace a drift in the metric definition.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Sequence


@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    mode: str
    started_at: str | None = None
    ended_at: str | None = None
    device_version: str | None = None
    config_hash: str | None = None
    sampling_period_s: float | None = None
    raw_jsonl_path: str | None = None
    summary_path: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict (drops nothing)."""
        return asdict(self)


def config_hash(cfg: Any) -> str:
    """Deterministic hash over a config object's canonical JSON form.

    Accepts a dataclass (converted via ``asdict``) or a plain dict. Sorted-key
    JSON ensures field order and dataclass identity do not affect the hash.
    Returns the first 16 hex chars (stable and short enough to print in a
    report header).
    """
    obj = asdict(cfg) if hasattr(cfg, "__dataclass_fields__") else cfg
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_order(
    modes: Sequence[str],
    *,
    repeats: int = 1,
    shuffle: bool = False,
    seed: int | None = None,
) -> list[str]:
    """Return the run order for a baseline-vs-saving comparison.

    Defaults to a deterministic alternating order (``baseline, saving, baseline,
    saving, ...``). With ``shuffle=True`` the sequence is randomized using the
    given seed so the experiment is not biased by time-of-day / weather drift —
    still reproducible because the seed fixes the permutation.
    """
    seq = [m for _ in range(repeats) for m in modes]
    if shuffle:
        random.Random(seed).shuffle(seq)
    return seq


__all__ = ["ExperimentManifest", "build_order", "config_hash"]

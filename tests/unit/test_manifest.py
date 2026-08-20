"""Unit tests for the experiment manifest and config hashing."""

import unittest
from dataclasses import dataclass

from energy_system.experiments.manifest import (
    ExperimentManifest,
    build_order,
    config_hash,
)


@dataclass(frozen=True)
class _SampleConfig:
    mode: str = "saving"
    seed: int = 42
    threshold: float = 300.0


class TestExperimentManifest(unittest.TestCase):
    def test_to_dict_roundtrip(self):
        m = ExperimentManifest(
            experiment_id="e-1",
            mode="saving",
            config_hash="abc123",
            sampling_period_s=300.0,
        )
        d = m.to_dict()
        self.assertEqual(d["experiment_id"], "e-1")
        self.assertEqual(d["mode"], "saving")
        self.assertEqual(d["config_hash"], "abc123")
        self.assertEqual(d["sampling_period_s"], 300.0)
        self.assertIsNone(d["raw_jsonl_path"])


class TestConfigHash(unittest.TestCase):
    def test_dict_hash_is_deterministic(self):
        a = config_hash({"b": 2, "a": 1})
        b = config_hash({"a": 1, "b": 2})  # key order must not matter
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)

    def test_different_configs_differ(self):
        self.assertNotEqual(config_hash({"a": 1}), config_hash({"a": 2}))

    def test_dataclass_hash(self):
        self.assertEqual(config_hash(_SampleConfig()), config_hash(_SampleConfig()))
        self.assertNotEqual(config_hash(_SampleConfig(mode="baseline")), config_hash(_SampleConfig()))


class TestBuildOrder(unittest.TestCase):
    def test_default_alternates(self):
        self.assertEqual(
            build_order(["baseline", "saving"], repeats=2),
            ["baseline", "saving", "baseline", "saving"],
        )

    def test_shuffle_is_reproducible(self):
        modes = ["baseline", "saving"]
        a = build_order(modes, repeats=3, shuffle=True, seed=7)
        b = build_order(modes, repeats=3, shuffle=True, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(sorted(a), ["baseline", "baseline", "baseline", "saving", "saving", "saving"])


if __name__ == "__main__":
    unittest.main()

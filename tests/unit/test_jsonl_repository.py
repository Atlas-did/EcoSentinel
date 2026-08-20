"""Unit tests for the JSONL telemetry repository."""

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from energy_system.persistence.jsonl_repository import JsonlTelemetryRepository


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestJsonlTelemetryRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.repo = JsonlTelemetryRepository(self.dir, run_label="saving")

    def tearDown(self):
        self._tmp.cleanup()

    def _hardware(self, label="saving", lines=None):
        p = self.dir / f"hardware_{label}.jsonl"
        _write(p, lines or [])
        return p

    def test_read_all_counts_corrupt_lines(self):
        rows = [
            json.dumps({"timestamp": "2026-08-20T08:00:00", "temperature": 25.0}),
            "{not valid json",
            "[]",  # valid JSON but not a dict → corrupt
            json.dumps({"timestamp": "2026-08-20T08:05:00", "temperature": 25.5}),
        ]
        self._hardware(lines=rows)
        result = self.repo.read_all()
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.corrupt_records, 2)

    def test_read_all_missing_file(self):
        result = self.repo.read_all()
        self.assertEqual(result.rows, [])
        self.assertEqual(result.corrupt_records, 0)

    def test_latest_and_tail(self):
        lines = [json.dumps({"n": i}) for i in range(10)]
        self._hardware(lines=lines)
        self.assertEqual(self.repo.latest()["n"], 9)
        tail = self.repo.tail(n=3)
        self.assertEqual([r["n"] for r in tail.rows], [7, 8, 9])

    def test_read_since_filters_by_timestamp(self):
        now = datetime.now()
        recent = (now - timedelta(seconds=60)).isoformat()
        old = (now - timedelta(hours=2)).isoformat()
        self._hardware(lines=[
            json.dumps({"timestamp": old, "n": 0}),
            json.dumps({"timestamp": recent, "n": 1}),
            json.dumps({"n": 2}),  # no timestamp → kept (cannot be proven stale)
        ])
        result = self.repo.read_since(window_s=300)
        self.assertEqual([r["n"] for r in result.rows], [1, 2])

    def test_daily_summary_reads_todays_file(self):
        today = date.today().isoformat()
        p = self.dir / f"daily_energy_saving_{today}.json"
        p.write_text(json.dumps({"load_energy_wh": 1234.5}), encoding="utf-8")
        summary = self.repo.daily_summary()
        self.assertEqual(summary["load_energy_wh"], 1234.5)

    def test_daily_summary_missing(self):
        self.assertIsNone(self.repo.daily_summary())

    def test_incident_tail(self):
        lines = [json.dumps({"incident_id": f"inc-{i}"}) for i in range(5)]
        p = self.dir / "incidents_saving.jsonl"
        _write(p, lines)
        events = self.repo.incident_tail(n=2)
        self.assertEqual([e["incident_id"] for e in events], ["inc-3", "inc-4"])


if __name__ == "__main__":
    unittest.main()

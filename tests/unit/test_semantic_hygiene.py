"""回归测试：D2 / D4 / D6 / D9 四个语义缺陷的修复不得回潮。

这些都是「看起来能用、实际在对外宣称错误信息」的缺陷，
只有专门断言才能锁住（既有测试全部绿灯时它们也照样存在）。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from energy_system.core.command_dispatcher import _command_ok
from energy_system.persistence.jsonl_repository import JsonlTelemetryRepository


class TestD2FailedCommandIsNotCachedAsSuccess(unittest.TestCase):
    """D2：下发失败不得被当作已生效缓存下来。"""

    def test_ok_false_is_failure(self):
        self.assertFalse(_command_ok({"ok": False, "error": "not_connected"}))
        self.assertFalse(_command_ok({"ok": False, "error": "pyserial_not_installed"}))

    def test_ok_true_is_success(self):
        self.assertTrue(_command_ok({"ok": True}))

    def test_none_and_plain_bools_keep_working(self):
        # 注入用的 stub bridge 可能返回 None / True，不能因此判失败
        self.assertTrue(_command_ok(None))
        self.assertTrue(_command_ok(True))
        self.assertFalse(_command_ok(False))


class TestD9LabelCannotEscapeLogDir(unittest.TestCase):
    """D9：run_label 直接来自 HTTP 查询串，不得穿越目录。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = JsonlTelemetryRepository(Path(self._tmp.name), run_label="saving")

    def tearDown(self):
        self._tmp.cleanup()

    def test_normal_labels_ok(self):
        for label in ("saving", "baseline", "run-01", "a_b.c"):
            with self.subTest(label=label):
                path = self.repo._path(label)
                self.assertEqual(path.parent, Path(self._tmp.name))

    def test_traversal_labels_rejected(self):
        # 空串走 `label or run_label` 回退，属于有意行为，不在此列表
        for label in ("../../etc/passwd", "../secret", "a/b", "..", "x" * 65,
                      "a\\b", "a b"):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    self.repo._path(label)

    def test_has_log_rejects_too(self):
        with self.assertRaises(ValueError):
            self.repo.has_log("../../x")


class TestD6HealthDoesNotFabricate(unittest.TestCase):
    """D6：无来源的字段必须是 None，不能伪造 0 / False / 1.0。"""

    def test_schema_allows_null(self):
        from energy_system.api.schemas import Health

        h = Health()
        self.assertIsNone(h.retry_count)
        self.assertIsNone(h.stale_detected)
        self.assertIsNone(h.sampling_rate_hz)

    def test_no_data_health_is_honest(self):
        from unittest import mock

        from energy_system.api.services import ApiServices
        from energy_system.persistence.jsonl_repository import JsonlReadResult

        with tempfile.TemporaryDirectory() as td:
            repo = JsonlTelemetryRepository(Path(td), run_label="saving")
            cfg = mock.Mock()
            cfg.self_healing.enabled = False
            svc = ApiServices(repo, cfg)
            with mock.patch.object(repo, "tail", return_value=JsonlReadResult(rows=[], corrupt_records=0)):
                health = svc.health()
        # 没有任何数据时：这些全都必须是"未知"，不是具体值
        self.assertFalse(health.serial_connected)
        self.assertIsNone(health.sampling_rate_hz)
        self.assertIsNone(health.retry_count)
        self.assertIsNone(health.stale_detected)


class TestD4ComfortUnitIsConsistent(unittest.TestCase):
    """D4：comfort_score 在 snapshot 与 chart 必须是同一量纲 0..1。"""

    def test_chart_and_snapshot_agree(self):
        from unittest import mock

        from energy_system.api.schemas import ChartPoint
        from energy_system.persistence.jsonl_repository import JsonlReadResult

        recent = (datetime.now() - timedelta(minutes=1)).isoformat()
        row = {"timestamp": recent, "temperature": 24.0, "comfort_score": 0.78}
        with tempfile.TemporaryDirectory() as td:
            repo = JsonlTelemetryRepository(Path(td), run_label="saving")
            cfg = mock.Mock()
            from energy_system.api.services import ApiServices

            svc = ApiServices(repo, cfg)
            with mock.patch.object(repo, "read_since",
                                   return_value=JsonlReadResult(rows=[row], corrupt_records=0)):
                points = svc.chart(range_="1h")
            with mock.patch.object(repo, "has_log", return_value=True), \
                 mock.patch.object(repo, "latest", return_value=row):
                snap = svc.snapshot()

        self.assertIsInstance(points[0], ChartPoint)
        self.assertEqual(points[0].comfort_score, 0.78)
        self.assertEqual(snap.comfort_score, 0.78)
        self.assertEqual(points[0].comfort_score, snap.comfort_score,
                         "chart 与 snapshot 的 comfort_score 必须同量纲")


if __name__ == "__main__":
    unittest.main()

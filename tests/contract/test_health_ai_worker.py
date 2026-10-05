"""评审 P1：`/api/health` 需暴露 AI 工作线程计数。

为什么值得一条门禁：AI 建议"为什么没被采纳"此前只能靠翻日志猜
（`AI_ADVICE_MAX_AGE_S` 偏小 ⇒ 建议成批过期丢弃；worker 报错 ⇒ 静默无建议）。
三条性质：
1) 接上注入口 ⇒ `/api/health` 里能读到计数
2) **未接线 ⇒ 字段为 null，不得伪造数字**（与项目"绝不伪造读数"的一贯口径一致）
3) 注入口抛异常 ⇒ health 仍然 200（监控端点不能被被监控对象拖死）
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from energy_system.api.app import create_app

STATS = {
    "submitted": 7,
    "completed": 5,
    "errors": 1,
    "dropped_superseded": 0,
    "dropped_stale": 1,
    "in_flight": False,
}


class TestHealthExposesAiWorkerStats(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_ai_worker_counters_appear_in_health(self):
        app = create_app(log_dir=self.log_dir, ai_worker_stats=lambda: STATS)
        body = TestClient(app).get("/api/health").json()
        self.assertEqual(body["ai_worker"], STATS)

    def test_without_the_hook_the_field_is_null_not_fabricated(self):
        app = create_app(log_dir=self.log_dir)
        body = TestClient(app).get("/api/health").json()
        self.assertIn("ai_worker", body, "Health 模型必须声明该字段（可加字段，不破坏旧前端）")
        self.assertIsNone(body["ai_worker"], "未接线时必须为 null，不得伪造计数")

    def test_broken_hook_does_not_take_down_health(self):
        def boom():
            raise RuntimeError("worker gone")

        app = create_app(log_dir=self.log_dir, ai_worker_stats=boom)
        resp = TestClient(app).get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["ai_worker"])


if __name__ == "__main__":
    unittest.main()

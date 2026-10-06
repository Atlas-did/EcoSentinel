"""`/api/health` 暴露"当前参数假设"的门禁（用户任务 ②）。

为什么值得一条门禁：前端要能显示"现在跑的是哪套假设、它有没有热惯性"。
★ 关键语义：`demo` 集**必然不满足** θ>0.9 ⇒ 健康检查必须**如实报 `meets_inertia_constraint=false`**，
既不报错也不隐藏（若这里改成调用会抛错的 `check_parameter_set()`，监控端点就会 500）。

覆盖边界：只验 health 的字段与容错；不验参数集的物理（见 test_parameter_sets / test_thermal_model_params）。
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from energy_system.api.app import create_app
from energy_system.config.settings import check_parameter_set, describe_parameter_set

INJECTED = {
    "name": "realistic",
    "UA_w_per_k": 150.0,
    "C_j_per_k": 430000.0,
    "tau_s": 2866.7,
    "theta": 0.9006,
    "min_tau_s": 2847.0,
    "meets_inertia_constraint": True,
    "source": "测试注入值",
}


class TestHealthExposesAssumptions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_default_path_reports_the_active_set_honestly(self):
        """不注入 ⇒ 直接读当前 settings，并**如实报告 demo 不满足惯性约束**。"""
        body = TestClient(create_app(log_dir=self.log_dir)).get("/api/health").json()
        info = body["assumptions"]
        self.assertIsNotNone(info)
        for key in ("name", "tau_s", "theta", "UA_w_per_k", "C_j_per_k", "source",
                    "meets_inertia_constraint"):
            self.assertIn(key, info)
        self.assertEqual(info["name"], "demo")
        self.assertIs(info["meets_inertia_constraint"], False)
        self.assertLess(info["theta"], 1e-9)
        self.assertAlmostEqual(info["tau_s"], 13.889, delta=0.01)

    def test_check_parameter_set_still_raises_for_demo(self):
        """重构没有削弱校验：会抛错的那个入口对 demo **仍然抛错**。"""
        with self.assertRaises(ValueError):
            check_parameter_set("demo")
        self.assertGreater(describe_parameter_set("realistic")["theta"], 0.9)

    def test_injected_value_wins(self):
        app = create_app(log_dir=self.log_dir, parameter_set_info=lambda: INJECTED)
        body = TestClient(app).get("/api/health").json()
        self.assertEqual(body["assumptions"], INJECTED)

    def test_injection_failure_keeps_health_at_200(self):
        """注入抛异常 ⇒ health 仍 200、字段为 null（监控端点不能被被监控对象拖死）。"""
        def boom():
            raise RuntimeError("probe failed")

        app = create_app(log_dir=self.log_dir, parameter_set_info=boom)
        response = TestClient(app).get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["assumptions"])


if __name__ == "__main__":
    unittest.main()

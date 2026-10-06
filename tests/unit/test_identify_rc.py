"""参数辨识脚本的门禁：自检 / 精确复原 / 共线拒答 / 输入校验。

为什么值得一条门禁：这个脚本将来会用**真机数据**算出 `UA`/`C`，而这两个数一旦被写进
`settings.py` 就会改动对外节能率口径。它出错的代价极高（"看起来很科学的错数字"），
所以：
- 自检必须 PASS（验代数）；
- 用**已知真值**的合成数据必须复原到容差内；
- **稳态数据必须被拒答**（此时 C 不可辨识 —— 本脚本第一版就在这上面栽过：拟出 C=544533）；
- 记录约定的 off-by-one 必须被钉死（第一版把 Q 列错位一拍 ⇒ UA 偏 +3.8%、R² 掉到 0.989）。
"""

import math
import unittest

from scripts.identify_rc import SECONDS_PER_DAY, fit_rc, main  # noqa: F401  (SECONDS_PER_DAY 供阅读)


def _exact_rows(truth_ua: float, truth_c: float, dt: float, n: int) -> list[dict]:
    """按脚本规定的**记录约定**生成数据：本行的 T_out/Q 配它之后的那个区间。"""
    t_out, t_in = 32.0, 24.0
    rows = []
    for k in range(n):
        q = 1200.0 if (k // 60) % 2 == 0 else 200.0
        rows.append({"time_s": k * dt, "T_in": t_in, "T_out": t_out, "Q_w": q})
        t_inf = t_out + q / truth_ua
        t_in = t_inf + (t_in - t_inf) * math.exp(-truth_ua * dt / truth_c)
    return rows


class TestIdentifyRc(unittest.TestCase):
    def test_selftest_passes(self):
        self.assertEqual(main(["--selftest"]), 0)

    def test_exact_recovery_when_dt_is_far_below_tau(self):
        """Δt=0.1s、τ=13.9s（Δt/τ≈0.007）⇒ 线性化偏倚 ≈0.4% ⇒ 两个参数都应复原。"""
        fit = fit_rc(_exact_rows(1800.0, 25000.0, 0.1, 4000), dt=0.1)
        self.assertAlmostEqual(fit["UA_w_per_k"], 1800.0, delta=1800.0 * 0.01)
        self.assertAlmostEqual(fit["C_j_per_k"], 25000.0, delta=25000.0 * 0.01)
        self.assertGreater(fit["r2"], 0.999)

    def test_ua_survives_moderate_dt_but_c_carries_known_bias(self):
        """Δt/τ≈0.036 时：UA 无偏（比值抵消），C 有 ≈Δt/(2τ)≈1.8% 的**已知**偏倚。"""
        fit = fit_rc(_exact_rows(1800.0, 25000.0, 0.5, 2400), dt=0.5)
        self.assertAlmostEqual(fit["UA_w_per_k"], 1800.0, delta=1800.0 * 0.005)
        self.assertGreater(fit["C_j_per_k"], 25000.0)          # 已知偏大，不是随机误差
        self.assertLess(fit["C_j_per_k"], 25000.0 * 1.03)

    def test_steady_state_data_is_rejected(self):
        """稳态/无激励数据（Q 恒为 0）⇒ 设计矩阵退化 ⇒ 必须拒答，而不是给个错数。

        第一版用例我用了"正弦 Q + 300s 步长"，结果共线程度不够、**测试自己没红** ——
        改用**确定性退化**数据（Q 恒 0）才真正钉住这条守卫。
        """
        dt = 300.0
        rows = [
            {"time_s": k * dt, "T_in": 24.0, "T_out": 32.0, "Q_w": 0.0}
            for k in range(50)
        ]
        with self.assertRaises(ValueError) as ctx:
            fit_rc(rows, dt=dt)
        self.assertTrue(
            ("共线" in str(ctx.exception)) or ("退化" in str(ctx.exception)),
            f"拒答消息应说明是共线/退化，实为：{ctx.exception}",
        )

    def test_non_positive_solution_is_rejected(self):
        """★ 队友审计指出的缺口：原实现只有 `|b|<1e-12` 的退化守卫 ⇒ 负热容会**通过**。

        这里直接构造"ΔT 随 Q 增大而下降"的数据（等价于负热容），要求脚本**拒答**而非返回非物理值。
        rcmodel 用 logit 把参数约束在正数域（helper_functions.py:105）；本脚本用显式拒答等价实现。
        """
        rows = []
        t_in = 24.0
        for k in range(400):
            t_out = 30.0 + 2.0 * math.sin(k / 7.0)          # 室外有变化 ⇒ 不与 Q 共线
            q = 300.0 + 200.0 * math.sin(k / 5.0 + 1.0)
            rows.append({"time_s": k * 10.0, "T_in": t_in, "T_out": t_out, "Q_w": q})
            t_in += 1e-3 * (t_out - t_in) * 10.0 - 1e-5 * q * 10.0   # 人为的"负热容"响应
        with self.assertRaises(ValueError) as ctx:
            fit_rc(rows, dt=10.0)
        self.assertIn("非正", str(ctx.exception))

    def test_too_few_rows_is_reported_as_input_error(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tiny.csv"
            path.write_text("time_s,T_in,T_out,Q_w\n0,24,32,550\n300,24.5,32,550\n", encoding="utf-8")
            self.assertEqual(main(["--input", str(path)]), 1)


if __name__ == "__main__":
    unittest.main()

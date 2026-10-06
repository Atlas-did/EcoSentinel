"""IPMVP Option C：ASO 交替实验 + 回归 baseline（评审 §6.4）。

## 为什么需要它

现在的 `compare` 是"先把 baseline 跑 3 天、再把 saving 跑 3 天"，属**两次不同模式的仿真对比**：
接近 IPMVP Option D，但模型未校准，**严格说不成立**；且 IPMVP 明确要求 baseline 与报告期覆盖完整工况。

## ASO 的做法（本项目按天交替）

在同一段**连续**仿真里交替开关节能策略："关"的时段当 **baseline**、"开"的时段当**报告期**；
再用**室外温度为自变量**的回归模型（本项目用线性/变点）把 baseline 外推到报告期的工况，
最后比较「回归预测的 baseline」与「实测报告期能耗」。

## 重要口径约束

- 本模块只做**方法学**，不改物理参数（`A_WALL/U_WALL/C_AIR` 仍是演示级未标定值）。
- 仿真时长比 `compare` 长（需要足够的 baseline/报告期样本），且**未覆盖全工况** ⇒
  对外只能说"内部一致性参考"，必须带口径，不能与文献实测值同表比较。
- 与 `compare` 的"配对差值"是两个**不同估计量**：不要混用、不要取平均，各自标注方法。
"""

from __future__ import annotations

import math
from typing import Any, Callable

from energy_system.config import settings
from energy_system.simulation.simulator import Simulator

SECONDS_PER_DAY = 24 * 3600


def daily_alternating_schedule(period_days: int = 1) -> Callable[[float], str]:
    """返回 ASO 调度：每 `period_days` 天在同一段仿真里切换 baseline / saving。"""

    if period_days < 1:
        raise ValueError("period_days 必须 >= 1")

    def schedule(t_seconds: float) -> str:
        block = int(t_seconds // (SECONDS_PER_DAY * period_days))
        return "saving" if block % 2 == 1 else "baseline"

    return schedule


def _daily_aggregates(history: dict[str, Any]) -> list[dict[str, Any]]:
    """把逐步历史聚合成**逐日**样本：日能耗 kWh + 日均室外温度 + 该日主导模式。"""
    dt = settings.TIME_STEP
    steps_per_day = max(1, int(SECONDS_PER_DAY / dt))
    days: list[dict[str, Any]] = []

    power = history["power_total"]
    t_out = history["T_out"]
    modes = history.get("mode") or []

    for start in range(0, len(power), steps_per_day):
        chunk_power = power[start : start + steps_per_day]
        if not chunk_power:
            continue
        chunk_t = t_out[start : start + steps_per_day]
        chunk_mode = modes[start : start + steps_per_day]
        saving_steps = sum(1 for m in chunk_mode if m == "saving")
        days.append(
            {
                "kwh": sum(chunk_power) * dt / 3_600_000.0,
                "t_out_mean": sum(chunk_t) / len(chunk_t),
                "mode": "saving" if saving_steps > len(chunk_mode) / 2 else "baseline",
            }
        )
    return days


def _fit_linear(xs: list[float], ys: list[float]) -> dict[str, float]:
    """最小二乘 y = a + b·x（手写，避免引入 numpy 依赖），并给出 R² 与残差标准差。"""
    n = len(xs)
    if n < 2:
        raise ValueError(f"回归需要至少 2 个 baseline 日样本，实得 {n}")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0.0:
        raise ValueError("室外温度无变化，无法回归（请加长仿真或换工况）")
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = mean_y - b * mean_x
    residuals = [y - (a + b * x) for x, y in zip(xs, ys)]
    ss_res = sum(r * r for r in residuals)
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    resid_std = math.sqrt(ss_res / max(1, n - 2)) if n > 2 else 0.0
    return {
        "a": a,
        "b": b,
        "r2": (1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0,
        "resid_std": resid_std,
        "n": float(n),
    }


def run_aso_experiment(days: int = 6, seed: int = 42, period_days: int = 1) -> dict[str, Any]:
    """跑一次 ASO 交替实验并按 IPMVP Option C 估算节能量。

    返回结构化报告；`savings_percent` 是"回归预测 baseline vs 实测报告期"的估计量
    （与 `compare` 的配对差值**不是**同一个数，二者不可混用）。
    """
    if days % (2 * period_days) != 0:
        raise ValueError("days 必须是 2*period_days 的整数倍，才能保证 baseline/报告期成对")

    history = Simulator(
        mode="baseline", seed=seed, mode_schedule=daily_alternating_schedule(period_days)
    ).run_simulation(days=days)
    daily = _daily_aggregates(history)

    base = [d for d in daily if d["mode"] == "baseline"]
    report = [d for d in daily if d["mode"] == "saving"]
    if len(base) < 2 or not report:
        raise ValueError(f"样本不足：baseline {len(base)} 天 / 报告期 {len(report)} 天")

    fit = _fit_linear([d["t_out_mean"] for d in base], [d["kwh"] for d in base])
    predicted_baseline = sum(fit["a"] + fit["b"] * d["t_out_mean"] for d in report)
    actual = sum(d["kwh"] for d in report)
    savings_kwh = predicted_baseline - actual
    savings_pct = (savings_kwh / predicted_baseline * 100.0) if predicted_baseline else 0.0
    # 简化不确定度：以回归残差标准差按报告期天数聚合（95% 近似）
    ci95 = 1.96 * fit["resid_std"] * math.sqrt(len(report))

    return {
        "schema_version": "1.0",
        "method": "IPMVP Option C (ASO alternating) + outdoor-temperature regression baseline",
        "days": days,
        "period_days": period_days,
        "seed": seed,
        "baseline_days": len(base),
        "report_days": len(report),
        "regression": {k: round(v, 4) for k, v in fit.items()},
        "predicted_baseline_kwh": round(predicted_baseline, 3),
        "actual_report_kwh": round(actual, 3),
        "savings_kwh": round(savings_kwh, 3),
        "savings_percent": round(savings_pct, 2),
        "savings_ci95_kwh": round(ci95, 3),
        "caveat": (
            f"{days} 天数字孪生仿真、未覆盖全工况；建筑参数为演示级未标定值 ⇒ "
            "只作内部一致性参考，不可与实测/文献值同表比较"
        ),
    }


if __name__ == "__main__":  # pragma: no cover —— 便于人工查看
    import json

    print(json.dumps(run_aso_experiment(), ensure_ascii=False, indent=2))

"""舒适度 KPI：**越界量的时间积分**（BOPTEST 的 core KPI 范式）+ 分项报告。

## 出处（不是我发明的口径）

BOPTEST `kpis/kpi_calculator.py:237-287` 的热不舒适计算：

```python
dT_lower = LowerSetp - data ;  dT_lower[dT_lower < 0] = 0   # 只惩罚低于下限的部分
dT_upper = data - UpperSetp ;  dT_upper[dT_upper < 0] = 0   # 只惩罚高于上限的部分
tdis_dict[...] += np.trapezoid(dT_lower, time) / 3600.      # 单位 K·h
```

**为什么不是"算术平均评分"**（BOPTEST 范式 + 队友审计的 IPMVP 口径共同指向同一结论）：
截断到 [0,1] 的评分取平均，对**偏离持续时间完全不敏感** —— 偏 0.1 K 持续三天与偏 5 K 持续十分钟
可以有同样的均值；而积分形式**同时编码"偏离多少"与"偏离多久"**。本项目对外因此用两个并列口径：
`time_in_band_share`（IPMVP 原生"带内时间占比"）与本模块的**越界积分**。

## 分项报告（来自 rl-testbed 的 reward 分解范式）

rl-testbed 的 reward 返回 5 元组并把每一项单独记录/画图（
`..._Temp_Fan.py:242`、`:321-343`）—— 目的就是"能看出策略靠哪一项赢"。本模块把越界拆成
**温度 / 湿度 / 照度**三项分别积分、分别报告，于是"节能是不是牺牲舒适换的"可以归因到具体项。

## 三种区间及其来源（每个都必须有出处，不许拍脑袋）

| 项 | 区间 | 来源 |
|---|---|---|
| 温度 | **[23, 26] ℃** | ISO 7730（PMV ∈ ±0.5 数值解 ≈23–26.5）与 Sinergym `range_comfort_summer=(23.0,26.0)` 双来源一致 |
| 相对湿度 | **[30, 60] %** | ISO 7730 / ASHRAE 55 的常见舒适湿度带（**作为公开假设写在 assumptions 里**，不是测量值） |
| 照度下限 | `settings.COMFORT_ILLUMINANCE_MIN` | **本仓既有配置**（`core/controller.py:140` 已在用），不自造 |
"""

from __future__ import annotations

from typing import Iterable, Sequence

from energy_system.config import settings

TEMP_BAND_C = (23.0, 26.0)
RH_BAND_PERCENT = (30.0, 60.0)
DEFAULT_DT_S = 300.0


def _clean(values: Iterable[float | None]) -> list[float]:
    """去掉 None/NaN（不计入分母，也不产生 NaN）。"""
    out: list[float] = []
    for value in values:
        if value is None:
            continue
        f = float(value)
        if f == f:  # NaN 检查（不用 math，避免额外导入）
            out.append(f)
    return out


def violation_integral(values: Sequence[float | None], lower: float, upper: float,
                       dt_s: float = DEFAULT_DT_S) -> float:
    """越界量的时间积分：区间内为 0，越界取**正的**偏离量，按梯形法积分。

    单位 = 被测量的单位 × 小时（温度 ⇒ K·h；湿度 ⇒ %·h；照度 ⇒ lx·h）。

    - 与 BOPTEST 一致：**上下界分别取正**，越界外为 0（`:269-272`）；
    - 用**梯形法**而非简单求和（同 `np.trapezoid`），端点只算一半；
    - `lower > upper` 或 `dt_s <= 0` 视为调用错误（抛 `ValueError`），不静默返回 0。
    """
    if lower > upper:
        raise ValueError(f"区间上下界反了：lower={lower} > upper={upper}")
    if dt_s <= 0:
        raise ValueError(f"dt_s 必须为正，实得 {dt_s}")
    series = _clean(values)
    if len(series) < 2:
        return 0.0

    deviations = [
        0.0 if lower <= v <= upper else (lower - v if v < lower else v - upper)
        for v in series
    ]
    # 梯形积分（等间隔 dt_s）→ 秒；再 /3600 转小时 ⇒ 单位·h
    area_s = dt_s * (sum(deviations) - 0.5 * (deviations[0] + deviations[-1]))
    return area_s / 3600.0


def comfort_kpi_breakdown(
    t_in: Sequence[float | None],
    humidity: Sequence[float | None] | None = None,
    illuminance: Sequence[float | None] | None = None,
    dt_s: float = DEFAULT_DT_S,
    temp_band: tuple[float, float] = TEMP_BAND_C,
    rh_band: tuple[float, float] = RH_BAND_PERCENT,
    lux_min: float | None = None,
) -> dict:
    """把舒适越界拆成三项分别积分，并把口径假设一并返回（便于写进报告）。"""
    from energy_system.algorithms.comfort_eval import time_in_band_share

    lux_floor = float(settings.COMFORT_ILLUMINANCE_MIN) if lux_min is None else float(lux_min)
    out: dict = {
        "temp_violation_kh": round(violation_integral(t_in, temp_band[0], temp_band[1], dt_s), 4),
        "band_share": round(time_in_band_share(t_in, low=temp_band[0], high=temp_band[1]), 4),
        "assumptions": {
            "temp_band_c": list(temp_band),
            "temp_band_source": "ISO 7730 (PMV±0.5 ≈23–26.5 ℃) 与 Sinergym range_comfort_summer 一致",
            "rh_band_percent": list(rh_band),
            "rh_band_source": "ISO 7730 / ASHRAE 55 常见舒适湿度带（公开假设，非实测）",
            "lux_min": lux_floor,
            "lux_min_source": "本仓 config settings.COMFORT_ILLUMINANCE_MIN",
            "dt_s": dt_s,
            "unit": "越界量的时间积分：温度 K·h、湿度 %·h、照度 lx·h",
        },
    }
    if humidity is not None:
        out["humidity_violation_rh_h"] = round(
            violation_integral(humidity, rh_band[0], rh_band[1], dt_s), 4
        )
    if illuminance is not None:
        # 照度是"不足"型：低于下限才是问题 ⇒ 用 (lux_min, +inf) 表达"越高越好"
        out["illuminance_violation_lx_h"] = round(
            violation_integral(illuminance, lux_floor, float("inf"), dt_s), 4
        )
    return out

"""峰值功率 KPI：**先按 15 分钟重采样取均值，再取 max**（BOPTEST 范式）。

## 出处与"为什么反直觉但正确"

BOPTEST `kpis/kpi_calculator.py:372-417`：

```python
df.resample('15T').mean() / area / 1000.      # 再 .idxmax()
```

直觉上"峰值 = 最大值"。但本项目步长 300 s，**单点最大功率是步长/求解器的产物**，不是电网侧的真实
冲击；15 分钟是需求侧计量（demand meter）的行业窗口口径。⇒ **先降采样再取极值 = 主动丢弃伪信号**。
因此本模块同时返回 `raw_max_kw`（未降采样的单点最大），让报告可以**并列展示两者**并说明差异，
而不是偷偷替换掉原来的数字。

面积归一（`peak_w_per_m2`）需要建筑面积：本仓 `settings.FLOOR_AREA_M2` 已声明（来源为本文件已有的
"50m² 办公室"假设；见该常量注释）。未声明时返回 `None` —— **不猜**。
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

DEFAULT_DT_S = 300.0
DEFAULT_WINDOW_S = 15 * 60.0


def _clean(values: Iterable[float | None]) -> list[float]:
    out: list[float] = []
    for value in values:
        if value is None:
            continue
        f = float(value)
        if f == f:
            out.append(f)
    return out


def _window_means(series: Sequence[float], dt_s: float, window_s: float) -> list[float]:
    """按固定时长窗口（**时间**窗口，不是固定点数）求均值，尾部不完整窗口也计入。"""
    if window_s < dt_s:
        raise ValueError(f"window_s({window_s}) 不得小于 dt_s({dt_s})")
    steps = max(1, int(round(window_s / dt_s)))
    return [
        sum(series[i:i + steps]) / len(series[i:i + steps])
        for i in range(0, len(series), steps)
        if series[i:i + steps]
    ]


def peak_power_15min_kw(
    power_w: Sequence[float | None],
    dt_s: float = DEFAULT_DT_S,
    window_s: float = DEFAULT_WINDOW_S,
    area_m2: float | None = None,
) -> dict:
    """返回窗口均值峰值（kW）、未降采样单点最大（kW）与可选的面积归一直（W/m²）。

    覆盖边界：只做"窗口均值 → 取 max"这一步；**不代表**配电容量、需量计口径或电网冲击
    （那需要真实的计量窗口与费率定义）。
    """
    if dt_s <= 0:
        raise ValueError(f"dt_s 必须为正，实得 {dt_s}")
    series = _clean(power_w)
    if not series:
        return {"peak_kw": 0.0, "raw_max_kw": 0.0, "peak_w_per_m2": None,
                "window_s": window_s, "dt_s": dt_s, "samples": 0}

    means = _window_means(series, dt_s, window_s)
    peak_w = max(means)
    result = {
        "peak_kw": round(peak_w / 1000.0, 4),
        "raw_max_kw": round(max(series) / 1000.0, 4),
        "peak_w_per_m2": None,
        "window_s": window_s,
        "dt_s": dt_s,
        "samples": len(series),
    }
    if area_m2 is not None:
        if area_m2 <= 0:
            raise ValueError(f"area_m2 必须为正，实得 {area_m2}")
        result["peak_w_per_m2"] = round(peak_w / float(area_m2), 3)
    return result


def peak_power_15min_kw_from_settings(power_w: Sequence[float | None], dt_s: float = DEFAULT_DT_S) -> dict:
    """便捷入口：面积取 `settings.FLOOR_AREA_M2`（该常量若为 None 则不做面积归一）。"""
    from energy_system.config import settings

    area = getattr(settings, "FLOOR_AREA_M2", None)
    area_m2 = float(area) if isinstance(area, (int, float)) and not math.isnan(float(area)) else None
    return peak_power_15min_kw(power_w, dt_s=dt_s, area_m2=area_m2)

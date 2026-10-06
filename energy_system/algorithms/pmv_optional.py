"""PMV/PPD 报告层指标（**可选依赖**，绝不进入核心 requirements）。

## 为什么单独放一个模块

`pythermalcomfort` 会拖进 numpy/scipy。审计明确提醒：**不要把硬塞进核心依赖**，
否则"只想跑 API 与测试的人"也被迫安装。所以：

- 核心依赖（`requirements.txt`）**不含** `pythermalcomfort`；
- 本模块在导入时**守卫式**探测它，缺失时**不报错**（`PMV_AVAILABLE = False`），
  只有调用 `pmv_ppd()` 时才抛出带安装指引的 `RuntimeError`；
- ⇒ `import energy_system...` 与整个测试套件**在无该依赖时照常可用**。

## 口径（重要，别混）

PMV 是 **−3…+3 的感热等级**，`PPD` 是"不满意百分比"；它们与
`time_in_band_share`（IPMVP 原生"带内时间占比"）**不是同一类指标，不可互相换算**。
对外要写"**PMV ∈ [−0.5, +0.5] 的时间占比**"这类描述，而不是把旧的 0–1 评分改个名。

假设必须随结果一起公开：`met`（代谢率）、`clo`（服装热阻）、`vr`（风速）、`rh`（相对湿度）。
本模块的默认值是**常见办公场景假设**，仅用于自检与演示，**对外引用时必须显式写出**。
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - 取决于环境是否安装可选依赖
    from pythermalcomfort.models import pmv_ppd as _pmv_ppd

    PMV_AVAILABLE = True
    PMV_IMPORT_ERROR: str | None = None
except Exception as exc:  # noqa: BLE001 - 任何导入问题都降级为"不可用"
    _pmv_ppd = None
    PMV_AVAILABLE = False
    PMV_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

#: 常见办公场景假设（**仅供自检/演示**，对外引用必须随结果公开）
DEFAULT_MET = 1.2      # 静坐办公 ≈1.2 met
DEFAULT_CLO = 0.5      # 夏季典型着装 ≈0.5 clo
DEFAULT_VR = 0.1       # 室内风速 m/s
DEFAULT_RH = 50.0      # 相对湿度 %

INSTALL_HINT = "pip install pythermalcomfort  # 可选；核心依赖不含它，缺失时其余功能不受影响"


def pmv_ppd(
    tdb: float,
    tr: float | None = None,
    vr: float = DEFAULT_VR,
    rh: float = DEFAULT_RH,
    met: float = DEFAULT_MET,
    clo: float = DEFAULT_CLO,
) -> dict[str, Any]:
    """返回 `{"pmv": float, "ppd": float, ...}`；缺依赖时抛 `RuntimeError`（不静默给假数）。"""
    if not PMV_AVAILABLE:
        raise RuntimeError(
            "pythermalcomfort 未安装（它是**可选**依赖）⇒ 无法计算 PMV/PPD。"
            f"安装方式：{INSTALL_HINT}。导入时的错误：{PMV_IMPORT_ERROR}"
        )
    result = _pmv_ppd(tdb=tdb, tr=tr if tr is not None else tdb, vr=vr, rh=rh, met=met, clo=clo)
    pmv = float(result.pmv)
    ppd = float(result.ppd)
    return {
        "pmv": pmv,
        "ppd": ppd,
        "assumptions": {"met": met, "clo": clo, "vr": vr, "rh": rh, "tr": tr if tr is not None else tdb},
        "band": "PMV ∈ [-0.5, +0.5] 为 ISO 7730 推荐舒适区间（不等于 IPMVP 的带内时间占比）",
    }


def pmv_band_share(temps, **kwargs: Any) -> float:
    """PMV ∈ [−0.5, +0.5] 的**时间占比**（真正的"占比"口径，可与 time_in_band_share 并列报告）。

    缺依赖时抛 `RuntimeError`（同 `pmv_ppd`），**不**回退成温度带占比 —— 那是另一回事。
    """
    values = list(temps)
    if not values:
        return 0.0
    inside = sum(1 for t in values if -0.5 <= pmv_ppd(float(t), **kwargs)["pmv"] <= 0.5)
    return inside / len(values)

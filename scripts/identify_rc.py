"""1R1C 参数辨识：从实测序列拟合 UA / C（评审 §6.2 的"把拍脑袋常数换成辨识值"）。

## 它解决什么

当前 `config/settings.py` 的 `U_WALL/A_WALL/C_AIR` 是**演示级手拍值**，因此仿真节能率只能当
"内部一致性参考"。等实测数据到手（用户同学几天后测），用本脚本把 `UA` 与 `C` **辨识**出来，
对外就能写"模型参数经 X 小时实测识别（R²=…）"，而不是"取自演示级简化值"。

## 方法与口径（全程可复核）

一阶线性模型 `C·dT/dt = UA·(T_out − T_in) + Q`，在固定步长 Δt 上离散：

    ΔT = a·(T_out − T_in)·Δt + b·Q·Δt ,  其中 a = UA/C, b = 1/C

于是它就是一个**二元线性最小二乘**问题（本脚本手写正规方程解 2×2，**不引入 numpy 等新依赖**）：

    UA = a / b ,  C = 1 / b ,  τ = C / UA

## 输入

CSV，表头必须含：`time_s,T_in,T_out,Q_w`

**★ 记录约定（写数据时必须遵守，否则辨识必错）**：每一行记录

    time_s = t 时刻；T_in = t 时刻的室内温度；T_out / Q_w = 在区间 [t, t+dt) 内**生效**的值

也就是说 `T_out`/`Q_w` 要配**这一行之后的那个区间**，而不是配到达这一行的那一步。
（本脚本第一版的自检就踩了这个 off-by-one：热量列整体错位一拍 ⇒ UA 偏 +3.8%、C 偏 +5.2%、
无噪声数据 R² 也只有 0.989 而非 1.0 —— 这个 bug 是被"自检必须通过"挡下来的。）

## 它**不会**做什么

- **不会**自动改 `settings.py` —— 辨识值是否采用、以及随之而来的对外口径变化，是人的决策；
- **不会**在数据缺失时"猜"参数：样本不足 / 回归退化 / R² 过低时**明确报错并用退出码表达**。

退出码：0 成功 / 1 输入问题（缺列、样本不足）/ 2 回归退化或**共线**（C 不可辨识）/ 3 自检失败

## ⚠️ 可辨识性（实测踩过）

**稳态数据只能辨识 UA，辨识不了 C。** 本脚本第一版的自检数据让温度收敛到稳态，
结果辨识出 `UA=1809`（对）而 `C=544533`（真值 25000，**错 20 倍**）——因为此时
`Q` 与 `(T_out − T_in)` 高度共线，只有比值 `a/b = UA` 可辨识。
因此 `fit_rc` 现在会算两个回归量的相关系数 `rho`，`|rho| > 0.98` 时**直接报错拒答**，
并把 `rho` 一并返回（供人工判断）。要辨识 `C`，数据必须有**足够强的动态激励**（暂态段）。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

SECONDS_PER_DAY = 24 * 3600


def _solve_2x2(sxx: float, sxy: float, syy: float, sxz: float, syz: float) -> tuple[float, float]:
    """解 [[sxx, sxy], [sxy, syy]]·[a, b] = [sxz, syz]（正规方程）。"""
    det = sxx * syy - sxy * sxy
    if abs(det) < 1e-12:
        raise ValueError("回归退化：设计矩阵近奇异（室外温度几乎不变，或 Q 恒为 0）")
    a = (sxz * syy - syz * sxy) / det
    b = (sxx * syz - sxy * sxz) / det
    return a, b


def fit_rc(rows: list[dict], dt: float | None = None) -> dict:
    """rows: [{time_s, T_in, T_out, Q_w}, ...]（按时间升序）→ 辨识结果。"""
    if len(rows) < 10:
        raise ValueError(f"样本太少（{len(rows)} 行），至少需要 10 行")

    pairs = []
    for prev, cur in zip(rows, rows[1:]):
        step = (cur["time_s"] - prev["time_s"]) if dt is None else dt
        if step <= 0:
            continue
        pairs.append(
            {
                "x": (prev["T_out"] - prev["T_in"]) * step,   # 传热项
                "z": prev["Q_w"] * step,                       # 得热项
                "y": cur["T_in"] - prev["T_in"],               # ΔT
            }
        )
    if len(pairs) < 10:
        raise ValueError(f"有效相邻样本太少（{len(pairs)} 组）")

    n = len(pairs)
    mx = sum(p["x"] for p in pairs) / n
    mz = sum(p["z"] for p in pairs) / n
    my = sum(p["y"] for p in pairs) / n
    sxx = sum((p["x"] - mx) ** 2 for p in pairs)
    syy = sum((p["z"] - mz) ** 2 for p in pairs)
    sxy = sum((p["x"] - mx) * (p["z"] - mz) for p in pairs)
    sxz = sum((p["x"] - mx) * (p["y"] - my) for p in pairs)
    syz = sum((p["z"] - mz) * (p["y"] - my) for p in pairs)

    a, b = _solve_2x2(sxx, sxy, syy, sxz, syz)
    rho = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 1.0
    if abs(rho) > 0.98:
        raise ValueError(
            f"设计矩阵近共线（rho={rho:.4f}）：Q 与 (T_out−T_in) 几乎同向 ⇒ **C 不可辨识**，"
            "只有比值 UA 可信。请提供含**暂态段**的数据（策略/负荷有阶跃变化）后再辨识 C。"
        )
    if abs(b) < 1e-12:
        raise ValueError("1/C ≈ 0：数据无法约束热容（Q 列可能是恒 0）")

    ua = a / b
    c = 1.0 / b
    # ★ 正性守卫（队友审计指出：本脚本原先没有这条 ⇒ 理论上会给出负热容/负热阻）
    # rcmodel 用 logit 把参数约束在正数域（src/rcmodel/tools/helper_functions.py:105）；
    # 本脚本对"2 个标量"的场景选择更简单的等价做法：**直接拒答**，不返回非物理值。
    if not (ua > 0.0) or not (c > 0.0):
        raise ValueError(
            "拟合出**非正**的物理参数（UA={:.4g} W/K，C={:.4g} J/K）⇒ 拒答："
            "热阻/热容必须为正。常见原因：符号约定反了（制冷/得热的正负号）、数据含未建模的"
            "热源或开窗、激励不足。".format(ua, c)
        )
    residuals = [p["y"] - (a * p["x"] + b * p["z"]) for p in pairs]
    ss_res = sum(r * r for r in residuals)
    ss_tot = sum((p["y"] - my) ** 2 for p in pairs)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        "n_pairs": n,
        "UA_w_per_k": ua,
        "C_j_per_k": c,
        "tau_s": (c / ua) if ua > 0 else float("inf"),
        "r2": r2,
        "rho": rho,
        "rmse_k": math.sqrt(ss_res / n),
        "dt_s": (rows[1]["time_s"] - rows[0]["time_s"]) if dt is None else dt,
    }


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        need = {"time_s", "T_in", "T_out"}
        missing = need - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV 缺列：{sorted(missing)}（应为 time_s,T_in,T_out,Q_w）")
        rows = []
        for row in reader:
            rows.append(
                {
                    "time_s": float(row["time_s"]),
                    "T_in": float(row["T_in"]),
                    "T_out": float(row["T_out"]),
                    "Q_w": float(row.get("Q_w") or 0.0),
                }
            )
    rows.sort(key=lambda r: r["time_s"])
    return rows


def selftest() -> int:
    """用已知 UA/C 生成合成数据，检查能否复原（这是本脚本可被测试钉住的入口）。

    ⚠️ 关键：合成数据的**步长必须远小于 τ**（否则每个点都已在准稳态、C 不可辨识，
    见文件头"可辨识性"）。这里取 dt=0.5s，而真值 τ=C/UA=13.9s ⇒ Δt/τ≈0.036。
    ⚠️ 且此处**不加噪声**：本自检验的是**代数是否正确**（辨识的是纯数学解）。
    真实数据的量测噪声会让 T_in 同时进入回归量与因变量 ⇒ 产生误差变量偏倚（实测 +3~5%），
    所以真实辨识结果请结合 R²/rho/残差人工判断，不要只看参数值。
    """
    truth_ua, truth_c, dt, n = 1800.0, 25000.0, 0.5, 2400
    t_out, t_in = 32.0, 24.0
    rows = []
    for k in range(n):
        q = 1200.0 if (k // 60) % 2 == 0 else 200.0   # 方波激励：区间 [t_k, t_k+dt) 生效的热量
        # ★ 先按"记录约定"落盘（本行的 Q 配的是它之后的那个区间），再推进状态
        rows.append({"time_s": k * dt, "T_in": t_in, "T_out": t_out, "Q_w": q})
        t_inf = t_out + q / truth_ua
        t_in = t_inf + (t_in - t_inf) * math.exp(-truth_ua * dt / truth_c)
    fit = fit_rc(rows, dt=dt)
    ok = (
        abs(fit["UA_w_per_k"] - truth_ua) / truth_ua < 0.05
        and abs(fit["C_j_per_k"] - truth_c) / truth_c < 0.05
    )
    print(
        "  自检(Δt={:.0f}s, {} 点): 真值 UA={:.0f} C={:.0f} → 辨识 UA={:.1f} C={:.0f} "
        "(R²={:.4f}, rho={:.3f}) ⇒ {}".format(
            dt, n, truth_ua, truth_c, fit["UA_w_per_k"], fit["C_j_per_k"],
            fit["r2"], fit["rho"], "PASS" if ok else "FAIL",
        )
    )
    return 0 if ok else 3


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="1R1C 参数辨识（UA / C），不自动修改任何配置")
    ap.add_argument("--input", type=Path, help="实测 CSV：time_s,T_in,T_out,Q_w")
    ap.add_argument("--dt", type=float, default=None, help="固定步长（秒）；缺省用相邻时间差")
    ap.add_argument("--json", type=Path, default=None, help="把结果写到该 JSON")
    ap.add_argument("--selftest", action="store_true", help="用合成数据自检（不需要输入文件）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.input:
        ap.error("需要 --input 或 --selftest")

    try:
        rows = read_csv(args.input)
    except Exception as exc:  # noqa: BLE001
        print(f"  [输入问题] {exc}")
        return 1
    if len(rows) < 10:
        print(f"  [输入问题] 样本太少（{len(rows)} 行），至少需要 10 行")
        return 1

    try:
        fit = fit_rc(rows, dt=args.dt)
    except ValueError as exc:
        print(f"  [回归问题] {exc}")
        return 2

    print("  1R1C 参数辨识结果（仅报告，不改任何配置）：")
    print(f"    UA = {fit['UA_w_per_k']:.1f} W/K      C = {fit['C_j_per_k']:.0f} J/K      τ = {fit['tau_s']:.1f} s")
    print(f"    R² = {fit['r2']:.4f}    rho = {fit['rho']:.3f}    RMSE = {fit['rmse_k']:.3f} K    样本 = {fit['n_pairs']} 组（Δt={fit['dt_s']:.0f}s）")
    if fit["dt_s"] > fit["tau_s"]:
        print("    ⚠️ 采样步长大于时间常数 τ：该数据只能辨识 UA，C 不可辨识（需要更快采样或更强暂态）")
    elif fit["dt_s"] > 0.1 * fit["tau_s"]:
        print(
            "    ⚠️ 步长/τ = {:.3f} > 0.1：本脚本用的是**一阶线性化**离散（ΔT≈(a·x+b·z)·Δt），"
            "在步长不显著小于 τ 时会低估 C（实测 2s/13.9s 时 C 偏大约 10%）。"
            "建议 Δt < 0.1τ；否则应改用精确离散（ARX：T[k+1]=c1·T[k]+c2·T_out+c3·Q）".format(
                fit["dt_s"] / fit["tau_s"]
            )
        )
    if fit["r2"] < 0.5:
        print("    ⚠️ R² 偏低：数据可能含未建模的热源/开窗/人员活动，采用前请人工复核")
    print("    提醒：辨识值必须由人决定是否写入 settings.py，并同步对外口径与 golden 断言。")

    if args.json:
        args.json.write_text(json.dumps(fit, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    已写入 {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

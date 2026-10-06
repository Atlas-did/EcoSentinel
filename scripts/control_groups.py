"""对照矩阵：{do_nothing, baseline, saving} × {demo, realistic} × {bangbang, feedforward}。

出处：《docs/deep-audit-report.md》第 5 章 + 用户任务 ① —— 没有 **baseline 侧对照**，
saving 在 realistic+前馈下的带内占比就没有参照，在 IPMVP 口径下站不住。

⚠️ 口径铁律：`realistic` 是**文献量级假设、非实测**（见 settings.PARAMETER_SETS 的 source）。
所有 realistic 行必须与该标签一起引用，**不得**当作实测结论。
⚠️ `do_nothing` 不参与控制律 ⇒ 只按 params 出 2 行（control_law 记为 "-"），避免重复行。

产物两份（`--write` 生成）：
  tests/references/control_groups.csv      —— 10 行矩阵
  tests/references/saving_vs_baseline.csv  —— 4 行配对对照（IPMVP 口径需要的那个差值）
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from energy_system.algorithms.comfort_kpi import violation_integral  # noqa: E402
from energy_system.algorithms.comfort_eval import time_in_band_share  # noqa: E402
from energy_system.algorithms.peak_kpi import peak_power_15min_kw_from_settings  # noqa: E402
from energy_system.config.settings import PARAMETER_SETS  # noqa: E402
from energy_system.simulation.simulator import Simulator  # noqa: E402

MATRIX_CSV = PROJECT_ROOT / "tests" / "references" / "control_groups.csv"
PAIRED_CSV = PROJECT_ROOT / "tests" / "references" / "saving_vs_baseline.csv"

DAYS, SEED = 3, 42
LAWS = ("bangbang", "feedforward")
SETS = ("demo", "realistic")
FIELDS = ("mode", "params", "control_law", "total_kwh", "band_share", "temp_violation_kh",
          "peak_15min_kw", "t_in_mean", "t_in_min", "t_in_max")
PAIRED_FIELDS = ("params", "control_law", "baseline_kwh", "saving_kwh", "saving_rate_percent",
                 "band_share_baseline", "band_share_saving", "band_share_delta",
                 "temp_violation_baseline_kh", "temp_violation_saving_kh", "temp_violation_delta_kh")


def _params(name: str) -> dict | None:
    """demo 用 settings 默认值（传 None ⇒ 行为与历史逐位一致）；realistic 用集合里的值。"""
    if name == "demo":
        return None
    values = PARAMETER_SETS[name]
    return {k: values[k] for k in ("U_WALL", "A_WALL", "C_AIR")}


def run_cell(mode: str, set_name: str, law: str) -> dict:
    # do_nothing 用早退分支，行为与控制律无关 ⇒ 传合法律（避免触发校验），只把记录写成 "-"
    effective_law = "bangbang" if law == "-" else law
    history = Simulator(mode=mode, seed=SEED, params=_params(set_name),
                        control_law=effective_law).run_simulation(days=DAYS)
    track = history["T_in"]
    peak = peak_power_15min_kw_from_settings(history["power_total"])
    return {
        "mode": mode,
        "params": set_name,
        "control_law": law,
        "total_kwh": round(history["total_kwh"], 3),
        "band_share": round(time_in_band_share(track), 4),
        "temp_violation_kh": round(violation_integral(track, 23.0, 26.0), 3),
        "peak_15min_kw": peak["peak_kw"],
        "t_in_mean": round(statistics.mean(track), 3),
        "t_in_min": round(min(track), 3),
        "t_in_max": round(max(track), 3),
    }


def run_matrix() -> list[dict]:
    rows: list[dict] = []
    for set_name in SETS:
        for mode in ("do_nothing", "baseline", "saving"):
            if mode == "do_nothing":
                rows.append(run_cell(mode, set_name, "-"))
                continue
            for law in LAWS:
                rows.append(run_cell(mode, set_name, law))
    return rows


def run_paired(rows: list[dict]) -> list[dict]:
    """每个 (params, law) 下 saving 相对同参同律 baseline 的配对差 —— IPMVP 口径需要的对照。"""
    index = {(r["params"], r["control_law"], r["mode"]): r for r in rows}
    out: list[dict] = []
    for set_name in SETS:
        for law in LAWS:
            base = index[(set_name, law, "baseline")]
            save = index[(set_name, law, "saving")]
            out.append({
                "params": set_name,
                "control_law": law,
                "baseline_kwh": base["total_kwh"],
                "saving_kwh": save["total_kwh"],
                "saving_rate_percent": round(
                    (base["total_kwh"] - save["total_kwh"]) / base["total_kwh"] * 100.0, 2),
                "band_share_baseline": base["band_share"],
                "band_share_saving": save["band_share"],
                "band_share_delta": round(save["band_share"] - base["band_share"], 4),
                "temp_violation_baseline_kh": base["temp_violation_kh"],
                "temp_violation_saving_kh": save["temp_violation_kh"],
                "temp_violation_delta_kh": round(
                    save["temp_violation_kh"] - base["temp_violation_kh"], 3),
            })
    return out


def write_csv(rows: list[dict], fields: tuple, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows([{k: r[k] for k in fields} for r in rows])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="对照矩阵（含 baseline 侧）")
    ap.add_argument("--write", action="store_true", help="重新生成两份参考 CSV")
    args = ap.parse_args(argv)

    rows = run_matrix()
    paired = run_paired(rows)
    print("  {:<11} {:<10} {:<12} {:>8} {:>7} {:>9} {:>7}".format(
        "mode", "params", "law", "kWh", "band", "viol K·h", "peak kW"))
    for r in rows:
        print("  {mode:<11} {params:<10} {control_law:<12} {total_kwh:>8.2f} "
              "{band_share:>6.1%} {temp_violation_kh:>9.1f} {peak_15min_kw:>7.2f}".format(**r))
    print("  --- saving 相对 baseline（IPMVP 口径需要的对照）---")
    for p in paired:
        print("  {params:<10} {control_law:<12} 节能 {saving_rate_percent:>6.2f}%  "
              "带内占比 {band_share_baseline:.1%}→{band_share_saving:.1%} (Δ{band_share_delta:+.1%})  "
              "越界 Δ{temp_violation_delta_kh:+.1f} K·h".format(**p))

    if args.write:
        write_csv(rows, FIELDS, MATRIX_CSV)
        write_csv(paired, PAIRED_FIELDS, PAIRED_CSV)
        print("  已写入两份参考 CSV")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""三组对照运行器：do_nothing / baseline(建筑默认) / saving。

出处与方法（《report-benchmarks.md》P0-2 + BOPTEST 的基线范式）：
- BOPTEST 的空动作基线返回 `u={}`（`examples/python/controllers/baseline.py:29-31`），
  并由它**预生成参考值**（`baselines/README.md:32-37` 声明 3180 场景，产物是 `baselines/csv/*.csv`）。
- 本仓的**修正**（必须说明，不能照抄）：我们的 1R1C 模型**没有自带 thermostat** ⇒
  "空动作 = 交给建筑本体"在本仓不成立；`do_nothing` 只能是"空调与照明都不动作"。
  另外 `baseline`（全天 24 ℃ 定值）**已经**扮演"建筑默认控制器"的角色，所以**不再新增
  `building_default`** —— 那样会与 `baseline` 逐值相同，是冗余。

用法：
    python scripts/control_groups.py            # 与 tests/references/control_groups.csv 比对
    python scripts/control_groups.py --write    # 重新生成参考 CSV（只在**有意**改动时用）

⚠️ 参考 CSV 是"跑一次、提交、之后当门禁"（同 BOPTEST `testing/utilities.py:302-304` 的做法），
**不是**手写或拟合出来的数字。
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from energy_system.algorithms.comfort_eval import (  # noqa: E402
    evaluate_comfort,
    time_in_band_share,
)
from energy_system.simulation.simulator import Simulator  # noqa: E402

REFERENCE = PROJECT_ROOT / "tests" / "references" / "control_groups.csv"
DAYS = 3
SEED = 42
#: 三种对照：do_nothing = 不动作；baseline = 全天 24 ℃ 定值（承担"建筑默认控制器"角色）；
#: saving = 本仓的节能策略（含 07–09 预冷 —— 注意本模型无热惯性，见 README）。
MODES = ("do_nothing", "baseline", "saving")

FIELDS = (
    "mode",
    "total_kwh",
    "band_share",
    "comfort_mean_legacy",
    "t_in_mean",
    "t_in_min",
    "t_in_max",
)


def run_group(mode: str, days: int = DAYS, seed: int = SEED) -> dict:
    history = Simulator(mode=mode, seed=seed).run_simulation(days=days)
    t_in = history["T_in"]
    humidity = history["humidity"]
    return {
        "mode": mode,
        "total_kwh": round(history["total_kwh"], 3),
        "band_share": round(time_in_band_share(t_in), 4),
        "comfort_mean_legacy": round(
            statistics.mean(evaluate_comfort(t, h) for t, h in zip(t_in, humidity)), 4
        ),
        "t_in_mean": round(statistics.mean(t_in), 3),
        "t_in_min": round(min(t_in), 3),
        "t_in_max": round(max(t_in), 3),
    }


def run_all(days: int = DAYS, seed: int = SEED) -> list[dict]:
    return [run_group(mode, days=days, seed=seed) for mode in MODES]


def load_reference(path: Path = REFERENCE) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def compare(rows: list[dict], reference: list[dict], tol_kwh: float = 0.05,
            tol_share: float = 0.002) -> list[str]:
    """返回不一致清单（空 = 一致）。数值容差与测试里一致。"""
    problems: list[str] = []
    if len(rows) != len(reference):
        return [f"行数不一致：实得 {len(rows)}，参考 {len(reference)}"]
    for got, want in zip(rows, reference):
        if got["mode"] != want["mode"]:
            problems.append(f"顺序不一致：{got['mode']} vs {want['mode']}")
            continue
        if abs(float(got["total_kwh"]) - float(want["total_kwh"])) > tol_kwh:
            problems.append(f"{got['mode']}.total_kwh: {got['total_kwh']} vs 参考 {want['total_kwh']}")
        if abs(float(got["band_share"]) - float(want["band_share"])) > tol_share:
            problems.append(f"{got['mode']}.band_share: {got['band_share']} vs 参考 {want['band_share']}")
    return problems


def write_reference(rows: list[dict], path: Path = REFERENCE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="三组对照运行器（do_nothing / baseline / saving）")
    ap.add_argument("--write", action="store_true", help="重新生成参考 CSV（有意改动时才用）")
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)

    rows = run_all(days=args.days, seed=args.seed)
    for row in rows:
        print("  {mode:<12} {total_kwh:>8.2f} kWh  带内占比={band_share:>6.1%}  "
              "旧评分={comfort_mean_legacy:.3f}  T_in=[{t_in_min:.2f}, {t_in_max:.2f}] 均值 {t_in_mean:.2f}".format(**row))

    if args.write:
        write_reference(rows)
        print(f"  已写入参考：{REFERENCE.relative_to(PROJECT_ROOT)}")
        return 0

    if not REFERENCE.exists():
        print(f"  [缺参考文件] {REFERENCE} 不存在；确认无误后跑 `--write` 生成")
        return 2
    problems = compare(rows, load_reference())
    if problems:
        print("  ❌ 与参考不一致：")
        for item in problems:
            print(f"     {item}")
        return 1
    print("  ✅ 与参考一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

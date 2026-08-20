"""Baseline-vs-saving simulation comparison with explicit experiment parameters.

Runs a fixed-parameter 3-day digital-twin simulation for both control modes and
reports total energy, savings rate, and mean comfort. The output is deterministic
for a given seed, so the same invocation reproduces the same numbers — this is the
behaviour baseline that refactoring must not silently change.

Usage:
    python -m energy_system.simulation.compare
    python -m energy_system.simulation.compare --json results/baseline.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from energy_system.algorithms.energy_saving import calculate_savings
from energy_system.config import settings
from energy_system.domain.metrics import descriptive_stats
from energy_system.experiments.manifest import ExperimentManifest, config_hash
from energy_system.simulation.simulator import Simulator

# Fixed parameters that fully describe this experiment. Keep these in one place so
# the refactor-baseline docs and the JSON report stay in sync.
SCHEMA_VERSION = "1.0"
SIM_SEED = 42
INITIAL_TEMP_C = 20.0
DURATION_DAYS = 3


def _comfort_mean(history: dict) -> float:
    values = history.get("comfort") or [0.0]
    return sum(values) / len(values)


def run_compare(duration_days: int = DURATION_DAYS, seed: int = SIM_SEED) -> dict:
    """Run the baseline + saving simulation and return a structured report dict.

    The returned dict is the canonical experiment record: every field needed to
    reproduce the result is included, along with the computed metrics.
    """
    sim_base = Simulator(mode="baseline", seed=seed)
    history_base = sim_base.run_simulation(days=duration_days)

    sim_save = Simulator(mode="saving", seed=seed)
    history_save = sim_save.run_simulation(days=duration_days)

    report = calculate_savings(history_base["total_kwh"], history_save["total_kwh"])
    comfort_base = _comfort_mean(history_base)
    comfort_save = _comfort_mean(history_save)
    comfort_base_stats = descriptive_stats(history_base.get("comfort") or [])
    comfort_save_stats = descriptive_stats(history_save.get("comfort") or [])

    experiment_id = f"baseline-{datetime.now().strftime('%Y-%m-%d')}"
    simulation = {
        "seed": seed,
        "dt_seconds": settings.TIME_STEP,
        "duration_days": duration_days,
        "initial_temperature_c": INITIAL_TEMP_C,
        "weather_input_version": "environment_generator_v1",
        "control_mode": "baseline_vs_saving",
        "model_params": {
            "c_air_j_k": settings.C_AIR,
            "u_wall_w_m2k": settings.U_WALL,
            "a_wall_m2": settings.A_WALL,
            "alpha_solar": settings.ALPHA_SOLAR,
            "a_window_m2": settings.A_WINDOW,
            "q_people_w": settings.Q_PEOPLE,
            "q_equip_w": settings.Q_EQUIP,
            "cop_cooling": settings.COP_COOLING,
            "cop_heating": settings.COP_HEATING,
            "q_ac_max_w": settings.Q_AC_MAX,
            "power_light_max_w": settings.POWER_LIGHT_MAX,
            "power_light_standby_w": settings.POWER_LIGHT_STANDBY,
        },
    }
    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        mode="baseline_vs_saving",
        started_at=datetime.now().isoformat(),
        ended_at=datetime.now().isoformat(),
        device_version="simulator_v1",
        config_hash=config_hash(simulation),
        sampling_period_s=float(settings.TIME_STEP),
        raw_jsonl_path=None,
        summary_path=None,
        notes="3-day digital-twin baseline-vs-saving comparison",
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "generated_at": datetime.now().isoformat(),
        "config_hash": manifest.config_hash,
        "experiment": manifest.to_dict(),
        "simulation": simulation,
        "results": {
            "baseline_energy_kwh": round(report["baseline_energy_kwh"], 2),
            "saving_energy_kwh": round(report["actual_energy_kwh"], 2),
            "energy_saved_kwh": round(report["energy_saved_kwh"], 2),
            "saving_rate_percent": round(report["saving_rate_percent"], 1),
            "carbon_reduced_kg": round(report["carbon_reduced_kg"], 2),
            "baseline_comfort_mean": round(comfort_base, 3),
            "saving_comfort_mean": round(comfort_save, 3),
            "baseline_comfort_stats": comfort_base_stats,
            "saving_comfort_stats": comfort_save_stats,
        },
    }
    return result


def _print_report(result: dict) -> None:
    r = result["results"]
    s = result["simulation"]
    print("=" * 60)
    print(" Energy Model Full Simulation (baseline vs saving)")
    print(f" dt={s['dt_seconds']}s, duration={s['duration_days']}d, seed={s['seed']}")
    print("=" * 60)
    print(f"[OK] Baseline energy:       {r['baseline_energy_kwh']:.2f} kWh")
    print(f"[OK] Saving energy:         {r['saving_energy_kwh']:.2f} kWh")
    print(f"[OK] Energy saved:          {r['energy_saved_kwh']:.2f} kWh")
    print(f"[>>] Saving rate:           {r['saving_rate_percent']:.1f}%")
    print(f"[>>] Carbon reduced:        {r['carbon_reduced_kg']:.2f} kgCO2")
    print("-" * 30)
    print(f"Baseline avg comfort: {r['baseline_comfort_mean']:.1%}")
    print(f"Saving avg comfort:   {r['saving_comfort_mean']:.1%}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="EcoSentinel simulation comparison")
    parser.add_argument("--json", type=str, default=None, help="Optional path to write the JSON report")
    parser.add_argument("--days", type=int, default=DURATION_DAYS, help="Simulation duration in days")
    parser.add_argument("--seed", type=int, default=SIM_SEED, help="Random seed for the weather generator")
    args = parser.parse_args()

    result = run_compare(duration_days=args.days, seed=args.seed)
    _print_report(result)

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[>>] Report written to {out}")


if __name__ == "__main__":
    main()

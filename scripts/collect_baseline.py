"""Collect a reproducible baseline snapshot for the EcoSentinel refactor.

Runs the test suite and the fixed-parameter simulation, then writes a structured
JSON report capturing the behaviour that refactoring must preserve. The report
contains no secrets and no runtime log contents — only test counts and simulation
metrics — so it is safe to commit.

Usage:
    python scripts/collect_baseline.py
    python scripts/collect_baseline.py --out results/baseline.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "1.0"


def _run_tests() -> dict:
    """Run pytest and return the summary line (last non-empty line)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    summary = ""
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            summary = line
    return {
        "returncode": proc.returncode,
        "summary": summary,
        "passed": proc.returncode == 0,
    }


def _run_simulation() -> dict:
    """Import and run the simulation comparison, returning the structured report."""
    sys.path.insert(0, str(ROOT))
    from energy_system.simulation.compare import run_compare  # noqa: E402

    return run_compare()


def collect() -> dict:
    tests = _run_tests()
    sim = _run_simulation()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(),
        "python_version": sys.version.split()[0],
        "tests": tests,
        "simulation": sim,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect EcoSentinel refactor baseline")
    parser.add_argument("--out", type=str, default="results/baseline.json",
                        help="Output path for the JSON report")
    args = parser.parse_args()

    report = collect()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[>>] Baseline written to {out}")

    if not report["tests"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

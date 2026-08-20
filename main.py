"""环境监测与 AI 节能调控系统 — 硬件模式主入口（兼容入口）。

Usage:
    python main.py
    python -m energy_system.cli.run_edge --config path/to/params.yaml

This module is now a thin compatibility shim. The real runtime lives in
:class:`energy_system.application.runtime.EnergySystemApp` and the CLI entry
point in :func:`energy_system.cli.run_edge.main`. Keeping ``python main.py``
working preserves the legacy entry point while the heavy lifting is delegated
to the new application/cli layers.
"""

from energy_system.application.runtime import EnergySystemApp
from energy_system.cli.run_edge import main as _cli_main

__all__ = ["EnergySystemApp"]


if __name__ == "__main__":
    raise SystemExit(_cli_main())

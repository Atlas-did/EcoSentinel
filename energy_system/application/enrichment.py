"""Telemetry enrichment: derive comfort, energy and battery metrics from a sample.

Extracted from ``EnergySystemApp._compute_comfort/_compute_energy`` so the
metric pipeline can be exercised in isolation from hardware and logging.
"""

from __future__ import annotations

from energy_system.algorithms.comfort_eval import evaluate_comfort
from energy_system.domain.telemetry import set_metric
from energy_system.power.energy_accounting import BatterySOC, EnergyAccumulator
from energy_system.utils.helpers import pick


class TelemetryEnrichmentService:
    """Owns the stateful energy/battery accumulators and comfort evaluation."""

    def __init__(
        self,
        *,
        battery_capacity_mah: float = 10000.0,
        battery_initial_soc: float = 80.0,
        current_key: str = "solar_current_ma",
    ) -> None:
        self.acc = EnergyAccumulator()
        self.solar_acc = EnergyAccumulator(
            pwr_mw_key="solar_pwr_mw",
            bus_v_key="solar_bus_v",
            current_ma_key="solar_current_ma",
        )
        self.battery_soc = BatterySOC(
            capacity_mah=battery_capacity_mah,
            initial_soc_percent=battery_initial_soc,
            current_key=current_key,
        )

    def enrich(self, sensor_data: dict) -> dict:
        """Enrich ``sensor_data`` in place with comfort/energy/soc fields.

        写指标一律走 ``set_metric``：键名拼错会**立刻抛错**，而不是静默多出一个
        没人认识的字段（旧代码的字面量赋值会一路无声地流到日志与 API）。
        """
        temp_c = pick(sensor_data, ["temperature", "temp"], default=25.0)
        hum_pct = pick(sensor_data, ["humidity", "hum"], default=50.0)
        set_metric(sensor_data, "comfort_score", evaluate_comfort(temp_c, hum_pct))

        stats = self.acc.update(sensor_data)
        if stats.power_w is not None:
            set_metric(sensor_data, "power_w", stats.power_w)
        set_metric(sensor_data, "energy_wh", stats.energy_wh)

        solar_stats = self.solar_acc.update(sensor_data)
        if solar_stats.power_w is not None:
            set_metric(sensor_data, "solar_power_w", solar_stats.power_w)
        set_metric(sensor_data, "solar_energy_wh", solar_stats.energy_wh)

        soc_stats = self.battery_soc.update_from_sample(sensor_data)
        set_metric(sensor_data, "soc_percent", soc_stats.soc_percent)
        return sensor_data

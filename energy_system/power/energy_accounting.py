import time
from dataclasses import dataclass


@dataclass
class EnergyStats:
    power_w: float | None = None
    energy_wh: float = 0.0
    last_ts: float | None = None


@dataclass
class BatterySOCStats:
    soc_percent: float = 100.0
    net_charge_mah: float = 0.0
    last_ts: float | None = None


class EnergyAccumulator:
    """Accumulate energy (Wh) from power samples.

    Supports inputs:
    - pwr_mw (preferred) -> W
    - bus_v + current_ma -> W

    Timestamps:
    - if sample contains 'timestamp' (ISO), caller can pass explicit ts
    - otherwise uses time.time() at update()
    """

    def __init__(
        self,
        pwr_mw_key: str = "pwr_mw",
        bus_v_key: str = "bus_v",
        current_ma_key: str = "current_ma",
    ):
        self._stats = EnergyStats()
        self._pwr_mw_key = pwr_mw_key
        self._bus_v_key = bus_v_key
        self._current_ma_key = current_ma_key

    def estimate_power_w(self, sample: dict) -> float | None:
        pwr_mw = sample.get(self._pwr_mw_key)
        if isinstance(pwr_mw, (int, float)):
            return float(pwr_mw) / 1000.0

        bus_v = sample.get(self._bus_v_key)
        current_ma = sample.get(self._current_ma_key)
        if isinstance(bus_v, (int, float)) and isinstance(current_ma, (int, float)):
            return float(bus_v) * float(current_ma) / 1000.0

        return None

    def update(self, sample: dict, ts: float | None = None) -> EnergyStats:
        now = float(ts if ts is not None else time.time())
        power_w = self.estimate_power_w(sample)

        if self._stats.last_ts is not None and power_w is not None:
            dt_s = max(0.0, now - self._stats.last_ts)
            self._stats.energy_wh += power_w * (dt_s / 3600.0)

        self._stats.power_w = power_w
        self._stats.last_ts = now
        return self._stats

    def snapshot(self) -> EnergyStats:
        return self._stats


class BatterySOC:
    """Simple battery SOC estimator via coulomb counting.

    Convention:
    - current_ma > 0: charging current
    - current_ma < 0: discharging current
    """

    def __init__(
        self,
        capacity_mah: float = 10000.0,
        initial_soc_percent: float = 100.0,
        current_key: str = "solar_current_ma",
    ):
        self.capacity_mah = max(1.0, float(capacity_mah))
        init_soc = max(0.0, min(100.0, float(initial_soc_percent)))
        self.current_key = current_key
        self._stats = BatterySOCStats(soc_percent=init_soc)

    def reset(self, soc_percent: float = 100.0) -> BatterySOCStats:
        self._stats = BatterySOCStats(
            soc_percent=max(0.0, min(100.0, float(soc_percent))),
            net_charge_mah=0.0,
            last_ts=None,
        )
        return self._stats

    def update(self, current_ma: float, ts: float | None = None) -> BatterySOCStats:
        now = float(ts if ts is not None else time.time())
        if self._stats.last_ts is not None:
            dt_s = max(0.0, now - self._stats.last_ts)
            delta_mah = float(current_ma) * (dt_s / 3600.0)
            self._stats.net_charge_mah += delta_mah
            delta_soc = (delta_mah / self.capacity_mah) * 100.0
            self._stats.soc_percent = max(0.0, min(100.0, self._stats.soc_percent + delta_soc))
        self._stats.last_ts = now
        return self._stats

    def update_from_sample(self, sample: dict, ts: float | None = None) -> BatterySOCStats:
        cur = sample.get(self.current_key)
        if isinstance(cur, (int, float)):
            return self.update(float(cur), ts=ts)
        # No current available: only advance timestamp to avoid stale large dt on next sample.
        self._stats.last_ts = float(ts if ts is not None else time.time())
        return self._stats

    def snapshot(self) -> BatterySOCStats:
        return self._stats

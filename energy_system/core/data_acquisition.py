"""Data acquisition coordinator for EnergySystemApp.

Handles reading sensor data from hardware (SerialBridge) or generating
mock data via the simulation module when hardware is unavailable.
"""

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("DataAcquisition")


class DataAcquisition:
    """Coordinates sensor data reading from hardware or simulation."""

    def __init__(
        self,
        use_hardware: bool = False,
        serial_bridge: Any = None,
    ) -> None:
        self.use_hardware = use_hardware
        self.serial_bridge = serial_bridge
        self._env_gen = None  # lazy init for mock mode

    def _get_mock_generator(self) -> Any:
        """Lazily create and return an EnvironmentGenerator for mock data."""
        if self._env_gen is None:
            from energy_system.simulation.data_generator import EnvironmentGenerator

            self._env_gen = EnvironmentGenerator(seed=None)  # random seed per run
        return self._env_gen

    def read(self) -> dict | None:
        """Fetch one sensor sample.

        Returns:
            A dict of sensor data, or None if no data is available.
        """
        if self.use_hardware:
            return self._read_hardware()
        else:
            return self._read_mock()

    def _read_hardware(self) -> dict | None:
        bridge = self.serial_bridge
        if not bridge:
            return None
        try:
            return bridge.read_sensors()
        except Exception as e:
            logger.warning(f"Sensor read failed: {e}")
            return None

    def _read_mock(self) -> dict:
        """Generate realistic mock data using the simulation environment generator.

        Uses EnvironmentGenerator to produce time-correlated random walk values
        instead of hardcoded constants. This provides more realistic dashboard
        testing when hardware is unavailable.
        """
        gen = self._get_mock_generator()
        now_ts = time.time()
        T_out, I_solar, hour = gen.generate(now_ts, use_random_walk=True)
        humidity = gen.generate_humidity(now_ts, use_random_walk=True)

        return {
            "temperature": round(float(T_out), 1),
            "humidity": round(float(humidity), 1),
            "illuminance": round(max(0.0, float(I_solar) * 100.0 * 0.15), 1),
            "eco2": 450,
            "tvoc": 12,
            "timestamp": datetime.now().isoformat(),
        }


def no_data_heartbeat_fields(
    safe_reason: str | None,
    resilience: Any,
    bridge_health: dict | None = None,
) -> dict:
    """Build a compact heartbeat row for logging when no sensor data is available."""
    return {
        "timestamp": datetime.now().isoformat(),
        "safe_mode": True,
        "safe_reason": safe_reason or "no_sample_yet",
        "bridge_health": bridge_health,
        "resilience": {
            "state": getattr(resilience, "breaker_state", None),
            "incident_id": getattr(resilience, "last_incident_id", None),
            "last_action": getattr(resilience, "last_action", None),
            "last_action_reason": getattr(resilience, "last_action_reason", None),
        },
    }

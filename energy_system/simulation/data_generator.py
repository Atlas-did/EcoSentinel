import math
import random


class EnvironmentGenerator:
    """Generate outdoor environment data with isolated random-walk state.

    Each instance keeps its own walk state so multiple simulations do not interfere.
    """

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self._temp_walk = 0.0
        self._solar_walk = 0.0
        self._humidity_walk = 0.0

    def generate(self, t_s, use_random_walk: bool = True):
        hour = (t_s / 3600.0) % 24.0

        # 模拟外部温度日波峰 (14:00 高峰) (更改夏季平均温度以适配节能分段策略)
        # 均温 29℃, 波动 ±6℃ => 23℃ ~ 35℃
        T_out = 29.0 + 6.0 * math.sin(2.0 * math.pi * (hour - 14.0) / 24.0)

        # 模拟太阳短波辐射 (6:00 - 18:00 半波)
        I_solar = 0.0
        if 6.0 <= hour <= 18.0:
            I_solar = 500.0 * math.sin(math.pi * (hour - 6.0) / 12.0)

        # 极度逼真的高斯随机游走 (Gaussian Random Walk)
        if use_random_walk:
            self._temp_walk += self.rng.gauss(0, 0.05)
            # 边界约束，防止偏差过大
            if abs(self._temp_walk) > 1.5:
                self._temp_walk *= 0.95
            T_out += self._temp_walk

            if I_solar > 0:
                self._solar_walk += self.rng.gauss(0, 5.0)
                if abs(self._solar_walk) > 50.0:
                    self._solar_walk *= 0.9
                I_solar = max(0.0, I_solar + self._solar_walk)

        return T_out, I_solar, hour

    def generate_humidity(self, t_s, use_random_walk: bool = True):
        """Generate outdoor-relative humidity (%) with optional random walk.

        Daytime tends to be lower and nighttime higher, with bounded noise.
        """
        hour = (t_s / 3600.0) % 24.0

        # 基础日变化：下午偏干、清晨偏湿
        humidity = 60.0 - 15.0 * math.sin(2.0 * math.pi * (hour - 14.0) / 24.0)

        if use_random_walk:
            self._humidity_walk += self.rng.gauss(0, 0.6)
            if abs(self._humidity_walk) > 10.0:
                self._humidity_walk *= 0.9
            humidity += self._humidity_walk

        return max(20.0, min(95.0, humidity))

def generate_environment_data(t_s, use_random_walk=True):
    """Backward-compatible helper for existing callers.

    Uses a per-call generator with a fixed seed so the result is reproducible
    within a single run, while avoiding shared module-level random-walk state.
    """
    if not hasattr(generate_environment_data, "_default_generator"):
        generate_environment_data._default_generator = EnvironmentGenerator(seed=42)  # type: ignore[attr-defined]
    gen = generate_environment_data._default_generator  # type: ignore[attr-defined]
    return gen.generate(t_s, use_random_walk=use_random_walk)

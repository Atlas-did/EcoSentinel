"""General-purpose utility helpers used across the project."""

from typing import Any


def pick(data: dict, keys: list[str], default: Any = None) -> Any:
    """Safely retrieve the first non-None value from a dict for a list of candidate keys.

    Useful when sensor data may use different key names (e.g. 'temperature' vs 'temp').

    Args:
        data: Source dictionary.
        keys: Ordered list of keys to try.
        default: Value returned when none of the keys are present with a non-None value.

    Returns:
        The first non-None value found, or `default`.

    Example:
        temp = pick(sensor_data, ["temperature", "temp"], default=25.0)
    """
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return default

"""Domain error hierarchy for EcoSentinel.

Failures are classified so callers can degrade gracefully instead of catching
bare ``Exception`` everywhere. High-risk boundaries (command validation, transport,
AI) must raise or log these specific types and preserve ``error_type``,
``operation``, ``recoverable`` and ``correlation_id`` in structured logs.

The hierarchy is deliberately shallow: a base type per major failure domain, with
leaf types only where a distinct recoverability decision exists.
"""

from __future__ import annotations


class EcoSentinelError(Exception):
    """Base class for all EcoSentinel domain errors."""

    error_type: str = "ecosentinel_error"

    def __init__(self, message: str, *, operation: str | None = None,
                 recoverable: bool = False, correlation_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.recoverable = recoverable
        self.correlation_id = correlation_id

    def to_log_fields(self) -> dict:
        """Return a structured dict suitable for a log record's error context."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "operation": self.operation,
            "recoverable": self.recoverable,
            "correlation_id": self.correlation_id,
        }


class ConfigurationError(EcoSentinelError):
    """Invalid or contradictory configuration."""

    error_type = "configuration_error"


class InvalidTelemetryError(EcoSentinelError):
    """Sensor data is missing, malformed, or stale and cannot be trusted."""

    error_type = "invalid_telemetry_error"


class CommandValidationError(EcoSentinelError):
    """A proposed command failed syntax or domain validation."""

    error_type = "command_validation_error"

    def __init__(self, message: str, *, reason: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.reason = reason  # machine-readable rejection code, e.g. "relay_channel_out_of_range"


class TransportError(EcoSentinelError):
    """A device transport failed (serial, MQTT, ...)."""

    error_type = "transport_error"


class SerialDisconnectedError(TransportError):
    error_type = "serial_disconnected_error"


class MqttUnavailableError(TransportError):
    error_type = "mqtt_unavailable_error"


class AIProviderError(EcoSentinelError):
    """An AI/cloud provider call failed or returned unusable output."""

    error_type = "ai_provider_error"


class AITimeoutError(AIProviderError):
    error_type = "ai_timeout_error"


class AIResponseFormatError(AIProviderError):
    error_type = "ai_response_format_error"


class AICircuitOpenError(AIProviderError):
    error_type = "ai_circuit_open_error"


class PersistenceError(EcoSentinelError):
    """Reading or writing persistent data (logs, experiments) failed."""

    error_type = "persistence_error"

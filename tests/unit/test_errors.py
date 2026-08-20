"""Unit tests for the domain error hierarchy."""

import unittest

from energy_system.core.errors import (
    AICircuitOpenError,
    AIProviderError,
    AIResponseFormatError,
    AITimeoutError,
    CommandValidationError,
    ConfigurationError,
    EcoSentinelError,
    InvalidTelemetryError,
    MqttUnavailableError,
    PersistenceError,
    SerialDisconnectedError,
    TransportError,
)


class TestErrorHierarchy(unittest.TestCase):
    def test_all_errors_inherit_base(self):
        for cls in (
            ConfigurationError, InvalidTelemetryError, CommandValidationError,
            TransportError, AIProviderError, PersistenceError,
        ):
            self.assertTrue(issubclass(cls, EcoSentinelError))

    def test_transport_leaves(self):
        self.assertTrue(issubclass(SerialDisconnectedError, TransportError))
        self.assertTrue(issubclass(MqttUnavailableError, TransportError))

    def test_ai_leaves(self):
        self.assertTrue(issubclass(AITimeoutError, AIProviderError))
        self.assertTrue(issubclass(AIResponseFormatError, AIProviderError))
        self.assertTrue(issubclass(AICircuitOpenError, AIProviderError))

    def test_error_types_are_distinct(self):
        self.assertEqual(ConfigurationError.error_type, "configuration_error")
        self.assertEqual(SerialDisconnectedError.error_type, "serial_disconnected_error")
        self.assertEqual(AITimeoutError.error_type, "ai_timeout_error")

    def test_to_log_fields(self):
        err = ConfigurationError("bad field", operation="load", recoverable=False)
        fields = err.to_log_fields()
        self.assertEqual(fields["error_type"], "configuration_error")
        self.assertEqual(fields["operation"], "load")
        self.assertFalse(fields["recoverable"])

    def test_command_validation_carries_reason(self):
        err = CommandValidationError("nope", reason="relay_channel_out_of_range")
        self.assertEqual(err.reason, "relay_channel_out_of_range")


if __name__ == "__main__":
    unittest.main()

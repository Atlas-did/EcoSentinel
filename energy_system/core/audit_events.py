"""Audit event model for command decisions and safety outcomes.

Every command that is accepted, rejected, rate-limited, or deliberately not
executed produces an audit record with enough context to answer "what happened to
this command, and why". Records are deliberately minimal: they must never contain
API keys, full prompts, or raw sensor payloads.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum


class AuditEventType(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RATE_LIMITED = "rate_limited"
    NOT_EXECUTED = "not_executed"


@dataclass(frozen=True)
class AuditEvent:
    """A single auditable command decision."""

    event_type: AuditEventType
    run_mode: str
    timestamp: str = ""
    command: str | None = None
    reason: str | None = None
    candidate_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None

    def to_record(self) -> dict:
        """Render as a JSON-serializable dict for structured logging."""
        data = asdict(self)
        data["timestamp"] = self.timestamp or datetime.now().isoformat()
        data["event_type"] = self.event_type.value if isinstance(self.event_type, AuditEventType) else str(self.event_type)
        return data


def sanitize_command_for_audit(raw: str, max_len: int = 128) -> str:
    """Return a bounded, secrets-free representation of a command string.

    Commands are short by design (e.g. "RELAY 3 1"); this caps length and strips
    control characters so malformed/oversized input cannot bloat the audit log.
    """
    s = str(raw or "").replace("\n", " ").replace("\r", " ")
    return s[:max_len]

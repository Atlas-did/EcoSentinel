"""ActuationService: executes ControlPlans against an ActuatorTransport.

Responsibilities (and nothing else):
    1. receive a :class:`ControlPlan`,
    2. check state-diff and minimum-interval (anti-jitter / rate limiting),
    3. call the transport,
    4. record the results.

It is transport-agnostic and time-agnostic (uses an injected :class:`Clock`), so it
can be tested with a mock transport and a fake clock.
"""

from __future__ import annotations

from energy_system.core.clock import Clock, SystemClock
from energy_system.core.control.compiler import CommandCompiler
from energy_system.core.control.models import ControlPlan
from energy_system.core.control.transport import ActuatorTransport, CommandResult
from energy_system.core.models.commands import RelayCommand


class ActuationService:
    def __init__(
        self,
        transport: ActuatorTransport,
        *,
        min_interval_s: float = 2.0,
        clock: Clock | None = None,
        compiler: CommandCompiler | None = None,
    ):
        self.transport = transport
        self.min_interval_s = float(min_interval_s)
        self.clock = clock or SystemClock()
        self.compiler = compiler or CommandCompiler()

        self._last_actuate_mono: float | None = None
        # channel -> last known relay state, so unchanged states are not re-sent.
        self._last_states: dict[int, bool] = {}

    def apply(self, plan: ControlPlan) -> list[CommandResult]:
        """Execute a plan, sending only commands whose state actually changed.

        Returns the list of command results (empty if rate-limited or nothing changed).
        """
        now = self.clock.monotonic()
        if self._last_actuate_mono is not None:
            if now - self._last_actuate_mono < self.min_interval_s:
                return []

        results: list[CommandResult] = []
        changed = False

        for command in self.compiler.compile(plan):
            if isinstance(command, RelayCommand):
                key = command.channel
                if self._last_states.get(key) == command.state:
                    continue
                result = self.transport.send(command)
                results.append(result)
                if result.ok:
                    self._last_states[key] = command.state
                    changed = True
            else:
                result = self.transport.send(command)
                results.append(result)
                if result.ok:
                    changed = True

        if changed:
            self._last_actuate_mono = now

        return results

    @property
    def last_states(self) -> dict[int, bool]:
        return dict(self._last_states)

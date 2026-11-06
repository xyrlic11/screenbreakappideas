"""The heartbeat: read sensors, update state, ask the policy, hand out orders.

Everything the app does flows through ``advance``. There is no timer in
this file — ``ui.app`` owns the QTimer and calls in once a second, and the
tests call in as fast as the CPU allows.
"""

from __future__ import annotations

from .models import Command, Config, SensorReading
from .policy import PolicyEngine
from .state import ScreenTimeMachine


class Ticker:
    def __init__(self, config: Config) -> None:
        self.cfg = config
        self.machine = ScreenTimeMachine(config)
        self.policy = PolicyEngine(config, self.machine)

    def advance(self, reading: SensorReading) -> list[Command]:
        snapshot = self.machine.update(reading)
        return self.policy.tick(reading, snapshot)

    # Convenience pass-throughs so the UI never has to reach two levels deep.

    def skip(self, now: float, reason: str = "skipped") -> list[Command]:
        return self.policy.on_skip(now, reason)

    def snooze(self, now: float) -> list[Command]:
        return self.policy.on_snooze(now)

    def break_now(self, now: float) -> list[Command]:
        return self.policy.request_break_now(now)

    def pause(self, now: float, duration_sec: float) -> None:
        self.machine.pause(now, duration_sec)

    def resume(self) -> None:
        self.machine.resume()

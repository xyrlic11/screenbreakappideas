"""Turns the Windows calls into the plain SensorReading the core expects."""

from __future__ import annotations

import time

from ..core.models import SensorReading
from .idle import idle_seconds
from .session import screen_locked


class SensorReader:
    def read(self) -> SensorReading:
        return SensorReading(
            now=time.monotonic(),
            wall=time.time(),
            idle_sec=idle_seconds(),
            screen_locked=screen_locked(),
        )

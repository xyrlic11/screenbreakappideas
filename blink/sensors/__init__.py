"""Everything that touches Windows.

Deliberately tiny: three ctypes calls, no hooks, no elevation, no network.
"""

from .idle import idle_seconds
from .session import lock_workstation, screen_locked
from .reader import SensorReader

__all__ = ["idle_seconds", "screen_locked", "lock_workstation", "SensorReader"]

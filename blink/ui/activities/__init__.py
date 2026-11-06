"""What you actually do during a break.

A black screen is not an eye break — people sit and stare straight at it.
Each of these asks the eyes to do something they cannot do while reading:
change focal distance, track movement, or close.

Adding one means writing a class here and appending it to ALL. The
overlay picks from that list and knows nothing else about them.
"""

from __future__ import annotations

import random

from .base import Activity, BreakContext
from .blink_count import BlinkCount
from .breathe import Breathe
from .look_far import LookFar
from .moving_dot import MovingDot
from .stretch import Stretch

ALL: list[Activity] = [LookFar(), MovingDot(), BlinkCount(), Breathe(), Stretch()]

_last_key: str | None = None


def pick(kind: str, duration_sec: float) -> Activity:
    """Choose an activity that fits, avoiding an immediate repeat."""
    global _last_key
    suitable = [a for a in ALL if kind in a.kinds and duration_sec >= a.min_duration]
    if not suitable:
        suitable = [ALL[0]]

    fresh = [a for a in suitable if a.key != _last_key] or suitable
    chosen = random.choice(fresh)
    _last_key = chosen.key
    return chosen


def by_key(key: str) -> Activity | None:
    return next((a for a in ALL if a.key == key), None)


__all__ = ["ALL", "Activity", "BreakContext", "pick", "by_key"]

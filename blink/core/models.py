"""Data types shared by the whole app.

The single state machine drawn in the design doc is factored into two
enums here, because it really tracks two independent things:

  State  — is screen time accruing right now? (the sensor's answer)
  Phase  — what is the policy doing about it? (the policy's answer)

Keeping them apart means "user went idle during a break" is representable
instead of being an impossible combination.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


class State(str, Enum):
    """What the sensors say about the person in front of the screen."""

    ACTIVE = "active"        # looking at the screen, time is accruing
    IDLE = "idle"            # away from the keyboard, time is frozen
    LOCKED = "locked"        # workstation locked, time is frozen and reset
    PAUSED = "paused"        # user asked us to shut up for a while
    SUSPENDED = "suspended"  # reserved: whitelist / DND (phase 2)


class Phase(str, Enum):
    """What the policy engine is currently doing."""

    COUNTING = "counting"            # waiting for the next deadline
    WARNING = "warning"              # deadline is close, escalating
    BREAK = "break"                  # short break overlay is up
    LONG_WARNING = "long_warning"    # 60s countdown before the long break
    LONG_BREAK = "long_break"        # long break overlay is up
    LOCKED_BREAK = "locked_break"    # asked Windows to lock; watching the outcome


class CommandKind(str, Enum):
    """The only vocabulary the policy uses to talk to the UI."""

    SHOW_TOAST = "show_toast"
    SHOW_EDGE = "show_edge"
    HIDE_EDGE = "hide_edge"
    START_BREAK = "start_break"
    UPDATE_BREAK = "update_break"
    END_BREAK = "end_break"
    SHOW_LONG_WARNING = "show_long_warning"
    UPDATE_LONG_WARNING = "update_long_warning"
    HIDE_LONG_WARNING = "hide_long_warning"
    LOCK_WORKSTATION = "lock_workstation"
    TRAY = "tray"
    LOG = "log"


@dataclass(frozen=True)
class SensorReading:
    """One sample of the outside world, taken once per tick.

    ``now`` is injected rather than read from the clock so tests can hand
    the engine any timeline they like.
    """

    now: float            # monotonic seconds
    wall: float           # time.time(), only used to spot sleep/hibernate gaps
    idle_sec: float       # seconds since the last mouse or key event
    screen_locked: bool


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    payload: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:  # keeps --simulate output readable
        if not self.payload:
            return f"<{self.kind.value}>"
        args = ", ".join(f"{k}={v!r}" for k, v in self.payload.items())
        return f"<{self.kind.value} {args}>"


@dataclass(frozen=True)
class Snapshot:
    """What the state machine concluded from one reading."""

    state: State
    screen_time_sec: float       # continuous screen time since the last short break
    long_time_sec: float         # screen time since the last long break
    idle_sec: float
    just_reset: bool = False
    reset_reason: str | None = None   # 'idle' | 'lock' | 'sleep'


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


# How firmly a break is enforced. The whole app works either way; this is
# the one place the user gets to decide how much it is allowed to insist.
OVERLAY = "overlay"   # fullscreen, blocking. The only way out costs something
POPUP = "popup"       # a corner reminder. You keep working if you want to
LOCK = "lock"         # LockWorkStation(). Long breaks only

# Listed gentlest first: that is the order the settings menu shows them in.
SHORT_ENFORCEMENT = (POPUP, OVERLAY)
LONG_ENFORCEMENT = (POPUP, OVERLAY, LOCK)


@dataclass
class ShortBreakConfig:
    work_sec: int = 1200        # 20 minutes of screen time
    break_sec: int = 20         # 20 second break
    toast_lead_sec: int = 120   # toast this many seconds before the deadline
    edge_lead_sec: int = 10     # screen-edge glow this many seconds before
    enforcement: str = OVERLAY


@dataclass
class LongBreakConfig:
    enabled: bool = True
    work_sec: int = 7200        # every 2 hours
    break_sec: int = 300        # 5 minutes
    warn_lead_sec: int = 60     # unmissable 60s countdown first
    enforcement: str = OVERLAY  # not LOCK by default: it is a big hammer
    snooze_sec: int = 300
    snooze_max: int = 2


@dataclass
class IdleConfig:
    idle_threshold_sec: int = 60     # below this you still count as staring
    reset_threshold_sec: int = 300   # away this long and your eyes really did rest
    sleep_gap_sec: int = 30          # tick gap larger than this means the box slept


@dataclass
class GraceConfig:
    enabled: bool = True
    max_defer_sec: int = 120    # never hold the overlay back longer than this
    quiet_input_sec: int = 3    # fire once the keyboard has been quiet this long


@dataclass
class SkipConfig:
    hold_sec: int = 5           # hold the skip button this long to actually skip


HUD_CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")


@dataclass
class HudConfig:
    """The small readout shown while the window is away."""

    enabled: bool = True
    corner: str = "top_right"


@dataclass
class SoundConfig:
    enabled: bool = True


@dataclass
class Config:
    language: str = "th"
    appearance: str = "system"     # 'system' | 'light' | 'dark'
    display_name: str = ""         # optional; the home page greets by it
    short_break: ShortBreakConfig = field(default_factory=ShortBreakConfig)
    long_break: LongBreakConfig = field(default_factory=LongBreakConfig)
    idle: IdleConfig = field(default_factory=IdleConfig)
    grace: GraceConfig = field(default_factory=GraceConfig)
    skip: SkipConfig = field(default_factory=SkipConfig)
    sound: SoundConfig = field(default_factory=SoundConfig)
    hud: HudConfig = field(default_factory=HudConfig)

    def debug_preset(self) -> "Config":
        """Same shape, seconds instead of minutes.

        Without this you would sit and wait 20 minutes per test run, which
        is exactly how a project like this dies.
        """
        return replace(
            self,
            short_break=ShortBreakConfig(
                work_sec=20, break_sec=5, toast_lead_sec=8, edge_lead_sec=3
            ),
            long_break=replace(
                self.long_break, work_sec=120, break_sec=15, warn_lead_sec=10,
                snooze_sec=15,
            ),
            idle=IdleConfig(
                idle_threshold_sec=10, reset_threshold_sec=30, sleep_gap_sec=30
            ),
            grace=replace(self.grace, max_defer_sec=10),
        )

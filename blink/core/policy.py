"""20-20-20, the escalation ladder, the grace period and the long break.

This is the module that decides *what should happen*. It never draws
anything: it returns a list of ``Command`` objects and the UI obeys them.
Keeping the decisions here is what makes the whole thing testable.
"""

from __future__ import annotations

from uuid import uuid4

from .models import (Command, CommandKind as K, Config, LOCK, Phase, POPUP,
                     SensorReading, Snapshot, State)
from .state import ScreenTimeMachine


class PolicyEngine:
    def __init__(self, config: Config, machine: ScreenTimeMachine) -> None:
        self.cfg = config
        self.machine = machine
        self.phase = Phase.COUNTING

        self._toast_shown = False
        self._edge_shown = False
        self._grace_until: float | None = None

        self._break_ends_at: float | None = None
        self._break_kind = "short"
        self._break_details: dict = {}

        self._long_warn_ends_at: float | None = None
        self._long_extra_sec = 0.0
        self._snoozes_used = 0

        # Locking is a request to Windows, not a result. These track whether
        # the screen actually went away and stayed away.
        self._lock_ends_at: float | None = None
        self._lock_asked_at: float | None = None
        self._lock_engaged = False

        # When the current unbroken run of typing began. Measured in seconds
        # rather than in ticks: the tick loop can be delayed by load or by
        # Windows coalescing timers, and a window counted in ticks would
        # silently stretch to cover half a minute.
        self._typing_since: float | None = None

    # -- the tick ----------------------------------------------------------

    # Input within this long counts as still typing; a longer gap ends the run.
    _KEYSTROKE_GAP_SEC = 1.0
    # How long that run must last before we treat someone as mid-sentence.
    _IN_FLOW_SEC = 3.0

    def tick(self, r: SensorReading, snap: Snapshot) -> list[Command]:
        if r.idle_sec < self._KEYSTROKE_GAP_SEC:
            if self._typing_since is None:
                self._typing_since = r.now
        else:
            self._typing_since = None

        if self.phase is Phase.LOCKED_BREAK:
            cmds = self._tick_locked_break(r)
        elif self.phase in (Phase.BREAK, Phase.LONG_BREAK):
            cmds = self._tick_break(r)
        elif self.phase is Phase.LONG_WARNING:
            cmds = self._tick_long_warning(r)
        else:
            cmds = self._tick_counting(r, snap)

        cmds.append(self._tray(snap))
        return cmds

    def _tick_counting(self, r: SensorReading, snap: Snapshot) -> list[Command]:
        cmds: list[Command] = []

        if snap.just_reset:
            cmds += self._clear_escalation()
            cmds.append(Command(K.LOG, {"event": "counter_reset", "reason": snap.reset_reason}))

        if snap.state is not State.ACTIVE:
            # Idle, paused or locked. Nobody is there to be interrupted, and
            # the counters are frozen anyway, so there is nothing to escalate.
            return cmds

        lb = self.cfg.long_break
        if lb.enabled and snap.long_time_sec >= self._long_deadline():
            # A long break subsumes the short one; don't stack two overlays.
            cmds += self._clear_escalation()
            cmds += self._enter_long_warning(r)
            return cmds

        sb = self.cfg.short_break
        left = sb.work_sec - snap.screen_time_sec

        if not self._toast_shown and left <= sb.toast_lead_sec:
            self._toast_shown = True
            self.phase = Phase.WARNING
            cmds.append(Command(K.SHOW_TOAST, {"seconds_left": max(0, round(left))}))

        if not self._edge_shown and left <= sb.edge_lead_sec:
            self._edge_shown = True
            self.phase = Phase.WARNING
            cmds.append(Command(K.SHOW_EDGE, {"seconds_left": max(0, round(left))}))

        if left <= 0:
            if self._grace_holds(r):
                cmds.append(Command(K.LOG, {"event": "grace_defer"}))
            else:
                cmds += self._start_break(r, "short", self._next_break_sec())

        return cmds

    # -- breaks ------------------------------------------------------------

    def _tick_break(self, r: SensorReading) -> list[Command]:
        assert self._break_ends_at is not None
        remaining = self._break_ends_at - r.now
        if remaining > 0:
            return [Command(K.UPDATE_BREAK, {
                "kind": self._break_kind,
                "remaining_sec": remaining,
            })]
        return self._finish_break("completed")

    def _start_break(self, r: SensorReading, kind: str, duration: float,
                     *, scheduled: bool = True) -> list[Command]:
        self._identify_break(kind, duration, scheduled)
        self.phase = Phase.BREAK if kind == "short" else Phase.LONG_BREAK
        self._break_kind = kind
        self._break_ends_at = r.now + duration
        self._grace_until = None
        cmds: list[Command] = []
        if self._edge_shown:
            cmds.append(Command(K.HIDE_EDGE))
        self._toast_shown = False
        self._edge_shown = False
        cmds.append(Command(K.START_BREAK, {
            "kind": kind,
            "duration_sec": duration,
            "remaining_sec": duration,
        }))
        return cmds

    def _identify_break(self, kind: str, duration: float, scheduled: bool) -> None:
        screen_sec = (self.machine.long_time_sec if kind == "long"
                      else self.machine.screen_time_sec)
        config = self.cfg.long_break if kind == "long" else self.cfg.short_break
        self._break_details = {
            "event_id": uuid4().hex,
            "scheduled": scheduled,
            "planned_sec": duration,
            "reward_screen_sec": screen_sec,
            "interval_sec": config.work_sec,
        }

    def _end_command(self, kind: str, outcome: str) -> Command:
        return Command(K.END_BREAK, {
            "kind": kind, "outcome": outcome, **self._break_details,
        })

    def _finish_break(self, outcome: str) -> list[Command]:
        """outcome: 'completed' | 'skipped' | 'emergency'"""
        kind = self._break_kind
        if kind == "long":
            self._reset_long_cycle()
        else:
            self.machine.consume_short_break()

        self.phase = Phase.COUNTING
        self._break_ends_at = None
        cmds = [self._end_command(kind, outcome)]
        cmds += self._clear_escalation()
        cmds.append(Command(K.LOG, {"event": "break_finished", "kind": kind, "outcome": outcome}))
        return cmds

    def _next_break_sec(self) -> float:
        """How long the next short break lasts.

        Phase 2's eye-debt system adds carried debt here and nowhere else,
        so adding it later touches exactly one line.
        """
        return float(self.cfg.short_break.break_sec)

    # -- long break --------------------------------------------------------

    def _long_deadline(self) -> float:
        return self.cfg.long_break.work_sec + self._long_extra_sec

    def _snoozes_left(self) -> int:
        return max(0, self.cfg.long_break.snooze_max - self._snoozes_used)

    def _enter_long_warning(self, r: SensorReading) -> list[Command]:
        if self.cfg.long_break.enforcement == POPUP:
            # A corner reminder needs no sixty second countdown: there is
            # nothing to save your work from.
            return self._start_break(r, "long", float(self.cfg.long_break.break_sec))

        self.phase = Phase.LONG_WARNING
        self._long_warn_ends_at = r.now + self.cfg.long_break.warn_lead_sec
        return [Command(K.SHOW_LONG_WARNING, {
            "remaining_sec": float(self.cfg.long_break.warn_lead_sec),
            "snoozes_left": self._snoozes_left(),
            "will_lock": self.cfg.long_break.enforcement == LOCK,
        })]

    def _tick_long_warning(self, r: SensorReading) -> list[Command]:
        assert self._long_warn_ends_at is not None
        remaining = self._long_warn_ends_at - r.now
        if remaining > 0:
            return [Command(K.UPDATE_LONG_WARNING, {
                "remaining_sec": remaining,
                "snoozes_left": self._snoozes_left(),
                "will_lock": self.cfg.long_break.enforcement == LOCK,
            })]

        cmds = [Command(K.HIDE_LONG_WARNING)]
        self._long_warn_ends_at = None
        if self.cfg.long_break.enforcement == LOCK:
            # Ask Windows to lock, then watch. Crediting the break here would
            # mean unlocking three seconds later bought a full five minutes —
            # making the harshest setting in the app the easiest one to dodge.
            self.phase = Phase.LOCKED_BREAK
            self._identify_break("long", self.cfg.long_break.break_sec, scheduled=True)
            self._lock_asked_at = r.now
            self._lock_ends_at = r.now + self.cfg.long_break.break_sec
            self._lock_engaged = False
            cmds.append(Command(K.LOCK_WORKSTATION))
            cmds.append(Command(K.LOG, {"event": "long_break_lock_requested"}))
        else:
            cmds += self._start_break(r, "long", float(self.cfg.long_break.break_sec))
        return cmds

    # How long to wait for the lock screen to appear before concluding that
    # LockWorkStation did not take effect.
    _LOCK_GRACE_SEC = 10.0

    def _tick_locked_break(self, r: SensorReading) -> list[Command]:
        assert self._lock_ends_at is not None and self._lock_asked_at is not None
        if r.screen_locked:
            self._lock_engaged = True
            if r.now >= self._lock_ends_at:
                return self._finish_locked_break("completed")
            return []

        if self._lock_engaged:
            # Back early. The cycle still resets — nagging the moment someone
            # sits down is what gets an app uninstalled — but the record says
            # what happened, exactly as the skip button does.
            return self._finish_locked_break("skipped")

        if r.now - self._lock_asked_at >= self._LOCK_GRACE_SEC:
            # The lock never engaged at all; do not sit in this phase forever.
            return self._finish_locked_break("skipped")
        return []

    def _finish_locked_break(self, outcome: str) -> list[Command]:
        self._reset_long_cycle()
        self.phase = Phase.COUNTING
        self._lock_ends_at = self._lock_asked_at = None
        self._lock_engaged = False
        return [
            self._end_command("long", outcome),
            Command(K.LOG, {"event": "long_break_finished", "kind": "long",
                            "outcome": outcome}),
        ]

    def _reset_long_cycle(self) -> None:
        self.machine.consume_long_break()
        self._long_extra_sec = 0.0
        self._snoozes_used = 0

    # -- things the user does ---------------------------------------------

    def on_skip(self, now: float, reason: str = "skipped") -> list[Command]:
        """Skip button (held) or emergency button (single click)."""
        if self.phase in (Phase.BREAK, Phase.LONG_BREAK):
            return self._finish_break(reason)
        if self.phase is Phase.LOCKED_BREAK:
            return self._finish_locked_break(reason)
        if self.phase is Phase.LONG_WARNING:
            # Bailing out of the warning cancels this long break outright,
            # otherwise it would re-fire one second later and feel broken.
            self._reset_long_cycle()
            self.phase = Phase.COUNTING
            self._long_warn_ends_at = None
            return [
                Command(K.HIDE_LONG_WARNING),
                Command(K.LOG, {"event": "long_break_finished", "outcome": reason}),
            ]
        return []

    def on_snooze(self, now: float) -> list[Command]:
        if self.phase is not Phase.LONG_WARNING or self._snoozes_left() <= 0:
            return []
        self._snoozes_used += 1
        self._long_extra_sec += self.cfg.long_break.snooze_sec
        self.phase = Phase.COUNTING
        self._long_warn_ends_at = None
        return [
            Command(K.HIDE_LONG_WARNING),
            Command(K.LOG, {"event": "long_break_snoozed", "used": self._snoozes_used}),
        ]

    def request_break_now(self, now: float) -> list[Command]:
        if self.phase in (Phase.BREAK, Phase.LONG_BREAK, Phase.LONG_WARNING,
                          Phase.LOCKED_BREAK):
            return []
        r = SensorReading(now=now, wall=now, idle_sec=0.0, screen_locked=False)
        return self._start_break(r, "short", self._next_break_sec(), scheduled=False)

    # -- helpers -----------------------------------------------------------

    def _grace_holds(self, r: SensorReading) -> bool:
        """Should we hold the overlay back for a moment?

        Being yanked out of a sentence mid-word is the single thing most
        likely to get this app uninstalled, so if the user is clearly in
        flow we wait for a gap — but never longer than the ceiling.
        """
        if self._grace_until is None:
            in_flow = (self._typing_since is not None
                       and r.now - self._typing_since >= self._IN_FLOW_SEC)
            busy = self.cfg.grace.enabled and in_flow
            self._grace_until = r.now + self.cfg.grace.max_defer_sec if busy else r.now
        if r.now >= self._grace_until:
            return False
        return r.idle_sec < self.cfg.grace.quiet_input_sec

    def _clear_escalation(self) -> list[Command]:
        cmds = [Command(K.HIDE_EDGE)] if self._edge_shown else []
        self._toast_shown = False
        self._edge_shown = False
        self._grace_until = None
        if self.phase is Phase.WARNING:
            self.phase = Phase.COUNTING
        return cmds

    def _tray(self, snap: Snapshot) -> Command:
        lb = self.cfg.long_break
        return Command(K.TRAY, {
            "state": snap.state.value,
            "phase": self.phase.value,
            "screen_time_sec": snap.screen_time_sec,
            "next_break_in_sec": max(0.0, self.cfg.short_break.work_sec - snap.screen_time_sec),
            "next_long_break_in_sec": (
                max(0.0, self._long_deadline() - snap.long_time_sec) if lb.enabled else None
            ),
        })

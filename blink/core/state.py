"""Screen-time accounting.

The only question this module answers is "how long have you been looking
at the screen without a real break?". It deliberately knows nothing about
overlays, warnings or 20-20-20.
"""

from __future__ import annotations

from .models import Config, SensorReading, Snapshot, State


class ScreenTimeMachine:
    def __init__(self, config: Config) -> None:
        self.cfg = config
        self.screen_time_sec: float = 0.0
        self.long_time_sec: float = 0.0
        self.state: State = State.ACTIVE
        self.paused_until: float | None = None
        self._last_now: float | None = None
        self._last_wall: float | None = None
        self._locked_since: float | None = None

    # -- external events ---------------------------------------------------

    def pause(self, now: float, duration_sec: float) -> None:
        self.paused_until = now + duration_sec

    def resume(self) -> None:
        self.paused_until = None

    def consume_short_break(self) -> None:
        self.screen_time_sec = 0.0

    def consume_long_break(self) -> None:
        self.screen_time_sec = 0.0
        self.long_time_sec = 0.0

    # -- the tick ----------------------------------------------------------

    def update(self, r: SensorReading) -> Snapshot:
        reset_reason = self._detect_sleep_gap(r)
        delta = self._elapsed(r, slept=reset_reason is not None)

        if self.paused_until is not None and r.now >= self.paused_until:
            self.paused_until = None
        if not r.screen_locked:
            self._locked_since = None

        if r.screen_locked:
            # Nobody is looking, so freeze — but do not treat it as a rest
            # until it has lasted as long as any other absence would need to.
            # A one second Win+L used to wipe the whole session, and the same
            # signal fires for the UAC secure desktop, so every elevation
            # prompt silently reset the clock too.
            self.state = State.LOCKED
            if self._locked_since is None:
                self._locked_since = r.now
            if r.now - self._locked_since >= self.cfg.idle.reset_threshold_sec:
                reset_reason = reset_reason or "lock"
        elif self.paused_until is not None:
            # Paused freezes the counters but must not reset them, otherwise
            # "pause for an hour" becomes a free way to wipe your screen time.
            self.state = State.PAUSED
        elif r.idle_sec >= self.cfg.idle.reset_threshold_sec:
            self.state = State.IDLE
            reset_reason = reset_reason or "idle"
        elif r.idle_sec >= self.cfg.idle.idle_threshold_sec:
            # Away, but not long enough to count as resting your eyes.
            self.state = State.IDLE
        else:
            # Under a minute of stillness still counts as staring: reading a
            # page without touching the mouse is exactly the case we care about.
            self.state = State.ACTIVE
            self.screen_time_sec += delta
            self.long_time_sec += delta

        just_reset = False
        if reset_reason is not None:
            # The reason stays true for every tick the user is still away, so
            # report only the tick that actually cleared something. Otherwise
            # a ten minute lunch break is six hundred identical events.
            just_reset = self.screen_time_sec > 0.0 or self.long_time_sec > 0.0
            self.screen_time_sec = 0.0
            self.long_time_sec = 0.0

        return Snapshot(
            state=self.state,
            screen_time_sec=self.screen_time_sec,
            long_time_sec=self.long_time_sec,
            idle_sec=r.idle_sec,
            just_reset=just_reset,
            reset_reason=reset_reason,
        )

    # -- helpers -----------------------------------------------------------

    def _detect_sleep_gap(self, r: SensorReading) -> str | None:
        """Spot suspend/hibernate by looking for a hole in the tick stream.

        Cheaper and broader than subscribing to power notifications: it also
        covers a stopped process, a debugger breakpoint and a clock change.
        """
        gap = None if self._last_wall is None else r.wall - self._last_wall
        self._last_wall = r.wall
        if gap is None:
            return None
        if gap > self.cfg.idle.sleep_gap_sec or gap < -5.0:
            return "sleep"
        return None

    def _elapsed(self, r: SensorReading, slept: bool) -> float:
        last, self._last_now = self._last_now, r.now
        if last is None or slept:
            return 0.0
        return max(0.0, r.now - last)

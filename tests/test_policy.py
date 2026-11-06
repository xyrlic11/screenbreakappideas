"""20-20-20, the escalation ladder, grace period, skips and the long break."""

from __future__ import annotations

import time
from dataclasses import replace

from blink.core.models import (CommandKind as K, Config, LOCK, LongBreakConfig,
                               OVERLAY, Phase, POPUP)

from conftest import Driver, has, only


def no_long_break(cfg: Config | None = None) -> Config:
    """Most short-break tests don't want a 2-hour break in the way."""
    cfg = cfg or Config()
    return replace(cfg, long_break=replace(cfg.long_break, enabled=False))


# --------------------------------------------------------------------------
# The escalation ladder
# --------------------------------------------------------------------------


def test_ladder_fires_in_order_toast_then_edge_then_overlay():
    d = Driver(no_long_break())
    d.run(1250, idle=2.0)   # idle 2s: present, but not typing

    toast = d.first_tick_of(K.SHOW_TOAST)
    edge = d.first_tick_of(K.SHOW_EDGE)
    overlay = d.first_tick_of(K.START_BREAK)

    assert toast is not None and edge is not None and overlay is not None
    assert toast < edge < overlay
    # 20 minutes of screen time, warned 2 minutes and 10 seconds ahead.
    assert abs(toast - (1200 - 120)) <= 2
    assert abs(edge - (1200 - 10)) <= 2
    assert abs(overlay - 1200) <= 2


def test_nothing_happens_before_the_first_warning():
    d = Driver(no_long_break())
    cmds = d.run(1000, idle=2.0)
    assert not has(cmds, K.SHOW_TOAST)
    assert not has(cmds, K.START_BREAK)


def test_break_lasts_twenty_seconds_then_resets_the_counter():
    d = Driver(no_long_break())
    d.run(1205, idle=2.0)
    assert d.ticker.policy.phase is Phase.BREAK

    d.run(25, idle=2.0)
    assert d.ticker.policy.phase is Phase.COUNTING
    end = only([c for _, c in d.history if c.kind is K.END_BREAK], K.END_BREAK)
    assert end.payload["outcome"] == "completed"
    assert d.screen_time < 30   # counter restarted, not still at 1200


def test_countdown_is_reported_every_second_of_the_break():
    d = Driver(no_long_break())
    d.run(1201, idle=2.0)
    d.run(10, idle=2.0)
    remaining = [p["remaining_sec"] for p in d.payloads(K.UPDATE_BREAK)]
    assert remaining == sorted(remaining, reverse=True)
    assert max(remaining) <= 20


def test_the_deadline_cannot_arrive_at_an_empty_desk():
    """Walking away freezes the counter, so it never reaches 20 minutes."""
    d = Driver(no_long_break())
    d.run(1100, idle=2.0)
    cmds = d.idle_for(600)   # past the idle threshold and past the reset
    assert not has(cmds, K.START_BREAK)
    assert d.screen_time == 0.0


def test_sitting_still_and_reading_does_count_towards_the_break():
    """The counterpart: no input for 50s is reading, not resting."""
    d = Driver(no_long_break())
    d.run(1150, idle=2.0)
    cmds = d.idle_for(55)
    assert has(cmds, K.START_BREAK)


# --------------------------------------------------------------------------
# Grace period
# --------------------------------------------------------------------------


def test_typing_at_the_deadline_defers_the_overlay():
    d = Driver(no_long_break())
    cmds = d.run(1215, idle=0.0)   # typing flat out
    assert not has(cmds, K.START_BREAK)
    assert any(p.get("event") == "grace_defer" for p in d.payloads(K.LOG))


def test_the_overlay_lands_in_the_first_gap_in_typing():
    d = Driver(no_long_break())
    d.run(1210, idle=0.0)
    assert d.first_tick_of(K.START_BREAK) is None

    d.tick(idle=1.0)
    d.tick(idle=2.0)
    assert d.first_tick_of(K.START_BREAK) is None   # 2s pause is not a gap yet
    d.tick(idle=3.0)
    assert d.first_tick_of(K.START_BREAK) is not None


def test_grace_has_a_hard_ceiling():
    """Two minutes of nonstop typing is not a licence to skip the break."""
    d = Driver(no_long_break())
    d.run(1200 + 130, idle=0.0)
    overlay = d.first_tick_of(K.START_BREAK)
    assert overlay is not None
    assert 1200 + 118 <= overlay <= 1200 + 124


def test_no_grace_for_someone_who_is_just_sitting_there():
    d = Driver(no_long_break())
    d.run(1205, idle=2.0)   # present, not typing: interrupt away
    assert abs(d.first_tick_of(K.START_BREAK) - 1200) <= 2


def test_grace_can_be_switched_off():
    cfg = no_long_break()
    cfg = replace(cfg, grace=replace(cfg.grace, enabled=False))
    d = Driver(cfg)
    d.run(1205, idle=0.0)
    assert abs(d.first_tick_of(K.START_BREAK) - 1200) <= 2


# --------------------------------------------------------------------------
# Skip and emergency
# --------------------------------------------------------------------------


def test_skip_ends_the_break_and_still_resets_the_counter():
    d = Driver(no_long_break())
    d.run(1205, idle=2.0)
    cmds = d.ticker.skip(d.now, "skipped")

    assert has(cmds, K.END_BREAK)
    assert d.ticker.policy.phase is Phase.COUNTING
    assert d.screen_time == 0.0


def test_skip_and_emergency_are_recorded_separately():
    """Phase 2 needs to tell 'I chose to skip' from 'something was on fire'."""
    for reason in ("skipped", "emergency"):
        d = Driver(no_long_break())
        d.run(1205, idle=2.0)
        cmds = d.ticker.skip(d.now, reason)
        assert only(cmds, K.END_BREAK).payload["outcome"] == reason


def test_skip_outside_a_break_does_nothing():
    d = Driver(no_long_break())
    d.run(100)
    assert d.ticker.skip(d.now) == []


def test_break_now_from_the_tray():
    d = Driver(no_long_break())
    d.run(100)
    cmds = d.ticker.break_now(d.now)
    assert has(cmds, K.START_BREAK)
    assert d.ticker.policy.phase is Phase.BREAK


# --------------------------------------------------------------------------
# Long break
# --------------------------------------------------------------------------


def long_break_cfg(**kw) -> Config:
    base = LongBreakConfig(work_sec=7200, break_sec=300, warn_lead_sec=60,
                           snooze_sec=300, snooze_max=2)
    return Config(long_break=replace(base, **kw))


def test_long_break_warns_a_full_minute_before_it_acts():
    d = Driver(long_break_cfg(enforcement=OVERLAY))
    d.run(7210, idle=2.0)
    warn = d.first_tick_of(K.SHOW_LONG_WARNING)
    assert warn is not None and abs(warn - 7200) <= 3
    assert d.ticker.policy.phase is Phase.LONG_WARNING
    assert not has([c for _, c in d.history], K.LOCK_WORKSTATION)


def test_long_break_falls_back_to_an_overlay_when_locking_is_off():
    d = Driver(long_break_cfg(enforcement=OVERLAY))
    d.run(7300, idle=2.0)
    starts = [p for p in d.payloads(K.START_BREAK) if p["kind"] == "long"]
    assert starts and starts[0]["duration_sec"] == 300
    assert d.first_tick_of(K.LOCK_WORKSTATION) is None


def test_long_break_asks_windows_to_lock_then_waits():
    d = Driver(long_break_cfg(enforcement=LOCK))
    d.run(7270, idle=2.0)

    lock = d.first_tick_of(K.LOCK_WORKSTATION)
    assert lock is not None
    assert abs(lock - (7200 + 60)) <= 3
    # Asking is not the same as being credited with the break.
    assert d.ticker.policy.phase is Phase.LOCKED_BREAK
    assert d.long_time > 7000


def test_a_lock_that_holds_for_the_whole_break_counts_as_completed():
    d = Driver(long_break_cfg(enforcement=LOCK))
    d.run(7265, idle=2.0)
    d.run(310, locked=True)          # screen actually stays away for 5 minutes

    end = [c for _, c in d.history if c.kind is K.END_BREAK][-1]
    assert end.payload == {"kind": "long", "outcome": "completed"}
    assert d.ticker.policy.phase is Phase.COUNTING
    assert d.long_time == 0.0


def test_unlocking_after_three_seconds_does_not_buy_a_five_minute_break():
    """The harshest setting in the app was the easiest one to dodge.

    The cycle still resets — nagging someone the moment they sit down is
    how an app gets uninstalled — but the record says skipped, not
    completed, so the statistics stop lying.
    """
    d = Driver(long_break_cfg(enforcement=LOCK))
    d.run(7265, idle=2.0)
    d.run(3, locked=True)            # locked
    d.run(2, idle=0.0)               # and straight back

    end = [c for _, c in d.history if c.kind is K.END_BREAK][-1]
    assert end.payload["outcome"] == "skipped"
    assert d.ticker.policy.phase is Phase.COUNTING


def test_returning_early_still_resets_so_it_cannot_nag_in_a_loop():
    d = Driver(long_break_cfg(enforcement=LOCK))
    d.run(7265, idle=2.0)
    d.run(3, locked=True)
    d.run(120, idle=2.0)             # two minutes of work afterwards

    warnings = [t for t, c in d.history if c.kind is K.SHOW_LONG_WARNING]
    assert len(warnings) == 1        # not re-fired the moment they came back


def test_a_lock_that_never_engages_does_not_wedge_the_phase():
    """If LockWorkStation silently fails, the app must not stop working."""
    d = Driver(long_break_cfg(enforcement=LOCK))
    d.run(7280, idle=2.0)            # never reports locked

    assert d.ticker.policy.phase is Phase.COUNTING
    end = [c for _, c in d.history if c.kind is K.END_BREAK][-1]
    assert end.payload["outcome"] == "skipped"


def test_snooze_pushes_the_long_break_out_and_runs_out():
    d = Driver(long_break_cfg(enforcement=LOCK, snooze_sec=300, snooze_max=2))
    d.run(7210, idle=2.0)

    assert has(d.ticker.snooze(d.now), K.HIDE_LONG_WARNING)
    assert d.ticker.policy.phase is Phase.COUNTING
    d.run(310, idle=2.0)
    assert d.ticker.policy.phase is Phase.LONG_WARNING   # came back on schedule

    assert has(d.ticker.snooze(d.now), K.HIDE_LONG_WARNING)
    d.run(310, idle=2.0)
    assert d.ticker.snooze(d.now) == []    # two snoozes is the limit

    d.run(70, idle=2.0)
    assert d.first_tick_of(K.LOCK_WORKSTATION) is not None


def test_emergency_during_the_warning_cancels_the_whole_cycle():
    """It must not re-fire one second later, or the button feels broken."""
    d = Driver(long_break_cfg(enforcement=LOCK))
    d.run(7210, idle=2.0)
    d.ticker.skip(d.now, "emergency")

    d.run(120, idle=2.0)
    assert d.first_tick_of(K.LOCK_WORKSTATION) is None
    assert d.ticker.policy.phase is not Phase.LONG_WARNING


def test_a_long_break_subsumes_the_short_one_no_stacked_overlays():
    d = Driver(long_break_cfg(enforcement=OVERLAY))
    d.run(7210, idle=2.0)
    at_warning = [t for t, c in d.history if c.kind is K.SHOW_LONG_WARNING][0]
    short_after = [t for t, c in d.history
                   if c.kind is K.START_BREAK and c.payload["kind"] == "short"
                   and t >= at_warning]
    assert not short_after


# --------------------------------------------------------------------------
# The claim that makes all of the above cheap to run
# --------------------------------------------------------------------------


def test_eight_hours_of_simulated_time_runs_in_well_under_a_second():
    d = Driver(Config())
    started = time.perf_counter()
    d.run(8 * 3600, idle=2.0)
    elapsed = time.perf_counter() - started

    assert elapsed < 2.0, f"core is doing real work somewhere: {elapsed:.2f}s"
    # A full working day should produce roughly one short break per 20 min.
    breaks = [p for p in d.payloads(K.START_BREAK) if p["kind"] == "short"]
    assert 18 <= len(breaks) <= 24


# --------------------------------------------------------------------------
# Enforcement: take over the screen, or just say something
# --------------------------------------------------------------------------


def test_popup_mode_produces_exactly_the_same_commands():
    """The policy does not know how a break is drawn, and must not start to.

    Everything downstream — recording, the tray, the counters — depends on
    START/UPDATE/END arriving the same way whichever presenter is used.
    """
    forced = Driver(no_long_break())
    forced.run(1235, idle=2.0)

    gentle_cfg = no_long_break()
    gentle_cfg = replace(gentle_cfg,
                         short_break=replace(gentle_cfg.short_break, enforcement=POPUP))
    gentle = Driver(gentle_cfg)
    gentle.run(1235, idle=2.0)

    def shape(driver):
        return [(tick, c.kind) for tick, c in driver.history if c.kind is not K.TRAY]

    assert shape(forced) == shape(gentle)


def test_a_reminder_long_break_skips_the_sixty_second_countdown():
    """The countdown exists to let you save your work before the screen goes.

    A card in the corner takes nothing away, so warning about it first is
    pure nagging.
    """
    d = Driver(long_break_cfg(enforcement=POPUP))
    d.run(7250, idle=2.0)

    assert d.first_tick_of(K.SHOW_LONG_WARNING) is None
    assert d.first_tick_of(K.LOCK_WORKSTATION) is None
    start = [t for t, c in d.history
             if c.kind is K.START_BREAK and c.payload["kind"] == "long"]
    assert start and abs(start[0] - 7200) <= 3


def test_reminder_mode_never_reaches_lockworkstation():
    for mode in (OVERLAY, POPUP):
        d = Driver(long_break_cfg(enforcement=mode))
        d.run(7400, idle=2.0)
        assert d.first_tick_of(K.LOCK_WORKSTATION) is None, mode


def test_the_warning_says_whether_the_screen_will_actually_go():
    for mode, expected in ((LOCK, True), (OVERLAY, False)):
        d = Driver(long_break_cfg(enforcement=mode))
        d.run(7210, idle=2.0)
        assert d.payloads(K.SHOW_LONG_WARNING)[0]["will_lock"] is expected, mode


def test_dismissing_a_reminder_counts_as_a_skip():
    cfg = no_long_break()
    cfg = replace(cfg, short_break=replace(cfg.short_break, enforcement=POPUP))
    d = Driver(cfg)
    d.run(1205, idle=2.0)

    cmds = d.ticker.skip(d.now, "skipped")
    assert only(cmds, K.END_BREAK).payload["outcome"] == "skipped"
    assert d.screen_time == 0.0


# --------------------------------------------------------------------------
# A tick loop that runs late
# --------------------------------------------------------------------------


def ticks_every(step: float, seconds: float, idle: float, cfg: Config):
    """Replay a timeline whose ticks arrive `step` seconds apart.

    Windows coalesces timers for background processes and a loaded machine
    delays them further, so one tick is never reliably one second.
    """
    from blink.core.models import SensorReading
    from blink.core.ticker import Ticker

    ticker = Ticker(cfg)
    now, out = 0.0, []
    while now < seconds:
        now += step
        out += ticker.advance(SensorReading(now=now, wall=1_700_000_000 + now,
                                            idle_sec=idle, screen_locked=False))
    return ticker, out


def test_screen_time_survives_a_late_tick_loop():
    """Accrual is measured from the clock, not counted in ticks."""
    cfg = no_long_break()
    for step in (1, 2, 5, 10):
        ticker, _ = ticks_every(step, 600, 2.0, cfg)
        assert abs(ticker.machine.screen_time_sec - 600) <= step


def test_the_break_still_lands_when_ticks_are_sparse():
    cfg = no_long_break()
    for step in (1, 5, 10):
        ticker, cmds = ticks_every(step, 1300, 2.0, cfg)
        starts = [c for c in cmds if c.kind is K.START_BREAK]
        assert len(starts) == 1, f"step={step}"


def test_flow_detection_does_not_stretch_with_the_tick_rate():
    """Someone sitting still is interrupted immediately at any tick rate.

    This used to be five booleans in a deque, one per tick, which quietly
    became a fifty second window whenever the loop ran at a tenth of speed.
    """
    cfg = no_long_break()
    for step in (1, 5, 10):
        ticker, cmds = ticks_every(step, 1220, 2.0, cfg)      # present, not typing
        assert any(c.kind is K.START_BREAK for c in cmds), f"step={step}"


def test_typing_still_earns_grace_at_any_tick_rate():
    cfg = no_long_break()
    for step in (1, 2, 5):
        ticker, cmds = ticks_every(step, 1215, 0.0, cfg)      # typing flat out
        assert not any(c.kind is K.START_BREAK for c in cmds), f"step={step}"
        assert any(c.kind is K.LOG and c.payload.get("event") == "grace_defer"
                   for c in cmds), f"step={step}"

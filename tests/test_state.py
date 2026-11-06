"""Screen-time accounting: what counts as staring, and what resets the clock."""

from __future__ import annotations

from blink.core.models import CommandKind, Config, State

from conftest import Driver


def test_active_time_accrues_one_second_per_tick():
    d = Driver()
    d.run(100)
    # The first tick has no predecessor to measure against, hence 99 not 100.
    assert d.screen_time == 99.0


def test_reading_without_touching_anything_still_counts():
    """Under a minute of stillness is reading, not resting."""
    d = Driver()
    d.idle_for(59)
    assert d.screen_time == 58.0
    assert d.ticker.machine.state is State.ACTIVE


def test_a_minute_away_freezes_the_counter():
    d = Driver()
    d.run(100)
    d.idle_for(70)          # the first 59s of this still count as reading
    frozen_at = d.screen_time
    assert d.ticker.machine.state is State.IDLE

    d.run(120, idle=200.0)  # stay away
    assert d.screen_time == frozen_at


def test_five_minutes_away_resets_the_counter():
    d = Driver()
    d.run(600)
    d.idle_for(301)
    assert d.screen_time == 0.0
    assert d.long_time == 0.0


def test_a_locked_screen_freezes_the_counter():
    """Locking says nobody is looking. It does not say they rested."""
    d = Driver()
    d.run(600)
    before = d.screen_time

    d.run(30, locked=True)
    assert d.ticker.machine.state is State.LOCKED
    assert d.screen_time == before


def test_a_lock_long_enough_to_be_a_rest_resets_like_any_other_absence():
    d = Driver()
    d.run(600)
    d.run(301, locked=True)          # the same threshold as walking away
    assert d.screen_time == 0.0
    assert d.long_time == 0.0


def test_a_one_second_lock_is_not_a_free_reset():
    """Win+L, unlock, and you have skipped nothing.

    Tapping Win+L used to wipe both counters outright, which made the two
    hour long break avoidable forever for the price of one keystroke.
    """
    d = Driver()
    d.run(1000)
    before_screen, before_long = d.screen_time, d.long_time

    d.run(1, locked=True)
    d.run(1)                          # back at the keyboard immediately

    assert d.screen_time >= before_screen
    assert d.long_time >= before_long


def test_a_uac_prompt_does_not_wipe_the_session():
    """OpenInputDesktop fails for the secure desktop as well as the lock
    screen, so every elevation prompt looks exactly like a lock."""
    d = Driver()
    d.run(900)
    before = d.long_time

    d.run(4, locked=True)             # UAC prompt on screen
    d.run(5)                          # dismissed

    assert d.long_time >= before


def test_a_lock_that_repeats_never_accumulates_towards_a_reset():
    """Locking and unlocking all afternoon must not add up to a rest."""
    d = Driver()
    d.run(600)
    before = d.screen_time
    for _ in range(20):
        d.run(10, locked=True)
        d.run(2)
    assert d.screen_time > before


def test_sleep_gap_resets_and_is_not_credited_as_screen_time():
    """Lid closed for two hours must not come back as two hours of staring."""
    d = Driver()
    d.run(600)
    d.sleep_gap(7200)
    assert d.screen_time == 0.0

    d.run(10)
    assert d.screen_time == 10.0  # counting resumed cleanly from zero


def test_clock_moving_backwards_is_treated_as_a_gap():
    d = Driver()
    d.run(600)
    d.tick(wall_gap=-3600)  # DST change, NTP correction, user fiddling
    assert d.screen_time == 0.0


def test_pause_freezes_without_wiping_progress():
    """Otherwise 'pause for an hour' would be a free reset."""
    d = Driver()
    d.run(600)
    before = d.screen_time
    d.ticker.pause(d.now, 3600)

    d.run(300)
    assert d.ticker.machine.state is State.PAUSED
    assert d.screen_time == before


def test_pause_expires_on_its_own():
    d = Driver()
    d.ticker.pause(d.now, 10)
    d.run(9)
    assert d.ticker.machine.state is State.PAUSED
    d.run(5)
    assert d.ticker.machine.state is State.ACTIVE


def test_long_counter_survives_short_breaks_but_not_a_real_absence():
    d = Driver(Config())
    d.run(1500)          # past one short break
    assert d.long_time > 1200
    assert d.screen_time < 1200   # short counter was consumed by the break

    d.idle_for(301)
    assert d.long_time == 0.0


def test_a_reset_is_announced_once_not_once_a_second():
    """The reason stays true while you are away; the event must not repeat.

    Phase 2 writes these into SQLite, where a ten minute lunch would
    otherwise land as six hundred identical rows.
    """
    d = Driver()
    d.run(600)
    d.run(600, idle=400.0)            # away for ten minutes

    resets = [c for _, c in d.history
              if c.kind is CommandKind.LOG and c.payload.get("event") == "counter_reset"]
    assert len(resets) == 1


def test_a_second_absence_is_announced_again():
    """Announcing once must not mean announcing only ever once."""
    d = Driver()
    for _ in range(3):
        d.run(400)
        d.run(400, idle=400.0)

    resets = [c for _, c in d.history
              if c.kind is CommandKind.LOG and c.payload.get("event") == "counter_reset"]
    assert len(resets) == 3

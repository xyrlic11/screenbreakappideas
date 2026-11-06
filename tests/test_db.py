"""Break history: the logical day boundary, aggregation and the streak."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from blink.storage.db import History, day_of


@pytest.fixture
def history(tmp_path):
    db = History(tmp_path / "test.sqlite3")
    yield db
    db.close()


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, day, hour, minute)


# -- the day boundary ------------------------------------------------------


def test_work_past_midnight_still_counts_as_the_same_day():
    """Finishing at 2am belongs to the day you started, not the calendar's."""
    assert day_of(at(10, 23, 30)) == "2026-03-10"
    assert day_of(at(11, 1, 45)) == "2026-03-10"
    assert day_of(at(11, 3, 59)) == "2026-03-10"


def test_the_new_day_starts_at_four():
    assert day_of(at(11, 4, 0)) == "2026-03-11"
    assert day_of(at(11, 9, 0)) == "2026-03-11"


# -- aggregation -----------------------------------------------------------


def test_counts_split_by_outcome(history):
    for outcome in ("completed", "completed", "skipped", "emergency"):
        history.record_break("short", outcome, 20, 1200, at(10, 10))

    stats = history.stats_for("2026-03-10")
    assert (stats.completed, stats.skipped, stats.emergency) == (2, 1, 1)
    assert stats.due == 4
    assert stats.compliance == 0.5


def test_a_day_with_nothing_due_is_not_a_failure(history):
    """Zero out of zero is 1.0, otherwise a day off reads as 0% compliance."""
    assert history.stats_for("2026-03-09").compliance == 1.0


def test_long_breaks_counted_separately(history):
    history.record_break("long", "completed", 300, 7200, at(10, 12))
    history.record_break("long", "skipped", 300, 7200, at(10, 15))
    stats = history.stats_for("2026-03-10")
    assert stats.long_breaks == 1      # only completed ones
    assert stats.due == 2


def test_recent_fills_in_empty_days(history):
    history.record_break("short", "completed", 20, 1200)
    week = history.recent(7)
    assert len(week) == 7
    assert week[-1].day == day_of(datetime.now())    # today is last
    assert [d.day for d in week] == sorted(d.day for d in week)


# -- streak ----------------------------------------------------------------


def test_streak_counts_clean_days_back_from_today(history):
    now = datetime.now()
    for back in range(1, 4):
        history.record_break("short", "completed", 20, 1200, now - timedelta(days=back))
    assert history.streak() == 3


def test_a_skip_ends_the_streak(history):
    now = datetime.now()
    history.record_break("short", "completed", 20, 1200, now - timedelta(days=1))
    history.record_break("short", "skipped", 20, 1200, now - timedelta(days=2))
    history.record_break("short", "completed", 20, 1200, now - timedelta(days=3))
    assert history.streak() == 1


def test_an_idle_day_stops_the_streak_without_extending_it(history):
    """A week off is not discipline, but it should not read as failure either."""
    now = datetime.now()
    history.record_break("short", "completed", 20, 1200, now - timedelta(days=1))
    history.record_break("short", "completed", 20, 1200, now - timedelta(days=5))
    assert history.streak() == 1


def test_today_being_empty_does_not_zero_the_streak(history):
    """At 09:00 nothing is due yet; the run so far must survive that."""
    now = datetime.now()
    for back in (1, 2):
        history.record_break("short", "completed", 20, 1200, now - timedelta(days=back))
    assert history.streak() == 2


def test_history_survives_reopening(tmp_path):
    path = tmp_path / "reopen.sqlite3"
    first = History(path)
    first.record_break("short", "completed", 20, 1200)
    first.close()

    second = History(path)
    assert second.today().completed == 1
    second.close()


# -- how the break was enforced -------------------------------------------


def test_mode_defaults_to_overlay_and_round_trips(history):
    history.record_break("short", "completed", 20, 1200, at(10, 9))
    history.record_break("short", "completed", 20, 1200, at(10, 10), mode="popup")

    stats = history.stats_for("2026-03-10")
    assert stats.completed == 2
    assert stats.enforced == 1     # only the overlay one was unavoidable


def test_a_popup_only_day_still_reads_as_compliant(history):
    """Reminder mode is a legitimate choice, not a failure to comply."""
    for _ in range(3):
        history.record_break("short", "completed", 20, 1200, at(10, 11), mode="popup")
    stats = history.stats_for("2026-03-10")
    assert stats.compliance == 1.0
    assert stats.enforced == 0


def test_a_database_from_before_the_mode_column_still_opens(tmp_path):
    """Upgrading must not lose someone's history."""
    import sqlite3

    path = tmp_path / "old.sqlite3"
    old = sqlite3.connect(str(path))
    old.executescript("""
        CREATE TABLE breaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL,
            outcome TEXT NOT NULL, planned_sec INTEGER NOT NULL,
            screen_sec INTEGER NOT NULL);
    """)
    old.execute(
        "INSERT INTO breaks (started_at, day, kind, outcome, planned_sec, screen_sec)"
        " VALUES ('2026-03-10T10:00:00', '2026-03-10', 'short', 'completed', 20, 1200)")
    old.commit()
    old.close()

    upgraded = History(path)
    stats = upgraded.stats_for("2026-03-10")
    assert stats.completed == 1
    assert stats.enforced == 1     # rows from before the column are overlays

    upgraded.record_break("short", "completed", 20, 1200, at(10, 12), mode="popup")
    assert upgraded.stats_for("2026-03-10").enforced == 1
    upgraded.close()


def test_opening_twice_does_not_re_run_the_migration(tmp_path):
    path = tmp_path / "twice.sqlite3"
    first = History(path)
    first.record_break("short", "completed", 20, 1200, mode="popup")
    first.close()

    second = History(path)          # the ALTER has already been applied
    assert second.today().completed == 1
    second.close()

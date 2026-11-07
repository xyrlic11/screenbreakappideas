"""Test the reward lifecycle against real SQLite saves and ticker events."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import sqlite3
from uuid import uuid4

import pytest

from blink.core.garden import ACHIEVEMENTS, Progress, level_floor, level_for
from blink.core.models import CommandKind as K, Config, POPUP
from blink.storage.db import History, day_of
from conftest import Driver, only

MORNING = datetime(2026, 3, 10, 9)


@pytest.fixture
def history(tmp_path):
    save = History(tmp_path / "blink.sqlite3")
    yield save
    save.close()


def record(history, moment=MORNING, *, kind="short", **overrides):
    work, rest = (1200, 20) if kind == "short" else (7200, 300)
    values = dict(kind=kind, outcome="completed", planned_sec=rest, screen_sec=work,
                  scheduled=True, reward_screen_sec=work, interval_sec=work, mode=POPUP,
                  event_id=uuid4().hex, moment=moment)
    values.update(overrides)
    return history.record_break(**values)


@pytest.mark.parametrize("overrides", [
    {"scheduled": False}, {"outcome": "skipped"}, {"outcome": "emergency"},
    {"planned_sec": 19}, {"reward_screen_sec": 1199}, {"interval_sec": 1199},
    {"kind": "long", "planned_sec": 299},
])
def test_ineligible_breaks_keep_history_without_reward(history, overrides):
    assert record(history, **overrides) is None
    assert history.garden.progress() == Progress()
    assert history.stats_for(day_of(MORNING)).due == 1
    assert history.garden.quests(day_of(MORNING)) == (0, set())


def test_scheduled_ticker_completion_is_rewarded_exactly_once(history):
    config = Config()
    config.short_break.enforcement = POPUP
    driver = Driver(config)
    result = only(driver.run(1221, idle=2), K.END_BREAK).payload
    reward = history.record_break(**result, screen_sec=1200, moment=MORNING, mode=POPUP)
    assert (reward.xp, reward.coins, reward.badges) == (25, 5, ("first_rest",))
    assert history.record_break(**result, screen_sec=1200, moment=MORNING, mode=POPUP) is None
    assert history.stats_for(day_of(MORNING)).completed == 1


def test_repeated_manual_breaks_and_short_custom_cycles_do_not_pay(history):
    config = Config()
    config.short_break.work_sec = 60
    driver = Driver(config)
    for _ in range(3):
        driver.ticker.break_now(driver.now)
        result = only(driver.run(20, idle=2), K.END_BREAK).payload
        assert result["scheduled"] is False
        assert history.record_break(**result, screen_sec=0, moment=MORNING) is None
    result = only(driver.run(80, idle=2), K.END_BREAK).payload
    assert result["scheduled"] is True
    assert history.record_break(**result, screen_sec=60, moment=MORNING) is None
    assert history.stats_for(day_of(MORNING)).completed == 4
    assert history.garden.progress() == Progress()


def test_daily_caps_and_independent_cooldowns(history):
    assert record(history)
    assert record(history, MORNING + timedelta(minutes=19, seconds=59)) is None
    for hours in (1, 2, 3):
        assert record(history, MORNING + timedelta(hours=hours))
    assert record(history, MORNING + timedelta(hours=4)) is None
    long = record(history, MORNING + timedelta(hours=4), kind="long")
    assert (long.xp, long.coins, long.badges) == (60, 15, ("long_rest",))
    assert record(history, MORNING + timedelta(hours=6), kind="long") is None
    assert history.garden.progress() == Progress(160, 2, 35)
    assert history.stats_for(day_of(MORNING)).completed == 8


def test_daily_quests_claim_once_and_roll_at_four(history):
    before = datetime(2026, 3, 11, 3, 59)
    boundary = before + timedelta(minutes=1)
    old_day, new_day = day_of(before), day_of(boundary)
    assert old_day == "2026-03-10" and new_day == "2026-03-11"
    assert history.claim_quest("first", before) is None
    assert record(history, before - timedelta(minutes=20))
    assert record(history, before)
    assert history.garden.quests(old_day) == (2, set())
    reward = history.claim_quest("first", before)
    assert (reward.xp, reward.coins) == (30, 10)
    assert history.claim_quest("first", before) is None
    assert history.claim_quest("second", before).level == 2
    assert history.claim_quest("first", boundary) is None
    assert record(history, boundary) is None  # Cooldown survives the day boundary.
    after = boundary + timedelta(minutes=20)
    assert record(history, after)
    assert history.claim_quest("first", after)
    assert history.garden.quests(old_day) == (2, {"first", "second"})
    assert history.garden.quests(new_day) == (1, {"first"})


def test_level_curve_and_progress():
    assert [level_floor(level) for level in range(1, 6)] == [0, 100, 250, 450, 700]
    for level in range(2, 100):
        assert level_for(level_floor(level) - 1) == level - 1
        assert level_for(level_floor(level)) == level
    assert Progress(135, 2, 0).level_xp == 35
    assert Progress(135, 2, 0).next_level_xp == 150


def test_achievement_unlocks_survive_gaps_and_never_repeat(history):
    awarded = []
    for day in range(0, 34, 2):
        for hours in range(3):
            reward = record(history, MORNING + timedelta(days=day, hours=hours))
            awarded.extend(reward.badges)
    reward = record(history, MORNING + timedelta(days=35), kind="long")
    awarded.extend(reward.badges)
    assert sorted(awarded) == sorted(ACHIEVEMENTS)
    assert history.garden.achievements()["first_rest"] == MORNING.isoformat()


def test_purchases_placement_and_restart(history):
    garden = history.garden
    assert garden.inventory() == {"sapling": (3, 0)}
    assert not garden.buy("flowers")
    record(history, kind="long")
    assert not garden.buy("mushrooms")   # Enough coins, insufficient level.
    assert garden.buy("flowers")
    assert not garden.buy("flowers")
    assert garden.progress() == Progress(60, 1, 5)
    assert not garden.place("flowers", 3, 0)
    assert not garden.place("flowers", 1, 2)
    assert not garden.place("flowers", -1, 0)
    assert not garden.place("mushrooms", 1, 1)
    assert garden.place("flowers", 1, 1)
    assert garden.place("flowers", 2, 3)
    assert not garden.remove("sapling")

    reopened = History(history.path)
    try:
        assert reopened.garden.progress() == Progress(60, 1, 5)
        assert reopened.garden.inventory()["flowers"] == (2, 3)
        assert "long_rest" in reopened.garden.achievements()
        assert reopened.garden.remove("flowers")
        assert reopened.garden.inventory()["flowers"] is None
    finally:
        reopened.close()


def test_debug_history_can_record_without_production_rewards(history):
    assert record(history)
    debug = History(":memory:", rewards_enabled=False)
    try:
        assert record(debug) is None
        assert debug.stats_for(day_of(MORNING)).completed == 1
        assert debug.claim_quest("first", MORNING) is None
        assert debug.garden.progress() == Progress()
        assert history.garden.progress() == Progress(25, 1, 5)
    finally:
        debug.close()


def test_reward_failure_rolls_back_the_completion_and_can_be_retried(history, monkeypatch):
    event = uuid4().hex
    credit = history.garden._credit

    def fail_after_credit(*args):
        credit(*args)
        raise sqlite3.OperationalError("interrupted write")

    with monkeypatch.context() as patch:
        patch.setattr(history.garden, "_credit", fail_after_credit)
        with pytest.raises(sqlite3.OperationalError, match="interrupted write"):
            record(history, event_id=event)
    assert history.stats_for(day_of(MORNING)).due == 0
    assert history.garden.progress() == Progress()
    assert history.garden.achievements() == {}
    assert history.garden.quests(day_of(MORNING)) == (0, set())
    assert record(history, event_id=event)
    assert record(history, event_id=event) is None


def test_purchase_failure_rolls_back_debit(history):
    record(history, kind="long")
    history._db.execute("""
        CREATE TRIGGER reject_purchase BEFORE INSERT ON garden_inventory
        WHEN NEW.item_id = 'flowers' BEGIN SELECT RAISE(ABORT, 'interrupted purchase'); END
    """)
    with pytest.raises(sqlite3.IntegrityError, match="interrupted purchase"):
        history.garden.buy("flowers")
    assert history.garden.progress().coins == 15
    assert "flowers" not in history.garden.inventory()


def test_concurrent_connections_cannot_duplicate_completion_or_claim(history):
    event = uuid4().hex

    def write(_):
        connection = History(history.path)
        try:
            return (bool(record(connection, event_id=event)),
                    bool(connection.claim_quest("first", MORNING)))
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, range(2)))
    assert tuple(map(sum, zip(*results))) == (1, 1)
    assert history.garden.progress() == Progress(55, 1, 15)

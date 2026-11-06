"""Break activities: selection rules and the contract each one keeps.

These import Qt but never construct a widget, so they run headless.
"""

from __future__ import annotations

import pytest

from blink.ui import activities


def test_every_activity_declares_what_it_needs():
    for activity in activities.ALL:
        assert activity.key, f"{type(activity).__name__} has no key"
        assert activity.kinds, f"{activity.key} suits no break kind"
        assert set(activity.kinds) <= {"short", "long"}


def test_keys_are_unique():
    keys = [a.key for a in activities.ALL]
    assert len(keys) == len(set(keys))


def test_every_activity_is_translated():
    """The overlay asks for title and subtitle by convention, not by field."""
    import json
    from pathlib import Path

    strings = json.loads(
        (Path(__file__).resolve().parents[1] / "blink" / "locales" / "en.json")
        .read_text(encoding="utf-8"))
    for activity in activities.ALL:
        assert activity.title_key in strings, activity.title_key
        assert activity.subtitle_key in strings, activity.subtitle_key


def test_a_short_break_never_gets_an_activity_that_cannot_finish():
    """4-7-8 breathing is a 19 second cycle; cutting it off is worse than not
    offering it at all."""
    for _ in range(60):
        chosen = activities.pick("short", 20.0)
        assert "short" in chosen.kinds
        assert chosen.min_duration <= 20.0


def test_a_long_break_can_use_the_slow_ones():
    keys = {activities.pick("long", 300.0).key for _ in range(200)}
    assert "breathe" in keys
    assert "stretch" in keys


def test_the_same_activity_does_not_come_up_twice_in_a_row():
    previous = None
    for _ in range(40):
        chosen = activities.pick("short", 20.0)
        assert chosen.key != previous
        previous = chosen.key


def test_a_single_candidate_is_allowed_to_repeat():
    """With one suitable activity, refusing to repeat would mean returning
    nothing — a break with no activity is worse than a repeat."""
    for _ in range(5):
        assert activities.pick("long", 40.0) is not None


def test_lookup_by_key():
    assert activities.by_key("look_far") is not None
    assert activities.by_key("nope") is None


@pytest.mark.parametrize("kind,duration", [("short", 20.0), ("long", 300.0)])
def test_paint_is_implemented_everywhere(kind, duration):
    from blink.ui.activities.base import Activity

    for activity in activities.ALL:
        if kind in activity.kinds:
            assert type(activity).paint is not Activity.paint

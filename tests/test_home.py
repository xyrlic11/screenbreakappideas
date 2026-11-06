"""The home page greeting, and the name that feeds it.

Runs on Qt's offscreen platform, so nothing is displayed.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication          # noqa: E402

from blink import i18n                              # noqa: E402
from blink.core.models import Config                # noqa: E402
from blink.storage.db import DayStats               # noqa: E402
from blink.ui import theme                          # noqa: E402
from blink.ui.pages import home as home_page        # noqa: E402
from blink.ui.pages.home import HomePage            # noqa: E402


@pytest.fixture(scope="session")
def qt_app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def page(qt_app):
    theme.load_fonts()
    i18n.load("en")
    return HomePage(Config())


class _Clock:
    """Stands in for the datetime module so the hour can be pinned."""

    def __init__(self, hour):
        self._hour = hour

    def now(self):
        return datetime(2026, 3, 10, self._hour, 30)


def at_hour(monkeypatch, hour):
    monkeypatch.setattr(home_page, "datetime", _Clock(hour))


# -- time of day -----------------------------------------------------------


@pytest.mark.parametrize("hour,expected", [
    (2, "greet.night"),      # still up at 2am, which this app has opinions about
    (7, "greet.morning"),
    (11, "greet.morning"),
    (13, "greet.afternoon"),
    (17, "greet.evening"),
    (23, "greet.evening"),
])
def test_the_greeting_matches_the_hour(monkeypatch, page, hour, expected):
    at_hour(monkeypatch, hour)
    page.refresh_greeting()
    assert page.heading.text() == i18n.t(expected)


def test_every_hour_of_the_day_gets_a_greeting(monkeypatch, page):
    """No gap between the buckets, at any hour."""
    for hour in range(24):
        at_hour(monkeypatch, hour)
        page.refresh_greeting()
        assert page.heading.text().strip()


# -- the name --------------------------------------------------------------


def test_a_name_is_used_when_one_is_given(monkeypatch, qt_app):
    i18n.load("en")
    config = Config()
    config.display_name = "Ton"
    page = HomePage(config)

    at_hour(monkeypatch, 9)
    page.refresh_greeting()
    assert "Ton" in page.heading.text()
    assert i18n.t("greet.morning") in page.heading.text()


def test_no_name_means_no_stray_punctuation(monkeypatch, page):
    at_hour(monkeypatch, 9)
    page.refresh_greeting()
    assert page.heading.text() == i18n.t("greet.morning")


def test_a_name_of_only_spaces_is_treated_as_unset(monkeypatch, qt_app):
    i18n.load("en")
    config = Config()
    config.display_name = "   "
    page = HomePage(config)

    at_hour(monkeypatch, 9)
    page.refresh_greeting()
    assert page.heading.text() == i18n.t("greet.morning")


# -- how today is going ----------------------------------------------------


def test_the_subline_says_nothing_is_due_yet(page):
    page.update_stats(DayStats(day="2026-03-10"))
    assert page.greeting_sub.text() == i18n.t("home.sub_none")


def test_the_subline_praises_a_clean_day(page):
    page.update_stats(DayStats(day="2026-03-10", completed=6))
    assert page.greeting_sub.text() == i18n.t("home.sub_clean")


def test_the_subline_counts_what_was_missed(page):
    page.update_stats(DayStats(day="2026-03-10", completed=4, skipped=2, emergency=1))
    assert page.greeting_sub.text() == i18n.t("home.sub_missed", count=3)


def test_the_greeting_follows_a_language_change(monkeypatch, qt_app):
    config = Config()
    page = HomePage(config)
    at_hour(monkeypatch, 9)

    i18n.load("th")
    page.retranslate()
    thai = page.heading.text()

    i18n.load("en")
    page.retranslate()
    assert page.heading.text() != thai
    assert page.heading.text() == i18n.t("greet.morning")


# -- where the name is set -------------------------------------------------


def test_settings_offers_a_place_to_put_the_name(qt_app):
    from blink.ui.pages.settings import SettingsPage
    from blink.ui.widgets import TextField

    i18n.load("en")
    config = Config()
    page = SettingsPage(config, lambda: None)

    fields = [r.control for r in page._rows if isinstance(r.control, TextField)]
    assert len(fields) == 1

    fields[0].line.setText("Ton")
    fields[0]._changed("Ton")
    fields[0]._settle.timeout.emit()          # skip the save-settling delay
    assert config.display_name == "Ton"


# -- the floating readout --------------------------------------------------


def hud_for(corner="top_right", enabled=True):
    from blink.ui.hud import MiniHud
    config = Config()
    config.hud.corner, config.hud.enabled = corner, enabled
    return MiniHud(config), config


@pytest.mark.parametrize("corner", ["top_left", "top_right",
                                    "bottom_left", "bottom_right"])
def test_the_hud_lands_in_the_corner_it_was_told_to(qt_app, corner):
    from PySide6.QtGui import QGuiApplication

    hud, _ = hud_for(corner)
    hud.reposition()
    area = QGuiApplication.primaryScreen().availableGeometry()   # not the taskbar
    pos = hud.pos()

    if corner.endswith("left"):
        assert pos.x() < area.center().x()
    else:
        assert pos.x() + hud.width() > area.center().x()
    if corner.startswith("top"):
        assert pos.y() < area.center().y()
    else:
        assert pos.y() + hud.height() > area.center().y()
    assert area.contains(pos)


def test_the_hud_stays_hidden_when_switched_off(qt_app):
    hud, _ = hud_for(enabled=False)
    hud.reveal()
    assert not hud.isVisible()


def test_the_hud_reads_the_countdown(qt_app):
    i18n.load("en")
    hud, _ = hud_for()
    hud.update_status({"state": "active", "phase": "counting",
                       "screen_time_sec": 900.0, "next_break_in_sec": 300.0,
                       "next_long_break_in_sec": None}, 1200)
    assert hud._label == "5:00"
    assert 0.7 < hud._fraction < 0.8


def test_the_hud_says_when_you_are_away_rather_than_counting(qt_app):
    i18n.load("en")
    hud, _ = hud_for()
    hud.update_status({"state": "idle", "phase": "counting",
                       "screen_time_sec": 0.0, "next_break_in_sec": 1200.0,
                       "next_long_break_in_sec": None}, 1200)
    assert hud._caption == i18n.t("home.away_short")
    assert hud._fraction == 0.0


def test_the_hud_shows_the_wall_clock(qt_app, monkeypatch):
    """A minimised window should still be able to tell you the time."""
    import time as time_module

    from blink.ui import hud as hud_module

    hud, _ = hud_for()
    monkeypatch.setattr(hud_module.time, "strftime",
                        lambda fmt: "09:41" if fmt == "%H:%M" else
                        time_module.strftime(fmt))
    hud.update_status({"state": "active", "phase": "counting",
                       "screen_time_sec": 900.0, "next_break_in_sec": 300.0,
                       "next_long_break_in_sec": None}, 1200)

    shot = hud.grab().toImage()
    # The clock lives in its own column past the divider; that area must not
    # be empty background.
    from blink.ui.hud import _CLOCK_W, _W
    bg = shot.pixelColor(2, 2)
    column = [shot.pixelColor(x, y)
              for x in range(_W - _CLOCK_W + 6, _W - 6, 2)
              for y in range(16, hud.height() - 16, 2)]
    assert any(c != bg for c in column), "nothing was drawn in the clock column"

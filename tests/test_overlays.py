"""Overlay lifecycle, and what happens when monitors come and go.

These build real widgets, so they run on Qt's offscreen platform: nothing
is ever displayed. Everything here is about the manager's bookkeeping —
whether the right number of overlays exist, which one owns the buttons,
and that a screen Qt is about to delete is dropped before anyone touches
it again.
"""

from __future__ import annotations

import os

import pytest

# Must be set before the first QApplication exists, or a real window appears.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication          # noqa: E402
from PySide6.QtWidgets import QApplication         # noqa: E402

from blink.core.models import Config               # noqa: E402
from blink.ui import activities, overlay_manager   # noqa: E402
from blink.ui.overlay_manager import OverlayManager  # noqa: E402


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def manager(qt_app):
    m = OverlayManager(Config())
    yield m
    m.finish()


def start(manager, kind="short", duration=20.0):
    return manager.begin(kind, duration, activities.by_key("look_far"))


# -- the ordinary case -----------------------------------------------------


def test_one_overlay_per_screen(manager):
    start(manager)
    assert len(manager._overlays) == len(QGuiApplication.screens())
    assert manager.active


def test_exactly_one_overlay_owns_the_buttons(manager):
    """Buttons on every monitor make a break screen look like a dialog."""
    start(manager)
    interactive = [o for o in manager._overlays if o.skip_button.isVisible()]
    assert len(interactive) == 1


def test_beginning_twice_does_not_stack_overlays(manager):
    start(manager)
    count = len(manager._overlays)
    assert start(manager) == ""          # refused
    assert len(manager._overlays) == count


def test_finish_tears_everything_down(manager):
    start(manager)
    manager.finish()
    assert manager._overlays == []
    assert not manager.active


# -- monitors appearing and vanishing mid-break ----------------------------


def test_a_screen_change_mid_break_rebuilds_the_set(manager):
    start(manager)
    before = list(manager._overlays)

    manager._screens_changed(None)       # a monitor appeared

    assert manager._overlays != before   # genuinely rebuilt
    assert len(manager._overlays) == len(QGuiApplication.screens())
    assert manager.active


def test_the_removed_screen_is_dropped_before_qt_deletes_it(manager):
    """Qt frees the QScreen right after announcing it, so nothing may keep it."""
    start(manager)
    doomed = QGuiApplication.screens()[0]

    manager._screens_changed(doomed)

    assert all(o._screen is not doomed for o in manager._overlays)


def test_a_rebuild_keeps_the_same_activity_and_countdown(manager):
    """The break must not visibly restart because a cable moved."""
    start(manager, duration=300.0)
    manager.set_remaining(212.0)
    original = manager._overlays[0]
    activity, started_at = original._activity, original._started_at

    manager._screens_changed(None)

    for overlay in manager._overlays:
        assert overlay._activity is activity
        assert overlay._remaining == 212.0
        assert overlay._started_at == started_at   # animation does not jump


def test_a_screen_change_outside_a_break_does_nothing(manager):
    manager._screens_changed(None)
    assert manager._overlays == []
    assert not manager.active


# -- which screen gets the buttons ----------------------------------------


class _FakeScreens:
    """Stands in for QGuiApplication so several monitors can be simulated.

    Only identity matters to _button_screen, so plain objects are enough.
    """

    def __init__(self, screens, under_pointer, primary):
        self._screens, self._under, self._primary = screens, under_pointer, primary

    def screens(self):
        return self._screens

    def screenAt(self, _pos):
        return self._under

    def primaryScreen(self):
        return self._primary

    def instance(self):
        return None


def with_screens(monkeypatch, screens, under_pointer, primary):
    monkeypatch.setattr(overlay_manager, "QGuiApplication",
                        _FakeScreens(screens, under_pointer, primary))


def test_the_buttons_follow_the_mouse(monkeypatch, manager):
    left, right = object(), object()
    with_screens(monkeypatch, [left, right], under_pointer=right, primary=left)
    assert manager._button_screen() is right


def test_a_pointer_between_monitors_falls_back_to_primary(monkeypatch, manager):
    """screenAt returns None in the gap; every screen used to get buttons."""
    left, right = object(), object()
    with_screens(monkeypatch, [left, right], under_pointer=None, primary=left)
    assert manager._button_screen() is left


def test_the_buttons_never_land_on_the_screen_being_removed(monkeypatch, manager):
    left, right = object(), object()
    with_screens(monkeypatch, [left, right], under_pointer=right, primary=right)
    assert manager._button_screen(skip=right) is left


def test_removing_the_last_screen_is_survivable(monkeypatch, manager):
    only = object()
    with_screens(monkeypatch, [only], under_pointer=only, primary=only)
    assert manager._button_screen(skip=only) is None


# -- the toast --------------------------------------------------------------


def pump(app, ms):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_every_toast_appears_not_just_the_first(qt_app):
    """The entrance and the exit must not share one animation.

    They did, and the exit connected finished->hide from inside its own
    handler, so from the second toast onwards it hid itself the instant it
    finished fading in. The first warning of the session worked and every
    one after it flashed for a third of a second.
    """
    from blink import i18n
    from blink.ui import theme
    from blink.ui.toast import Toast

    theme.load_fonts()
    i18n.load("en")
    toast = Toast()

    for attempt in range(1, 5):
        toast.show_for(120)
        pump(qt_app, 450)
        assert toast.isVisible(), f"toast {attempt} vanished on arrival"

        toast._fade_out()
        pump(qt_app, 400)
        assert not toast.isVisible(), f"toast {attempt} would not leave"
    toast.deleteLater()


# -- repainting -------------------------------------------------------------


def test_partial_repaint_draws_the_same_frame_as_a_full_one(qt_app):
    """Only the activity is redrawn per frame; the result must not differ.

    Repainting the whole screen thirty times a second cost a seventh of a
    core for the length of a break — on battery, while the user is meant to
    be away. Narrowing it is only safe if the output is identical, so this
    compares the two pixel for pixel.
    """
    from blink import i18n
    from blink.core.models import Config
    from blink.ui import activities, theme
    from blink.ui.overlay import BreakOverlay
    from PySide6.QtGui import QGuiApplication

    theme.load_fonts()
    i18n.load("th")

    overlay = BreakOverlay(QGuiApplication.primaryScreen(), Config())
    # look_far draws from `remaining` alone, so a pinned countdown makes the
    # frame deterministic and the two grabs directly comparable.
    overlay.begin("short", 20.0, activities.by_key("look_far"))
    pump(qt_app, 150)
    for _ in range(12):
        overlay.set_remaining(13.0)
        pump(qt_app, 40)
    partial = overlay.grab().toImage()

    overlay.update()                     # one full-window repaint
    pump(qt_app, 150)
    full = overlay.grab().toImage()
    overlay.finish()

    assert partial.size() == full.size()
    differing = sum(1 for y in range(partial.height())
                    for x in range(partial.width())
                    if partial.pixel(x, y) != full.pixel(x, y))
    assert differing == 0, f"{differing} pixels left stale by partial repainting"


def test_the_animation_timer_only_dirties_the_activity(qt_app):
    """Guards the intent, not just the output: a full update would pass the
    pixel test above while quietly costing what it used to."""
    from blink.core.models import Config
    from blink.ui import activities
    from blink.ui.overlay import BreakOverlay
    from PySide6.QtGui import QGuiApplication

    overlay = BreakOverlay(QGuiApplication.primaryScreen(), Config())
    overlay.begin("short", 20.0, activities.by_key("look_far"))

    asked = []
    overlay.update = lambda *a: asked.append(a)   # record what gets invalidated
    overlay._animate()
    overlay.finish()

    assert asked and asked[0], "the frame timer asked for a full repaint"
    assert asked[0][0] == overlay._activity_rect.toAlignedRect()

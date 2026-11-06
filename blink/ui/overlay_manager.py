"""One overlay per screen, all showing the same activity.

A single monitor is just a list of length one. Writing it this way costs
nothing today and means the day a second monitor gets plugged in, the
break screen already covers it instead of leaving somewhere to look.

Monitors that appear or vanish *during* a break are handled too. Qt deletes
a QScreen right after it announces the removal, so an overlay still holding
that screen is a crash waiting to happen; the whole set is rebuilt instead,
carrying the same activity and countdown across so the break is not
visibly interrupted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QScreen

from ..core.models import Config
from .activities import Activity
from .overlay import BreakOverlay


@dataclass
class _Showing:
    """Everything needed to put the current break back on screen."""

    kind: str
    duration: float
    activity: Activity
    remaining: float
    started_at: float


class OverlayManager(QObject):
    skipped = Signal()
    emergency = Signal()

    def __init__(self, config: Config, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.cfg = config
        self._overlays: list[BreakOverlay] = []
        self._showing: _Showing | None = None

        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._screens_changed)
            app.screenRemoved.connect(self._screens_changed)

    @property
    def active(self) -> bool:
        return self._showing is not None

    # -- driven by the policy ---------------------------------------------

    def begin(self, kind: str, duration_sec: float, activity: Activity) -> str:
        """Show the break on every screen. Returns the activity shown."""
        if self.active:
            return ""
        self._showing = _Showing(
            kind=kind,
            duration=max(1.0, duration_sec),
            activity=activity,
            remaining=duration_sec,
            started_at=time.monotonic(),
        )
        self._present()
        return activity.key

    def set_remaining(self, seconds: float) -> None:
        if self._showing is not None:
            self._showing.remaining = seconds
        for overlay in self._overlays:
            overlay.set_remaining(seconds)

    def finish(self) -> None:
        self._showing = None
        self._discard()

    # -- screens -----------------------------------------------------------

    def _present(self, skip: QScreen | None = None) -> None:
        """Put the current break on every screen, replacing what is up."""
        show = self._showing
        if show is None:
            return
        self._discard()

        buttons_on = self._button_screen(skip)
        for screen in QGuiApplication.screens():
            if screen is skip:
                continue
            overlay = BreakOverlay(screen, self.cfg)
            overlay.skipped.connect(self.skipped.emit)
            overlay.emergency.connect(self.emergency.emit)
            # started_at is carried over so a rebuild mid-break does not
            # restart the animation from frame zero.
            overlay.begin(show.kind, show.duration, show.activity,
                          interactive=screen is buttons_on,
                          started_at=show.started_at)
            overlay.set_remaining(show.remaining)
            self._overlays.append(overlay)

    def _button_screen(self, skip: QScreen | None = None) -> QScreen | None:
        """Exactly one set of buttons: where the hand already is.

        Falling back to the primary screen matters — without it a pointer
        between two monitors put a skip button on every one of them, which
        makes a break screen look like a dialog.
        """
        under_pointer = QGuiApplication.screenAt(QCursor.pos())
        if under_pointer is not None and under_pointer is not skip:
            return under_pointer
        primary = QGuiApplication.primaryScreen()
        if primary is not None and primary is not skip:
            return primary
        remaining = [s for s in QGuiApplication.screens() if s is not skip]
        return remaining[0] if remaining else None

    def _screens_changed(self, screen: QScreen | None = None) -> None:
        if not self.active:
            return
        # Qt is about to delete the screen it just told us about, so drop
        # every overlay before any of them can touch it again.
        self._present(skip=screen)

    def _discard(self) -> None:
        for overlay in self._overlays:
            overlay.finish()
            overlay.deleteLater()
        self._overlays = []

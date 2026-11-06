"""The break screen.

Paints the frame — title, subtitle, clock, progress, the two ways out —
and hands the middle of the screen to an activity. It stays dark in both
themes on purpose: a bright screen is the opposite of an eye break.
"""

from __future__ import annotations

import time

from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, QRectF, Qt,
                            QTimer, Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QScreen
from PySide6.QtWidgets import QWidget

from .. import i18n
from ..core.models import Config
from . import theme
from .activities import Activity, BreakContext
from .widgets import FlatButton, HoldButton

_FRAME_MS = 33          # ~30fps; the activities animate, the policy still ticks at 1Hz


class BreakOverlay(QWidget):
    skipped = Signal()
    emergency = Signal()

    def __init__(self, screen: QScreen, config: Config) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.cfg = config
        self._screen = screen
        self._activity: Activity | None = None
        self._remaining = 0.0
        self._duration = 1.0
        self._started_at = 0.0
        self._kind = "short"
        self._interactive = True

        self.setWindowTitle(i18n.t("app.name"))
        self.setCursor(Qt.CursorShape.BlankCursor)

        self.skip_button = HoldButton(
            i18n.t("break.skip"),
            i18n.t("break.skip_hint", seconds=config.skip.hold_sec),
            config.skip.hold_sec,
            QColor(theme.OVERLAY_FAINT),
            self,
        )
        self.skip_button.activated.connect(self.skipped.emit)

        self.emergency_button = FlatButton(
            i18n.t("break.emergency"), QColor(theme.OVERLAY_FAINT), parent=self)
        self.emergency_button.clicked.connect(self.emergency.emit)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(500)          # never appear out of nowhere
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Animation frames are independent of the one-second policy tick.
        self._layout()
        # Repainting 1920x1080 thirty times a second costs a sixth of a
        # core, sustained, for a whole five minute break — on battery,
        # while the user is meant to be away from the machine. Only the
        # activity animates, so only the activity is redrawn per frame.
        self._frames = QTimer(self)
        self._frames.setInterval(_FRAME_MS)
        self._frames.timeout.connect(self._animate)

    # -- lifecycle ---------------------------------------------------------

    def begin(self, kind: str, duration_sec: float, activity: Activity,
              interactive: bool = True, started_at: float | None = None) -> None:
        self._kind = kind
        self._duration = max(1.0, duration_sec)
        self._remaining = duration_sec
        self._activity = activity
        # Passed in when a monitor change forces a rebuild mid-break, so the
        # activity keeps animating from where it was rather than restarting.
        self._started_at = time.monotonic() if started_at is None else started_at
        self._interactive = interactive

        # Only the screen the mouse is on gets buttons; duplicating them on
        # every monitor makes the break look like a dialog.
        self.skip_button.setVisible(interactive)
        self.emergency_button.setVisible(interactive)

        self.setScreen(self._screen)
        self.setGeometry(self._screen.geometry())   # geometry(), not
        self.setWindowOpacity(0.0)                  # availableGeometry(): the
        self.showFullScreen()                       # taskbar gets covered too
        self.raise_()
        if interactive:
            self.activateWindow()

        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._frames.start()

    def _animate(self) -> None:
        self.update(self._activity_rect.toAlignedRect())

    def set_remaining(self, seconds: float) -> None:
        self._remaining = max(0.0, seconds)
        # Once a second, and only the two things that moved with it.
        self.update(self._clock_rect.toAlignedRect())
        self.update(self._progress_rect.toAlignedRect())

    def finish(self) -> None:
        self._frames.stop()
        self._fade.stop()
        self.hide()

    # -- input -------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        # Escape must not work. The only ways out are the skip button, which
        # costs five seconds, and the emergency button, which gets recorded.
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def _layout(self) -> None:
        """Where each piece lives, so a repaint can skip what did not move."""
        w, h = self.width(), self.height()
        margin = max(32, h // 22)
        side = min(w * 0.5, h * 0.42)

        self._activity_rect = QRectF((w - side) / 2, (h - side) / 2, side, side)
        self._clock_rect = QRectF(w - margin - 320, margin, 320, 60)
        self._title_rect = QRectF(0, h * 0.16, w, h * 0.09)
        self._subtitle_rect = QRectF(w * 0.2, h * 0.76, w * 0.6, h * 0.1)
        self._progress_rect = QRectF(0, h - 3, w, 3)

    def resizeEvent(self, event) -> None:
        self._layout()
        margin = max(32, self.height() // 22)
        height, width = 48, max(280, self.width() // 5)
        self.emergency_button.setGeometry(
            margin, self.height() - margin - height, width, height)
        self.skip_button.setGeometry(
            self.width() - margin - width, self.height() - margin - height,
            width, height)
        super().resizeEvent(event)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event) -> None:
        dirty = QRectF(event.rect())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Clearing just the dirty band is what erases the previous frame.
        p.fillRect(event.rect(), theme.OVERLAY_BG)

        ctx = BreakContext(
            remaining=self._remaining,
            duration=self._duration,
            elapsed=time.monotonic() - self._started_at,
            kind=self._kind,
        )

        if dirty.intersects(self._clock_rect):
            self._paint_clock(p)
        if dirty.intersects(self._title_rect):
            self._paint_title(p)
        if self._activity is not None:
            if dirty.intersects(self._activity_rect):
                self._activity.paint(p, self._activity_rect, ctx)
            if dirty.intersects(self._subtitle_rect):
                self._paint_subtitle(p)
        if dirty.intersects(self._progress_rect):
            self._paint_progress(p, ctx)
        p.end()

    def _paint_clock(self, p: QPainter) -> None:
        """A real clock, because we just covered the one in the taskbar."""
        p.setPen(QColor(theme.OVERLAY_FAINT))
        p.setFont(theme.font(max(16, self.height() // 40)))
        p.drawText(self._clock_rect,
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                   time.strftime("%H:%M"))

    def _paint_title(self, p: QPainter) -> None:
        if self._activity is None:
            return
        p.setPen(QColor(theme.OVERLAY_TEXT))
        p.setFont(theme.font(max(24, self.height() // 26), QFont.Weight.Light))
        p.drawText(self._title_rect, Qt.AlignmentFlag.AlignCenter,
                   i18n.t(self._activity.title_key))

    def _paint_subtitle(self, p: QPainter) -> None:
        assert self._activity is not None
        p.setPen(QColor(theme.OVERLAY_MUTED))
        p.setFont(theme.font(max(13, self.height() // 62)))
        p.drawText(self._subtitle_rect,
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                   | Qt.TextFlag.TextWordWrap,
                   i18n.t(self._activity.subtitle_key))

    def _paint_progress(self, p: QPainter, ctx: BreakContext) -> None:
        """A hairline along the very bottom. Glanceable, never in the way."""
        done = 1.0 - ctx.fraction_left
        rect = self._progress_rect
        p.fillRect(rect, theme.p().alpha(theme.OVERLAY_FAINT, 90))
        p.fillRect(QRectF(rect.left(), rect.top(), rect.width() * done,
                          rect.height()),
                   theme.p().alpha(theme.p().accent, 200))

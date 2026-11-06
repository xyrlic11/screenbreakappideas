"""The gentle way to take a break: a corner reminder instead of a wall.

Same countdown, same activity, none of the enforcement. It never takes
focus and never covers anything, so you can carry on working straight
through it — which is exactly the trade the user chose when they picked
this mode. Dismissing it early is recorded as a skip, same as the
fullscreen overlay's skip button.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRectF,
                            Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import i18n
from ..core.models import Config
from . import icons, theme
from .activities import Activity

_WIDTH, _HEIGHT = 360, 128
_RING = 62
_FRAME_MS = 100      # the ring only needs to look smooth, not animate


class BreakPopup(QWidget):
    dismissed = Signal()

    def __init__(self, config: Config) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        # Never steal focus: the entire point of this mode is that you can
        # keep typing.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_WIDTH, _HEIGHT)
        self.cfg = config

        self._activity: Activity | None = None
        self._remaining = 0.0
        self._duration = 1.0
        self._kind = "short"
        self._close_hot = False
        self.setMouseTracking(True)

        self._slide = QPropertyAnimation(self, b"pos", self)
        self._slide.setDuration(300)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._frames = QTimer(self)
        self._frames.setInterval(_FRAME_MS)
        self._frames.timeout.connect(self.update)

    # -- the presenter interface, shared with OverlayManager ---------------

    def begin(self, kind: str, duration_sec: float, activity: Activity) -> str:
        self._kind = kind
        self._duration = max(1.0, duration_sec)
        self._remaining = duration_sec
        self._activity = activity

        area = QGuiApplication.primaryScreen().availableGeometry()
        end = QPoint(area.right() - _WIDTH - 24, area.bottom() - _HEIGHT - 24)
        self.move(end + QPoint(0, 36))
        self.show()
        self.raise_()

        self._slide.stop()
        self._slide.setStartValue(end + QPoint(0, 36))
        self._slide.setEndValue(end)
        self._slide.start()
        self._frames.start()
        return activity.key

    def set_remaining(self, seconds: float) -> None:
        self._remaining = max(0.0, seconds)
        self.update()

    def finish(self) -> None:
        self._frames.stop()
        self.hide()

    # -- input -------------------------------------------------------------

    def _close_rect(self) -> QRectF:
        return QRectF(self.width() - 38, 12, 26, 26)

    def mouseMoveEvent(self, event) -> None:
        hot = self._close_rect().contains(event.position())
        if hot != self._close_hot:
            self._close_hot = hot
            self.update()

    def leaveEvent(self, event) -> None:
        self._close_hot = False
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self.dismissed.emit()

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        base = QColor(palette.bg)
        base.setAlpha(246)
        p.setPen(QPen(palette.stroke, 1))
        p.setBrush(base)
        p.drawRoundedRect(rect, 10, 10)

        self._paint_ring(p, palette)
        self._paint_text(p, palette, rect)
        self._paint_close(p, palette)
        p.end()

    def _paint_ring(self, p: QPainter, palette) -> None:
        ring = QRectF(22, (_HEIGHT - _RING) / 2, _RING, _RING)
        left = max(0.0, min(1.0, self._remaining / self._duration))

        track = QColor(palette.text_3)
        track.setAlpha(50)
        p.setPen(QPen(track, 5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(ring)

        p.setPen(QPen(palette.accent, 5, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        # Qt angles are sixteenths of a degree, clockwise from 12 o'clock.
        p.drawArc(ring, 90 * 16, int(-360 * 16 * left))

        p.setPen(palette.text)
        p.setFont(theme.font(20, QFont.Weight.Light))
        p.drawText(ring, Qt.AlignmentFlag.AlignCenter,
                   str(int(math.ceil(self._remaining))))

    def _paint_text(self, p: QPainter, palette, rect: QRectF) -> None:
        if self._activity is None:
            return
        left = 22 + _RING + 18

        p.setPen(palette.text)
        p.setFont(theme.semibold(theme.BODY_LG))
        p.drawText(QRectF(left, 30, rect.width() - left - 44, 26),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   i18n.t(self._activity.title_key))

        p.setPen(palette.text_3)
        p.setFont(theme.font(theme.CAPTION))
        p.drawText(QRectF(left, 58, rect.width() - left - 30, 42),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
                   | Qt.TextFlag.TextWordWrap,
                   i18n.t("popup.hint"))

    def _paint_close(self, p: QPainter, palette) -> None:
        box = self._close_rect()
        if self._close_hot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(palette.layer_alt)
            p.drawRoundedRect(box, 4, 4)
        icons.draw(p, icons.CLOSE, box,
                   palette.text if self._close_hot else palette.text_3, 12)

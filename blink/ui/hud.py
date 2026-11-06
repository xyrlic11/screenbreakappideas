"""A small always-on-top readout for when the window is away.

Closing the window drops Blink into the tray, where the only status is a
tooltip you have to go looking for. This keeps the countdown visible in a
corner instead, and clicking it brings the window back.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import i18n
from ..core.models import Config
from . import theme

_W, _H = 236, 54
_MARGIN = 18
_RING = 32
_CLOCK_W = 58   # the right-hand column, past the divider

CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")


class MiniHud(QWidget):
    clicked = Signal()

    def __init__(self, config: Config) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        # Never take focus: it sits on top of whatever you are working in.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_W, _H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cfg = config

        self._label = "--"
        self._caption = ""
        self._fraction = 0.0
        self._tone: QColor | None = None

    # -- placement ---------------------------------------------------------

    def reposition(self) -> None:
        area = QGuiApplication.primaryScreen().availableGeometry()   # respects the taskbar
        corner = self.cfg.hud.corner
        x = area.left() + _MARGIN if corner.endswith("left") else area.right() - _W - _MARGIN
        y = area.top() + _MARGIN if corner.startswith("top") else area.bottom() - _H - _MARGIN
        self.move(QPoint(x, y))

    def reveal(self) -> None:
        if not self.cfg.hud.enabled or self.isVisible():
            return
        self.reposition()
        self.show()
        self.raise_()

    # -- driven once a second ---------------------------------------------

    def update_status(self, payload: dict, work_sec: int) -> None:
        state, phase = payload["state"], payload["phase"]
        remaining = payload["next_break_in_sec"]
        palette = theme.p()

        if phase in ("break", "long_break", "locked_break"):
            self._label, self._caption = "···", i18n.t("tray.breaking")
            self._fraction, self._tone = 1.0, palette.accent
        elif state == "paused":
            self._label, self._caption = "||", i18n.t("home.paused_short")
            self._fraction, self._tone = 0.0, palette.text_3
        elif state in ("idle", "locked"):
            self._label, self._caption = "--", i18n.t("home.away_short")
            self._fraction, self._tone = 0.0, palette.text_3
        else:
            minutes, seconds = int(remaining) // 60, int(remaining) % 60
            self._label = f"{minutes}:{seconds:02d}"
            self._caption = i18n.t("home.until_break")
            self._fraction = 1.0 - min(1.0, remaining / max(1, work_sec))
            self._tone = palette.warn if remaining <= 120 else palette.accent
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self.clicked.emit()

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        base = QColor(palette.bg)
        base.setAlpha(242)
        p.setPen(QPen(palette.stroke, 1))
        p.setBrush(base)
        p.drawRoundedRect(rect, 9, 9)

        tone = self._tone or palette.accent
        ring = QRectF(12, (_H - _RING) / 2, _RING, _RING)
        track = QColor(palette.text_3)
        track.setAlpha(60)
        p.setPen(QPen(track, 3.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(ring)
        if self._fraction > 0:
            p.setPen(QPen(tone, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(ring, 90 * 16, int(-360 * 16 * self._fraction))

        left = 12 + _RING + 12
        p.setPen(palette.text)
        p.setFont(theme.font(16, QFont.Weight.DemiBold))
        p.drawText(QRectF(left, 9, _W - left - _CLOCK_W - 10, 20),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._label)

        p.setPen(palette.text_3)
        p.setFont(theme.font(theme.CAPTION))
        p.drawText(QRectF(left, 28, _W - left - _CLOCK_W - 10, 18),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._caption)

        self._paint_clock(p, palette, rect)
        p.end()

    def _paint_clock(self, p: QPainter, palette, rect: QRectF) -> None:
        """The wall clock, so a minimised window still tells the time."""
        divider_x = _W - _CLOCK_W
        p.setPen(QPen(palette.stroke, 1))
        p.drawLine(int(divider_x), 13, int(divider_x), _H - 13)

        p.setPen(palette.text_2)
        p.setFont(theme.font(17, QFont.Weight.DemiBold))
        p.drawText(QRectF(divider_x, 0, _CLOCK_W, _H),
                   Qt.AlignmentFlag.AlignCenter, time.strftime("%H:%M"))

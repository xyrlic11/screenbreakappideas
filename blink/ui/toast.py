"""The gentlest rung of the ladder: a corner card that never steals focus.

Slides up from the tray corner the way Windows notifications do, sits for
a few seconds, fades out.
"""

from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup, QPoint,
                            QPropertyAnimation, QRectF, Qt, QTimer)
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import i18n
from . import icons, theme

_WIDTH, _HEIGHT = 340, 96
_VISIBLE_MS = 7000


class Toast(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        # Never take focus: this shows up while you are typing.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_WIDTH, _HEIGHT)
        self._body = ""

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(320)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._slide = QPropertyAnimation(self, b"pos", self)
        self._slide.setDuration(320)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._entrance = QParallelAnimationGroup(self)
        self._entrance.addAnimation(self._fade)
        self._entrance.addAnimation(self._slide)

        # A separate animation for leaving. Reusing the entrance fade meant
        # connecting finished->hide inside the handler, which both stacked up
        # a new connection every time and, because the entrance shares that
        # animation, hid every later toast the moment it finished appearing.
        self._exit = QPropertyAnimation(self, b"windowOpacity", self)
        self._exit.setDuration(280)
        self._exit.setEasingCurve(QEasingCurve.Type.InCubic)
        self._exit.finished.connect(self.hide)

    def show_for(self, seconds_left: int) -> None:
        self._body = (i18n.t("toast.body_min", minutes=round(seconds_left / 60))
                      if seconds_left >= 90
                      else i18n.t("toast.body", seconds=seconds_left))

        area = QGuiApplication.primaryScreen().availableGeometry()  # respect the taskbar
        end = QPoint(area.right() - _WIDTH - 24, area.bottom() - _HEIGHT - 24)

        self._entrance.stop()
        self._exit.stop()          # a toast can arrive while the last is leaving
        self.setWindowOpacity(0.0)
        self.move(end + QPoint(0, 28))
        self.show()
        self.raise_()

        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._slide.setStartValue(end + QPoint(0, 28))
        self._slide.setEndValue(end)
        self._entrance.start()
        self._hide_timer.start(_VISIBLE_MS)
        self.update()

    def _fade_out(self) -> None:
        self._entrance.stop()
        self._exit.setStartValue(self.windowOpacity())
        self._exit.setEndValue(0.0)
        self._exit.start()

    def mouseReleaseEvent(self, event) -> None:
        self.hide()   # dismissible, it is only a heads-up

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        base = QColor(palette.bg)
        base.setAlpha(244)
        p.setPen(QPen(palette.stroke, 1))
        p.setBrush(base)
        p.drawRoundedRect(rect, 8, 8)

        icons.draw(p, icons.EYE, QRectF(rect.left() + 18, rect.top() + 22, 26, 26),
                   palette.accent, 20)

        p.setPen(palette.text)
        p.setFont(theme.semibold(theme.BODY))
        p.drawText(rect.adjusted(56, 24, -16, 0),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                   i18n.t("toast.title"))

        p.setPen(palette.text_3)
        p.setFont(theme.font(theme.CAPTION))
        p.drawText(rect.adjusted(56, 48, -16, -18),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self._body)
        p.end()

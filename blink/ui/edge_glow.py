"""The middle rung: a breathing band around the screen edge.

Meant to be caught out of the corner of your eye without pulling it. It
is click-through, so it cannot get in the way of whatever you are
finishing in the last ten seconds.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget

from . import theme

_BAND = 8          # px
_PERIOD_MS = 40


class _EdgeWindow(QWidget):
    def __init__(self, screen: QScreen) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._screen_ref = screen
        self._phase = 0.0

    def start(self) -> None:
        self.setScreen(self._screen_ref)
        self.setGeometry(self._screen_ref.geometry())
        self.show()
        self.raise_()

    def set_phase(self, phase: float) -> None:
        self._phase = phase
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour = QColor(theme.p().accent)
        colour.setAlpha(int(55 + 95 * self._phase))
        p.setPen(QPen(colour, _BAND))
        p.setBrush(Qt.BrushStyle.NoBrush)
        half = _BAND / 2
        p.drawRect(QRectF(self.rect()).adjusted(half, half, -half, -half))
        p.end()


class EdgeGlow:
    """Owns one click-through band per screen."""

    def __init__(self) -> None:
        self._windows: list[_EdgeWindow] = []
        self._elapsed = 0.0
        self._timer = QTimer()
        self._timer.setInterval(_PERIOD_MS)
        self._timer.timeout.connect(self._breathe)

    def show(self) -> None:
        if self._windows:
            return
        self._windows = [_EdgeWindow(s) for s in QGuiApplication.screens()]
        for window in self._windows:
            window.start()
        self._elapsed = 0.0
        self._timer.start()

    def hide(self) -> None:
        self._timer.stop()
        for window in self._windows:
            window.hide()
            window.deleteLater()
        self._windows = []

    def _breathe(self) -> None:
        # A slow 2 second pulse: noticeable in peripheral vision, not a strobe.
        self._elapsed += _PERIOD_MS / 1000
        phase = abs(((self._elapsed % 2.0) / 1.0) - 1.0)
        for window in self._windows:
            window.set_phase(phase)

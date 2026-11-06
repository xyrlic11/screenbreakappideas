"""Blink along with the eyelid.

Staring at a screen cuts the blink rate by roughly half, which is the
first cause of dry eyes. Counting deliberate slow blinks is the only part
of a break that treats that directly.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from .. import theme
from .base import Activity, BreakContext

_BLINK_SEC = 3.0     # one slow close-and-open


class BlinkCount(Activity):
    key = "blink_count"
    kinds = ("short", "long")
    min_duration = 6.0

    def paint(self, p: QPainter, rect: QRectF, ctx: BreakContext) -> None:
        accent = theme.p().accent
        width = rect.width() * 0.92
        height = width * 0.42
        centre = rect.center()

        # 0 = wide open, 1 = fully closed, held shut briefly at the bottom.
        phase = (ctx.elapsed % _BLINK_SEC) / _BLINK_SEC
        closed = math.sin(min(1.0, phase * 1.6) * math.pi) ** 2

        self._paint_eye(p, centre, width, height, closed, accent)

        count = int(ctx.elapsed // _BLINK_SEC) + 1
        p.setPen(QColor(theme.OVERLAY_MUTED))
        p.setFont(theme.font(int(height * 0.42), QFont.Weight.Light))
        p.drawText(
            QRectF(rect.left(), centre.y() + height * 0.9, rect.width(), height),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            str(count),
        )

    def _paint_eye(self, p: QPainter, centre: QPointF, width: float,
                   height: float, closed: float, accent: QColor) -> None:
        open_height = height * (1.0 - closed * 0.94)
        half_w, half_h = width / 2, max(1.0, open_height / 2)

        # Two arcs meeting at the corners: an almond, not an ellipse.
        outline = QPainterPath()
        outline.moveTo(centre.x() - half_w, centre.y())
        outline.quadTo(centre.x(), centre.y() - half_h * 2,
                       centre.x() + half_w, centre.y())
        outline.quadTo(centre.x(), centre.y() + half_h * 2,
                       centre.x() - half_w, centre.y())

        p.setPen(QPen(theme.p().alpha(accent, 220), max(2.0, height * 0.05)))
        p.setBrush(theme.p().alpha(accent, 20))
        p.drawPath(outline)

        if closed < 0.55:
            iris = half_h * 0.85
            p.setClipPath(outline)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.p().alpha(accent, 150))
            p.drawEllipse(centre, iris, iris)
            p.setClipping(False)

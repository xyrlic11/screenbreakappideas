"""Follow the dot.

Staring at one spot leaves the eye muscles locked in a single position.
Tracking something across the full width of the screen makes them work in
a way that reading never does.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from .. import theme
from .base import Activity, BreakContext

_SWEEP_SEC = 5.0     # one edge to the other; slow enough to actually follow


class MovingDot(Activity):
    key = "moving_dot"
    kinds = ("short", "long")
    min_duration = 8.0

    def paint(self, p: QPainter, rect: QRectF, ctx: BreakContext) -> None:
        accent = theme.p().accent

        # Ease in and out at the turns so the eye is never asked to snap.
        phase = (ctx.elapsed % (_SWEEP_SEC * 2)) / _SWEEP_SEC
        travel = phase if phase <= 1.0 else 2.0 - phase
        eased = 0.5 - 0.5 * math.cos(travel * math.pi)

        radius = min(rect.height() / 2, 26.0)
        left = rect.left() + radius
        span = rect.width() - radius * 2
        centre = QPointF(left + span * eased, rect.center().y())

        rail = QColor(theme.OVERLAY_FAINT)
        rail.setAlpha(40)
        p.setPen(QPen(rail, 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(left, centre.y()), QPointF(left + span, centre.y()))

        glow = theme.p().alpha(accent, 45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(centre, radius * 2.1, radius * 2.1)

        p.setBrush(accent)
        p.drawEllipse(centre, radius, radius)

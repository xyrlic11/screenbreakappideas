"""Look at something 20 feet away.

The circle shrinking towards a point is the whole design: there is nothing
to read, so the screen gives you no reason to keep looking at it.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from .. import theme
from .base import Activity, BreakContext


class LookFar(Activity):
    key = "look_far"
    kinds = ("short", "long")

    def paint(self, p: QPainter, rect: QRectF, ctx: BreakContext) -> None:
        centre = rect.center()
        max_radius = min(rect.width(), rect.height()) / 2

        guide = QColor(theme.OVERLAY_FAINT)   # copy: the token is shared
        guide.setAlpha(45)
        p.setPen(QPen(guide, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(centre, max_radius, max_radius)

        accent = theme.p().accent
        radius = max(2.0, max_radius * ctx.fraction_left)

        fill = theme.p().alpha(accent, 26)
        p.setBrush(fill)
        p.setPen(QPen(theme.p().alpha(accent, 210), 2))
        p.drawEllipse(centre, radius, radius)

        p.setPen(theme.OVERLAY_TEXT)
        p.setFont(theme.font(int(max_radius * 0.62), QFont.Weight.Light))
        p.drawText(
            QRectF(centre.x() - max_radius, centre.y() - max_radius,
                   max_radius * 2, max_radius * 2),
            Qt.AlignmentFlag.AlignCenter,
            str(int(math.ceil(ctx.remaining))),
        )

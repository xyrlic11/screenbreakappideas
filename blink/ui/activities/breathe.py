"""4-7-8 breathing.

One cycle is nineteen seconds, so this only appears on long breaks — on a
twenty second eye break you would be cut off halfway through the first
hold, which is worse than not offering it.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from ... import i18n
from .. import theme
from .base import Activity, BreakContext

_IN, _HOLD, _OUT = 4.0, 7.0, 8.0
_CYCLE = _IN + _HOLD + _OUT


class Breathe(Activity):
    key = "breathe"
    kinds = ("long",)
    min_duration = _CYCLE * 2

    def paint(self, p: QPainter, rect: QRectF, ctx: BreakContext) -> None:
        phase, label_key, remaining = self._phase(ctx.elapsed)
        accent = theme.p().accent
        max_radius = min(rect.width(), rect.height()) / 2
        centre = rect.center()

        guide = QColor(theme.OVERLAY_FAINT)
        guide.setAlpha(40)
        p.setPen(QPen(guide, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(centre, max_radius, max_radius)

        radius = max_radius * (0.34 + 0.66 * phase)
        p.setPen(QPen(theme.p().alpha(accent, 200), 2))
        p.setBrush(theme.p().alpha(accent, 30))
        p.drawEllipse(centre, radius, radius)

        p.setPen(QColor(theme.OVERLAY_TEXT))
        p.setFont(theme.font(int(max_radius * 0.22)))
        p.drawText(QRectF(centre.x() - max_radius, centre.y() - max_radius * 0.55,
                          max_radius * 2, max_radius * 0.6),
                   Qt.AlignmentFlag.AlignCenter, i18n.t(label_key))

        p.setPen(QColor(theme.OVERLAY_MUTED))
        p.setFont(theme.font(int(max_radius * 0.42)))
        p.drawText(QRectF(centre.x() - max_radius, centre.y() - max_radius * 0.05,
                          max_radius * 2, max_radius * 0.7),
                   Qt.AlignmentFlag.AlignCenter, str(int(math.ceil(remaining))))

    def _phase(self, elapsed: float) -> tuple[float, str, float]:
        """Returns (how inflated 0-1, which label, seconds left in this phase)."""
        t = elapsed % _CYCLE
        if t < _IN:
            return t / _IN, "activity.breathe.in", _IN - t
        if t < _IN + _HOLD:
            return 1.0, "activity.breathe.hold", _IN + _HOLD - t
        out = t - _IN - _HOLD
        return 1.0 - out / _OUT, "activity.breathe.out", _OUT - out

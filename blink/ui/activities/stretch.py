"""Neck and shoulders.

Long breaks are about the rest of the body, not the eyes. The dial traces
the movement being asked for and the instruction changes every twenty
seconds, so there is a pace to follow instead of a wall of text.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from ... import i18n
from .. import theme
from .base import Activity, BreakContext

_STEP_SEC = 20.0
_STEPS = ("roll", "tilt", "reach", "look")


class Stretch(Activity):
    key = "stretch"
    kinds = ("long",)
    min_duration = _STEP_SEC * 2

    def paint(self, p: QPainter, rect: QRectF, ctx: BreakContext) -> None:
        step = _STEPS[int(ctx.elapsed // _STEP_SEC) % len(_STEPS)]
        within = (ctx.elapsed % _STEP_SEC) / _STEP_SEC
        accent = theme.p().accent
        radius = min(rect.width(), rect.height()) / 2 * 0.62
        centre = rect.center()

        track = QColor(theme.OVERLAY_FAINT)
        track.setAlpha(45)
        p.setPen(QPen(track, 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(centre, radius, radius)

        # A head travelling the circle at the pace of the movement.
        angle = -math.pi / 2 + within * 2 * math.pi
        marker = QPointF(centre.x() + radius * math.cos(angle),
                         centre.y() + radius * math.sin(angle))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.p().alpha(accent, 50))
        p.drawEllipse(marker, radius * 0.22, radius * 0.22)
        p.setBrush(accent)
        p.drawEllipse(marker, radius * 0.11, radius * 0.11)

        p.setPen(QColor(theme.OVERLAY_TEXT))
        p.setFont(theme.font(int(radius * 0.3)))
        p.drawText(QRectF(centre.x() - radius, centre.y() - radius * 0.35,
                          radius * 2, radius * 0.7),
                   Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                   i18n.t(f"activity.stretch.{step}"))

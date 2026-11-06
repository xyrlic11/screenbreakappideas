"""Icons from the font Windows already ships.

Segoe Fluent Icons is present on Windows 11 and Segoe MDL2 Assets on 10;
the codepoints used here exist in both. No image assets, no licence
questions, and they scale perfectly at any DPI.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QIcon, QPainter, QPen,
                           QPixmap)

# Codepoints shared by Segoe Fluent Icons and Segoe MDL2 Assets.
HOME = ""
CHART = ""
SETTINGS = ""
INFO = ""
EYE = ""
TIMER = ""
PAUSE = ""
PLAY = ""
LOCK = ""
CHECK = ""
SKIP = ""
WARNING = ""
FLAME = ""
CLOSE = ""
FULLSCREEN = ""
MESSAGE = ""

_family: str | None = None


def icon_font(size: int) -> QFont:
    global _family
    if _family is None:
        installed = set(QFontDatabase.families())
        _family = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets")
                        if f in installed), "Segoe UI Symbol")
    font = QFont(_family)
    font.setPixelSize(size)
    return font


def draw(p: QPainter, glyph: str, rect: QRectF, colour: QColor, size: int) -> None:
    p.save()
    p.setFont(icon_font(size))
    p.setPen(colour)
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, glyph)
    p.restore()


def app_icon(accent: QColor, size: int = 256) -> QIcon:
    """The Blink mark: an open ring with a pupil, drawn not shipped."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    stroke = size * 0.09
    rect = QRectF(stroke, stroke * 1.6, size - stroke * 2, size - stroke * 3.2)

    p.setPen(QPen(accent, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    # Two arcs meeting at the corners: an eye, not a circle.
    p.drawArc(rect, 0, 180 * 16)
    p.drawArc(rect, 180 * 16, 180 * 16)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(accent)
    pupil = size * 0.13
    p.drawEllipse(rect.center(), pupil, pupil)
    p.end()
    return QIcon(pixmap)

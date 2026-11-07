"""Shared furniture for the pages: headings, stat tiles, scrolling."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,
                               QWidget)

from ... import i18n
from .. import icons, theme
from ..widgets import CARD_RADIUS


class Page(QWidget):
    """A scrollable column with a title at the top."""

    def __init__(self, title_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.heading = QLabel(i18n.t(title_key))
        self.heading.setFont(theme.font(theme.TITLE, QFont.Weight.DemiBold))
        self.heading.setStyleSheet(f"color:{theme.p().text.name()};")
        self.heading.setContentsMargins(36, 26, 36, 14)
        outer.addWidget(self.heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("pageScroll")
        scroll.setStyleSheet("QScrollArea#pageScroll { background: transparent; }")
        self.scroll = scroll

        body = QWidget()
        body.setObjectName("pageBody")
        body.setStyleSheet("QWidget#pageBody { background: transparent; }")
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(36, 0, 36, 32)
        self.body.setSpacing(10)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        self._title_key = title_key
        self._sections: list[tuple[QLabel, str]] = []

    def section(self, key: str) -> QLabel:
        label = QLabel(i18n.t(key))
        label.setFont(theme.semibold(theme.BODY_LG))
        label.setStyleSheet(f"color:{theme.p().text.name()};")
        label.setContentsMargins(2, 16, 0, 2)
        self.body.addWidget(label)
        self._sections.append((label, key))
        return label

    def retranslate(self) -> None:
        """Subclasses extend this; the shared parts are handled here."""
        self.heading.setText(i18n.t(self._title_key))
        self.heading.setStyleSheet(f"color:{theme.p().text.name()};")
        for label, key in self._sections:
            label.setText(i18n.t(key))
            label.setStyleSheet(f"color:{theme.p().text.name()};")


class StatTile(QWidget):
    """One number with a caption and an icon, in a card."""

    def __init__(self, glyph: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.glyph = glyph
        self.value = "--"
        self.caption = ""
        self.tone: QColor | None = None
        self.setMinimumHeight(96)

    def set_values(self, value: str, caption: str, tone: QColor | None = None) -> None:
        self.value, self.caption, self.tone = value, caption, tone
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        p.setBrush(palette.layer)
        p.setPen(QPen(palette.stroke, 1))
        p.drawRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)

        colour = self.tone or palette.accent
        icons.draw(p, self.glyph, QRectF(rect.left() + 14, rect.top() + 14, 22, 22),
                   colour, 18)

        # "4 ชม. 30 นาที" is a lot longer than "9": shrink to fit rather
        # than let the number spill out of the card.
        value_rect = rect.adjusted(14, 30, -14, -26)
        size = theme.TITLE
        p.setFont(theme.font(size))
        while size > theme.BODY and p.fontMetrics().horizontalAdvance(self.value) > value_rect.width():
            size -= 2
            p.setFont(theme.font(size))

        p.setPen(palette.text)
        p.drawText(value_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                   self.value)

        p.setPen(palette.text_3)
        p.setFont(theme.font(theme.CAPTION))
        p.drawText(rect.adjusted(14, 0, -14, -12),
                   Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                   self.caption)
        p.end()


def tile_row(tiles: list[StatTile]) -> QWidget:
    holder = QWidget()
    holder.setStyleSheet("background:transparent;")
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    for tile in tiles:
        layout.addWidget(tile, 1)
    return holder

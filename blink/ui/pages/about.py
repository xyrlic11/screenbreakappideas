"""What this is, and what it does not do."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ... import __version__, i18n
from ...storage.config import CONFIG_PATH
from ...storage.db import DB_PATH
from .. import icons, theme
from ..widgets import Card
from .base import Page


class AboutPage(Page):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("nav.about", parent)
        self._cards: list[tuple[Card, str, str]] = []

        self.tagline = QLabel()
        self.tagline.setFont(theme.font(theme.BODY_LG))
        self.tagline.setWordWrap(True)
        self.body.addWidget(self.tagline)

        self.section("about.privacy")
        self._note("about.no_hook", icons.CHECK)
        self._note("about.no_network", icons.CHECK)
        self._note("about.no_admin", icons.CHECK)

        self.section("about.files")
        self.paths = QLabel()
        self.paths.setFont(theme.font(theme.CAPTION))
        self.paths.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.paths.setWordWrap(True)
        self.body.addWidget(self.paths)
        self.body.addStretch(1)
        self.retranslate()

    def _note(self, key: str, glyph: str) -> None:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        label = QLabel()
        label.setFont(theme.font(theme.BODY))
        label.setWordWrap(True)
        layout.addWidget(label)
        self.body.addWidget(card)
        self._cards.append((card, key, glyph))
        card.label = label

    def retranslate(self) -> None:
        super().retranslate()
        palette = theme.p()
        self.tagline.setText(i18n.t("about.tagline", version=__version__))
        self.tagline.setStyleSheet(f"color:{palette.text_2.name()};")
        for card, key, _ in self._cards:
            card.label.setText(i18n.t(key))
            card.label.setStyleSheet(f"color:{palette.text_2.name()};")
        self.paths.setText(f"{CONFIG_PATH}\n{DB_PATH}")
        self.paths.setStyleSheet(f"color:{palette.text_3.name()};")

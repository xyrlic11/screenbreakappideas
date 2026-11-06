"""Seven days of evidence.

Deliberately small: this is here to answer "am I actually taking them?",
not to be a dashboard. The heavy charting lands in a later phase.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ... import i18n
from ...storage.db import DayStats, History
from .. import icons, theme
from ..charts import WeekBars
from ..widgets import Card
from .base import Page, StatTile, tile_row

_WEEKDAY_KEYS = ("day.mon", "day.tue", "day.wed", "day.thu",
                 "day.fri", "day.sat", "day.sun")


class StatsPage(Page):
    def __init__(self, history: History, parent: QWidget | None = None) -> None:
        super().__init__("nav.stats", parent)
        self.history = history

        self.compliance = StatTile(icons.CHECK)
        self.streak = StatTile(icons.FLAME)
        self.long_breaks = StatTile(icons.TIMER)
        self.body.addWidget(tile_row([self.compliance, self.streak, self.long_breaks]))

        self.section("stats.last_week")
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 10)
        self.bars = WeekBars()
        layout.addWidget(self.bars)
        self.body.addWidget(card)

        self.legend = QLabel()
        self.legend.setFont(theme.font(theme.CAPTION))
        self.body.addWidget(self.legend)
        self.body.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        week = self.history.recent(7)
        today = week[-1] if week else DayStats(day=date.today().isoformat())
        palette = theme.p()

        self.compliance.set_values(
            f"{round(today.compliance * 100)}%", i18n.t("stats.compliance_today"),
            palette.success if today.compliance >= 0.8 else palette.warn)

        streak = self.history.streak()
        self.streak.set_values(
            i18n.t("stats.days", count=streak), i18n.t("stats.streak"),
            palette.accent if streak else palette.text_3)

        self.long_breaks.set_values(
            str(sum(d.long_breaks for d in week)), i18n.t("stats.long_breaks_week"))

        self.bars.set_days([
            (i18n.t(_WEEKDAY_KEYS[date.fromisoformat(d.day).weekday()]),
             d.completed, d.skipped + d.emergency)
            for d in week
        ])
        self.legend.setText(i18n.t("stats.legend"))
        self.legend.setStyleSheet(f"color:{palette.text_3.name()};")

    def retranslate(self) -> None:
        super().retranslate()
        self.refresh()

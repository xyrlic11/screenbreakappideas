"""Where you land: how long until the next break, and today so far."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ... import i18n
from ...storage.db import DayStats
from .. import icons, theme
from ..charts import RingGauge
from ..widgets import FlatButton
from .base import Page, StatTile, tile_row
from .garden import GardenDashboard


class HomePage(Page):
    break_now = Signal()
    pause_toggled = Signal()

    def __init__(self, config, parent: QWidget | None = None, *,
                 garden: GardenDashboard | None = None) -> None:
        super().__init__("nav.home", parent)
        self.cfg = config
        self._paused = False
        self._today = None

        self.body.addWidget(self._greeting_block())
        self.ring = RingGauge()
        if garden is None:
            self.ring.setMinimumHeight(260)
            self.body.addWidget(self.ring)
        else:
            self.heading.setContentsMargins(36, 22, 36, 8)
            self.ring.setMinimumSize(140, 62)

        actions = QWidget()
        actions.setStyleSheet("background:transparent;")
        row = QHBoxLayout(actions)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(10)
        if garden is not None:
            row.addWidget(self.ring)
        row.addStretch(1)

        self.break_button = FlatButton(i18n.t("tray.break_now"), accent=True)
        self.break_button.clicked.connect(self.break_now.emit)
        row.addWidget(self.break_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.pause_button = FlatButton(i18n.t("tray.pause_hour"))
        self.pause_button.clicked.connect(self.pause_toggled.emit)
        row.addWidget(self.pause_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        if garden is None:
            row.addStretch(1)
        self.body.addWidget(actions)
        if garden is not None:
            self.body.addWidget(garden)

        self.section("home.today")
        self.completed = StatTile(icons.CHECK)
        self.skipped = StatTile(icons.SKIP)
        self.screen_time = StatTile(icons.EYE)
        self.body.addWidget(tile_row([self.completed, self.skipped, self.screen_time]))
        self.body.addStretch(1)
        self.garden = garden

    def _greeting_block(self) -> QWidget:
        block = QWidget()
        block.setStyleSheet("background:transparent;")
        column = QVBoxLayout(block)
        column.setContentsMargins(2, 0, 0, 10)
        column.setSpacing(2)

        self.greeting_sub = QLabel()
        self.greeting_sub.setFont(theme.font(theme.BODY))
        column.addWidget(self.greeting_sub)
        return block

    def refresh_greeting(self) -> None:
        """Time of day, a name if one was given, and how today is going."""
        hour = datetime.now().hour
        if hour < 5:
            part = "greet.night"
        elif hour < 12:
            part = "greet.morning"
        elif hour < 16:
            part = "greet.afternoon"
        else:
            part = "greet.evening"

        hello = i18n.t(part)
        name = (self.cfg.display_name or "").strip()
        if name:
            hello = i18n.t("greet.named", greeting=hello, name=name)
        # The sidebar already says which page this is, so the heading is
        # spent on something worth reading instead.
        self.heading.setText(hello)

        stats = self._today
        if stats is None or stats.due == 0:
            line = i18n.t("home.sub_none")
        elif stats.skipped + stats.emergency:
            line = i18n.t("home.sub_missed",
                          count=stats.skipped + stats.emergency)
        else:
            line = i18n.t("home.sub_clean")
        self.greeting_sub.setText(line)
        self._paint_greeting()

    def _paint_greeting(self) -> None:
        self.greeting_sub.setStyleSheet(f"color:{theme.p().text_3.name()};")

    # -- driven once a second ---------------------------------------------

    def update_status(self, payload: dict, work_sec: int) -> None:
        state, phase = payload["state"], payload["phase"]
        remaining = payload["next_break_in_sec"]
        self._paused = state == "paused"
        self.pause_button.text = i18n.t("tray.resume" if self._paused else "tray.pause_hour")
        self.pause_button.update()

        if phase in ("break", "long_break", "locked_break"):
            self.ring.set_values(1.0, i18n.t("home.on_break"), "", theme.p().accent)
            return
        if self._paused:
            self.ring.set_values(0.0, i18n.t("home.paused_short"),
                                 i18n.t("tray.paused"), theme.p().text_3)
            return
        if state in ("idle", "locked"):
            self.ring.set_values(0.0, i18n.t("home.away_short"),
                                 i18n.t(f"home.status_{state}"), theme.p().text_3)
            return

        minutes, seconds = int(remaining) // 60, int(remaining) % 60
        tone = theme.p().warn if remaining <= 120 else None
        self.ring.set_values(
            1.0 - min(1.0, remaining / max(1, work_sec)),
            f"{minutes}:{seconds:02d}",
            i18n.t("home.until_break"),
            tone,
        )

    def update_stats(self, stats: DayStats) -> None:
        self._today = stats
        if self.garden is not None:
            self.garden.update_break_summary(stats.completed)
        self.refresh_greeting()
        palette = theme.p()
        missed = stats.skipped + stats.emergency
        self.completed.set_values(str(stats.completed), i18n.t("stats.completed"),
                                  palette.success)
        self.skipped.set_values(str(missed), i18n.t("stats.missed"),
                                palette.danger if missed else palette.text_3)
        self.screen_time.set_values(i18n.human_time(stats.screen_sec),
                                    i18n.t("stats.screen_time"))

    def retranslate(self) -> None:
        super().retranslate()
        self.refresh_greeting()
        self.break_button.text = i18n.t("tray.break_now")
        self.pause_button.text = i18n.t("tray.resume" if self._paused else "tray.pause_hour")
        self.pause_button.colour = theme.p().text
        self.break_button.update()
        self.pause_button.update()

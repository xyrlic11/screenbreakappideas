"""The sixty seconds before a long break.

Deliberately *not* fullscreen. This is the warning that your screen is
about to lock, so covering the screen would stop you doing the one thing
it is telling you to do: save your work. It floats, it never takes focus,
and it is impossible to miss.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import i18n
from ..core.models import Config
from . import icons, theme
from .widgets import FlatButton

_WIDTH, _HEIGHT = 640, 262


class LongWarningPanel(QWidget):
    snoozed = Signal()
    cancelled = Signal()

    def __init__(self, config: Config) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_WIDTH, _HEIGHT)
        self.cfg = config

        self._remaining = 0.0
        self._total = max(1.0, float(config.long_break.warn_lead_sec))
        self._will_lock = False
        self._snoozes_left = 0

        self.snooze_button = FlatButton("", accent=True, parent=self)
        self.snooze_button.clicked.connect(self._on_snooze)
        self.snooze_button.setGeometry(32, _HEIGHT - 82, 280, 44)

        self.cancel_button = FlatButton(i18n.t("longwarn.cancel"), parent=self)
        self.cancel_button.clicked.connect(self.cancelled.emit)
        self.cancel_button.setGeometry(_WIDTH - 32 - 280, _HEIGHT - 82, 280, 44)

    def _on_snooze(self) -> None:
        if self._snoozes_left > 0:
            self.snoozed.emit()

    # -- lifecycle ---------------------------------------------------------

    def begin(self, remaining_sec: float, snoozes_left: int, will_lock: bool) -> None:
        self._total = max(1.0, remaining_sec)
        self.update_state(remaining_sec, snoozes_left, will_lock)
        area = QGuiApplication.primaryScreen().availableGeometry()
        self.move(area.center().x() - _WIDTH // 2, area.top() + area.height() // 9)
        self.show()
        self.raise_()

    def update_state(self, remaining_sec: float, snoozes_left: int,
                     will_lock: bool) -> None:
        self._remaining = max(0.0, remaining_sec)
        self._snoozes_left = snoozes_left
        self._will_lock = will_lock

        minutes = round(self.cfg.long_break.snooze_sec / 60)
        self.snooze_button.text = (
            i18n.t("longwarn.snooze", minutes=minutes, count=snoozes_left)
            if snoozes_left > 0 else i18n.t("longwarn.snooze_none"))
        self.snooze_button.accent = snoozes_left > 0
        self.snooze_button.update()
        self.cancel_button.text = i18n.t("longwarn.cancel")
        self.cancel_button.update()
        self.update()

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        tone = palette.danger if self._will_lock else palette.warn

        base = QColor(palette.bg)
        base.setAlpha(248)
        p.setPen(QPen(palette.stroke, 1))
        p.setBrush(base)
        p.drawRoundedRect(rect, 12, 12)

        icons.draw(p, icons.LOCK if self._will_lock else icons.TIMER,
                   QRectF(rect.left() + 32, rect.top() + 34, 30, 30), tone, 24)

        p.setPen(palette.text)
        p.setFont(theme.font(theme.TITLE, QFont.Weight.DemiBold))
        p.drawText(rect.adjusted(74, 28, -32, 0),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                   i18n.t("longwarn.title", seconds=int(math.ceil(self._remaining))))

        detail = (i18n.t("longwarn.will_lock") if self._will_lock
                  else i18n.t("longwarn.will_overlay",
                              minutes=round(self.cfg.long_break.break_sec / 60)))
        p.setPen(tone)
        p.setFont(theme.font(theme.BODY))
        p.drawText(rect.adjusted(74, 74, -32, -96),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
                   | Qt.TextFlag.TextWordWrap, detail)

        # A bar that empties as the countdown runs out.
        left = max(0.0, min(1.0, self._remaining / self._total))
        track = QRectF(rect.left() + 32, rect.top() + 122, rect.width() - 64, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(palette.alpha(palette.text_3, 60))
        p.drawRoundedRect(track, 2, 2)
        p.setBrush(tone)
        p.drawRoundedRect(QRectF(track.left(), track.top(), track.width() * left,
                                 track.height()), 2, 2)
        p.end()

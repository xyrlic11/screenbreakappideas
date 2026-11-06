"""Tray icon: the app's only permanent presence on screen.

The icon is drawn rather than shipped, so it can carry the progress ring
towards the next break — the state is readable without opening anything.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import i18n
from ..core.models import Config
from . import theme

_SIZE = 64


class TrayIcon(QObject):
    open_window = Signal()
    break_now = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    quit_requested = Signal()

    def __init__(self, config: Config, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.cfg = config
        self._icon_key: tuple | None = None
        self._paused = False

        self.tray = QSystemTrayIcon(parent)
        self.tray.setIcon(_ring_icon(0.0, theme.p().accent))
        self.tray.activated.connect(self._on_activated)
        self.retranslate()
        self.tray.show()

    # -- menu --------------------------------------------------------------

    def retranslate(self) -> None:
        menu = QMenu()
        self._add(menu, i18n.t("tray.open"), self.open_window.emit)
        menu.addSeparator()
        self._add(menu, i18n.t("tray.break_now"), self.break_now.emit)
        self._pause_action = self._add(
            menu, i18n.t("tray.resume" if self._paused else "tray.pause_hour"),
            self._toggle_pause)
        menu.addSeparator()
        self._add(menu, i18n.t("tray.quit"), self.quit_requested.emit)

        self._menu = menu           # keep a reference or Qt bins it
        self.tray.setContextMenu(menu)

    def _add(self, menu: QMenu, text: str, slot) -> QAction:
        action = QAction(text, menu)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _toggle_pause(self) -> None:
        (self.resume_requested if self._paused else self.pause_requested).emit()

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_window.emit()

    # -- driven by the policy ---------------------------------------------

    def update_status(self, payload: dict) -> None:
        state, phase = payload["state"], payload["phase"]
        remaining = payload["next_break_in_sec"]
        work = max(1, self.cfg.short_break.work_sec)
        fraction = 1.0 - min(1.0, remaining / work)
        palette = theme.p()

        was_paused, self._paused = self._paused, state == "paused"
        if was_paused != self._paused:
            self._pause_action.setText(
                i18n.t("tray.resume" if self._paused else "tray.pause_hour"))

        if phase in ("break", "long_break", "locked_break"):
            line, colour, fraction = i18n.t("tray.breaking"), palette.accent, 1.0
        elif state == "paused":
            line, colour = i18n.t("tray.paused"), palette.text_3
        elif state == "locked":
            line, colour = i18n.t("tray.locked"), palette.text_3
        elif state == "idle":
            line, colour = i18n.t("tray.idle"), palette.text_3
        else:
            line = i18n.t("tray.counting", time=i18n.human_time(remaining))
            colour = (palette.warn if remaining <= self.cfg.short_break.toast_lead_sec
                      else palette.accent)

        long_left = payload.get("next_long_break_in_sec")
        if long_left is not None:
            line += "\n" + i18n.t("tray.long_line", time=i18n.human_time(long_left))
        self.tray.setToolTip(line)

        # Redrawing the pixmap 86,400 times a day is pointless; only redraw
        # when the ring would actually look different.
        key = (round(fraction, 2), colour.name())
        if key != self._icon_key:
            self._icon_key = key
            self.tray.setIcon(_ring_icon(fraction, colour))

    def hide(self) -> None:
        self.tray.hide()


def _ring_icon(fraction: float, colour: QColor) -> QIcon:
    pixmap = QPixmap(_SIZE, _SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(7, 7, _SIZE - 14, _SIZE - 14)

    track = QColor(colour)
    track.setAlpha(65)
    p.setPen(QPen(track, 7))
    p.drawEllipse(rect)

    if fraction > 0:
        p.setPen(QPen(colour, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        # Qt angles are in sixteenths of a degree, clockwise from 12 o'clock.
        p.drawArc(rect, 90 * 16, int(-360 * 16 * min(1.0, fraction)))
    p.end()
    return QIcon(pixmap)

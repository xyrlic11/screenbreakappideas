"""Bootstrap and wiring.

The tick loop lives here and nowhere else: read sensors, hand them to the
core, carry out whatever commands come back. This file contains no rule
about when a break is due — that is entirely the policy's business.
"""

from __future__ import annotations

import ctypes
import sys
import time

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from .. import i18n
from ..core.models import (Command, CommandKind as K, Config, LOCK, OVERLAY,
                           POPUP)
from ..core.ticker import Ticker
from ..sensors import SensorReader, lock_workstation
from ..storage.config import save_config
from ..storage.db import History
from . import activities, icons, theme
from .break_popup import BreakPopup
from .edge_glow import EdgeGlow
from .hotkey import EmergencyHotkey
from .hud import MiniHud
from .long_warning import LongWarningPanel
from .overlay_manager import OverlayManager
from .sounds import Sounds
from .toast import Toast
from .tray import TrayIcon
from .window import MainWindow

_PAUSE_SEC = 3600


def set_dpi_awareness() -> None:
    """Must run before QApplication exists.

    Get this wrong and the overlay is blurry or mis-sized on any laptop at
    125-150% scaling — a bug that is miserable to track down later.
    """
    try:
        # PER_MONITOR_AWARE_V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


class Controller(QObject):
    def __init__(self, config: Config, debug: bool = False) -> None:
        super().__init__()
        self.cfg = config
        self.debug = debug

        self.ticker = Ticker(config)
        self.reader = SensorReader()
        self.history = History()

        self.overlays = OverlayManager(config, self)
        self.popup = BreakPopup(config)
        self.toast = Toast()
        self.edge = EdgeGlow()
        self.long_warning = LongWarningPanel(config)
        self.tray = TrayIcon(config, self)
        self.sounds = Sounds(config)
        self.window = MainWindow(config, self.history)
        self.hud = MiniHud(config)

        # Whichever of the two is showing the current break. Everything after
        # START_BREAK talks to this rather than to a specific presenter.
        self._presenter = self.overlays
        self._mode = OVERLAY

        # Screen time at the moment a break started, so the record says what
        # the break actually interrupted.
        self._screen_at_break = 0.0
        self._last_screen_sec = 0.0

        self._handlers = {
            K.SHOW_TOAST: lambda p: self.toast.show_for(int(p["seconds_left"])),
            K.SHOW_EDGE: lambda p: self.edge.show(),
            K.HIDE_EDGE: lambda p: self.edge.hide(),
            K.START_BREAK: self._on_start_break,
            K.UPDATE_BREAK: lambda p: self._presenter.set_remaining(p["remaining_sec"]),
            K.END_BREAK: self._on_end_break,
            K.SHOW_LONG_WARNING: self._on_show_long_warning,
            K.UPDATE_LONG_WARNING: self._on_update_long_warning,
            K.HIDE_LONG_WARNING: lambda p: self.long_warning.hide(),
            K.LOCK_WORKSTATION: self._on_lock,
            K.TRAY: self._on_status,
            K.LOG: self._on_log,
        }

        self._connect()
        self.hotkey = EmergencyHotkey(self._on_emergency)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

    def _connect(self) -> None:
        self.overlays.skipped.connect(lambda: self._act(self.ticker.skip(_now(), "skipped")))
        self.overlays.emergency.connect(self._on_emergency)
        # Waving the popup away is the same decision as pressing skip.
        self.popup.dismissed.connect(lambda: self._act(self.ticker.skip(_now(), "skipped")))
        self._connect_long_warning()

        self.tray.open_window.connect(self.window.reveal)
        self.tray.break_now.connect(self._break_now)
        self.tray.pause_requested.connect(self._pause)
        self.tray.resume_requested.connect(self.ticker.resume)
        self.tray.quit_requested.connect(self.shutdown)

        self.window.break_now.connect(self._break_now)
        self.window.pause_toggled.connect(self._toggle_pause)
        self.window.settings_changed.connect(self._on_settings_changed)
        self.hud.clicked.connect(self.window.reveal)

    # -- the loop ----------------------------------------------------------

    def start(self) -> None:
        if not self.hotkey.register():
            self._log("could not register Ctrl+Alt+Shift+Esc (already taken?)")
        QApplication.instance().installNativeEventFilter(self.hotkey)
        self.timer.start()
        self._tick()      # draw a correct tray icon immediately, not in a second

    def _tick(self) -> None:
        self._dispatch(self.ticker.advance(self.reader.read()))

    def _act(self, commands: list[Command]) -> None:
        """Commands produced by a click rather than by the clock."""
        self._dispatch(commands)

    def _dispatch(self, commands: list[Command]) -> None:
        for command in commands:
            handler = self._handlers.get(command.kind)
            if handler is not None:
                handler(command.payload)

    # -- handlers ----------------------------------------------------------

    def _on_status(self, payload: dict) -> None:
        self._last_screen_sec = payload["screen_time_sec"]
        self.tray.update_status(payload)
        self.window.update_status(payload)

        # Polled rather than driven by hide/minimise events: one check a
        # second is self-correcting, and covers every way a window can
        # go away without three separate event overrides.
        away = not self.window.isVisible() or self.window.isMinimized()
        if away and self.cfg.hud.enabled:
            self.hud.update_status(payload, self.cfg.short_break.work_sec)
            self.hud.reveal()
        else:
            self.hud.hide()

    def _enforcement(self, kind: str) -> str:
        section = self.cfg.long_break if kind == "long" else self.cfg.short_break
        return section.enforcement

    def _on_start_break(self, payload: dict) -> None:
        self.hud.hide()      # the break itself is the status now
        self.toast.hide()
        self.edge.hide()
        self._screen_at_break = self._last_screen_sec

        kind, duration = payload["kind"], payload["duration_sec"]
        mode = self._enforcement(kind)
        # Picked here rather than inside a presenter, so both of them show the
        # same thing and the choice does not depend on which one is on screen.
        activity = activities.pick(kind, duration)

        self._mode = mode
        self._presenter = self.popup if mode == POPUP else self.overlays
        self._presenter.begin(kind, duration, activity)
        self.sounds.play_start()
        if self.debug:
            self._log(f"break started: {kind} as {mode} via {activity.key}")

    def _on_end_break(self, payload: dict) -> None:
        self._presenter.finish()
        self.sounds.play_end()
        self._record(payload["kind"], payload["outcome"])

    def _on_lock(self, payload: dict) -> None:
        # Just ask. The policy watches whether the screen really went away and
        # sends END_BREAK with the honest outcome when it knows.
        self._mode = LOCK
        self._screen_at_break = self._last_screen_sec
        lock_workstation()

    def _record(self, kind: str, outcome: str) -> None:
        planned = (self.cfg.long_break.break_sec if kind == "long"
                   else self.cfg.short_break.break_sec)
        self.history.record_break(kind, outcome, planned, self._screen_at_break,
                                  mode=self._mode)
        self.window.refresh_stats()

    def _on_show_long_warning(self, payload: dict) -> None:
        self.toast.hide()   # a pending eye-break toast is now beside the point
        self.edge.hide()
        self.long_warning.begin(
            payload["remaining_sec"], payload["snoozes_left"], payload["will_lock"])

    def _on_update_long_warning(self, payload: dict) -> None:
        self.long_warning.update_state(
            payload["remaining_sec"], payload["snoozes_left"], payload["will_lock"])

    def _connect_long_warning(self) -> None:
        self.long_warning.snoozed.connect(lambda: self._act(self.ticker.snooze(_now())))
        self.long_warning.cancelled.connect(self._on_emergency)

    def _on_emergency(self) -> None:
        self._act(self.ticker.skip(_now(), "emergency"))

    def _on_log(self, payload: dict) -> None:
        if self.debug:
            self._log(", ".join(f"{k}={v}" for k, v in payload.items()))

    def _log(self, message: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)

    # -- user actions ------------------------------------------------------

    def _break_now(self) -> None:
        self._act(self.ticker.break_now(_now()))

    def _pause(self) -> None:
        self.ticker.pause(_now(), _PAUSE_SEC)

    def _toggle_pause(self) -> None:
        if self.ticker.machine.paused_until is None:
            self._pause()
        else:
            self.ticker.resume()

    def _on_settings_changed(self) -> None:
        """Config objects are shared by reference, so most changes are live.

        Language and appearance still need the widgets told to redraw.
        """
        i18n.load(self.cfg.language)
        theme.set_mode(self.cfg.appearance)
        QApplication.instance().setStyleSheet(theme.stylesheet())
        self.hud.reposition()
        self.tray.retranslate()
        self.window.apply_theme()
        self.long_warning.close()
        self.long_warning.deleteLater()     # or every language switch leaks one
        self.long_warning = LongWarningPanel(self.cfg)
        self._connect_long_warning()

    def shutdown(self) -> None:
        self.timer.stop()
        self.hotkey.unregister()
        self._presenter.finish()
        self.edge.hide()
        self.toast.hide()
        self.long_warning.hide()
        self.hud.hide()
        self.window.hide()
        self.tray.hide()
        self.history.close()
        save_config(self.cfg)
        QApplication.instance().quit()


def _now() -> float:
    return time.monotonic()


def run(config: Config, debug: bool = False, show_window: bool = True) -> int:
    set_dpi_awareness()                       # before QApplication, always
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)      # closing the window is not quitting
    app.setApplicationName("Blink")

    theme.load_fonts()
    theme.set_mode(config.appearance)
    app.setStyleSheet(theme.stylesheet())
    i18n.load(config.language)
    app.setWindowIcon(icons.app_icon(theme.p().accent))

    controller = Controller(config, debug)
    controller.start()
    if show_window:
        controller.window.reveal()
    if debug:
        controller._log(
            f"debug mode: break every {config.short_break.work_sec}s, "
            f"long break every {config.long_break.work_sec}s, "
            f"theme={'dark' if theme.is_dark() else 'light'}"
        )
    return app.exec()

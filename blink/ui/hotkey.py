"""Ctrl+Alt+Shift+Esc — the way out when the mouse is not an option.

This is a safety net twice over: for the user if an overlay ever wedges,
and for whoever is developing it with a fullscreen window in the way.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter

_user32 = ctypes.windll.user32

_HOTKEY_ID = 0xB11
_WM_HOTKEY = 0x0312
_MOD_ALT, _MOD_CONTROL, _MOD_SHIFT, _MOD_NOREPEAT = 0x0001, 0x0002, 0x0004, 0x4000
_VK_ESCAPE = 0x1B


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
    ]


class EmergencyHotkey(QAbstractNativeEventFilter):
    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__()
        self._callback = callback
        self.registered = False

    def register(self) -> bool:
        modifiers = _MOD_CONTROL | _MOD_ALT | _MOD_SHIFT | _MOD_NOREPEAT
        self.registered = bool(
            _user32.RegisterHotKey(None, _HOTKEY_ID, modifiers, _VK_ESCAPE)
        )
        return self.registered

    def unregister(self) -> None:
        if self.registered:
            _user32.UnregisterHotKey(None, _HOTKEY_ID)
            self.registered = False

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = _MSG.from_address(int(message))
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                self._callback()
        return False, 0

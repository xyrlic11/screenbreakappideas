"""Is the workstation locked, and how do we lock it.

Polling OpenInputDesktop once a second is far less code than registering
for WTS session notifications, and it needs no window to receive them.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32

_DESKTOP_SWITCHDESKTOP = 0x0100

_user32.OpenInputDesktop.restype = wintypes.HANDLE
_user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_user32.CloseDesktop.argtypes = [wintypes.HANDLE]


def screen_locked() -> bool:
    """True when the lock screen (or a secure desktop) is up.

    When the desktop is locked the input desktop belongs to Winlogon and
    this call fails, which is exactly the signal we want.
    """
    handle = _user32.OpenInputDesktop(0, False, _DESKTOP_SWITCHDESKTOP)
    if not handle:
        return True
    _user32.CloseDesktop(handle)  # every successful open must be closed
    return False


def lock_workstation() -> bool:
    """The one place in this app that actually locks the screen."""
    return bool(_user32.LockWorkStation())

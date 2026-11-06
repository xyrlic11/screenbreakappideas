"""How long since the user last touched anything.

Uses GetLastInputInfo rather than a keyboard hook. That choice is the
whole privacy story of this app:

  * it reports *when* input happened, never *what* was pressed
  * it is not a hook, so antivirus does not flag it as a keylogger
  * it needs no elevation and costs essentially nothing per call
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_kernel32.GetTickCount64.restype = ctypes.c_ulonglong


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds() -> float:
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not _user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0

    # dwTime is a 32-bit tick count that wraps roughly every 49.7 days while
    # GetTickCount64 does not, so fold the difference back into 32 bits.
    elapsed_ms = (_kernel32.GetTickCount64() - info.dwTime) & 0xFFFFFFFF
    return elapsed_ms / 1000.0

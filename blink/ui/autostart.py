"""Start with Windows.

The HKCU Run key rather than Task Scheduler: one registry value, no
elevation, and the user can see and remove it from Task Manager's Startup
tab like any other app.
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "Blink"


def command() -> str:
    """The exact command line Windows will run at login.

    Always --tray: having a window appear over whatever you opened first
    thing in the morning is how a startup app earns its way out of Startup.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'

    # pythonw.exe, so a dev install does not park a console window on screen.
    interpreter = Path(sys.executable)
    windowless = interpreter.with_name("pythonw.exe")
    if windowless.exists():
        interpreter = windowless

    # A Run entry has no working directory, so point sys.path at the checkout
    # rather than relying on `-m blink` resolving from wherever Windows starts us.
    project = Path(__file__).resolve().parents[2]
    bootstrap = (f"import sys;sys.path.insert(0, r'{project}');"
                 f"from blink.__main__ import main;sys.exit(main(['--tray']))")
    return f'"{interpreter}" -c "{bootstrap}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, _VALUE_NAME)[0])
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Returns whether the registry now matches what was asked for."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(key, _VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False

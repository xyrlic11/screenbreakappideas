"""config.json — hand-editable, and hard to break by hand.

Anything missing is filled from the defaults and written back, anything
out of range is clamped rather than rejected. A typo in this file should
never stop the app from starting.
"""

from __future__ import annotations

import json
import os
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from ..core.models import (Config, HUD_CORNERS, LOCK, LONG_ENFORCEMENT,
                           OVERLAY, SHORT_ENFORCEMENT)

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Blink"
CONFIG_PATH = CONFIG_DIR / "config.json"

# Sane bounds, keyed by dotted path. Values outside these are clamped, not
# refused: a 3-second work interval is a typo, not a feature request.
LIMITS: dict[str, tuple[float, float]] = {
    "short_break.work_sec": (60, 7200),
    "short_break.break_sec": (5, 600),
    "short_break.toast_lead_sec": (0, 600),
    "short_break.edge_lead_sec": (0, 120),
    "long_break.work_sec": (600, 86400),
    "long_break.break_sec": (30, 3600),
    "long_break.warn_lead_sec": (5, 600),
    "long_break.snooze_sec": (30, 3600),
    "long_break.snooze_max": (0, 10),
    "idle.idle_threshold_sec": (10, 3600),
    "idle.reset_threshold_sec": (30, 7200),
    "idle.sleep_gap_sec": (10, 600),
    "grace.max_defer_sec": (0, 900),
    "grace.quiet_input_sec": (1, 60),
    "skip.hold_sec": (0, 30),
}

# String fields with a fixed set of answers. Anything else falls back to the
# default rather than reaching the UI as an unknown mode.
CHOICES: dict[str, tuple[str, ...]] = {
    "short_break.enforcement": SHORT_ENFORCEMENT,
    "long_break.enforcement": LONG_ENFORCEMENT,
    "appearance": ("system", "light", "dark"),
    "hud.corner": HUD_CORNERS,
}


def _migrate(raw: dict[str, Any]) -> dict[str, Any]:
    """Carry older config files forward.

    real_lock was a boolean before the break screen became a choice of
    three. True meant lock, False meant the fullscreen overlay.
    """
    long_break = raw.get("long_break")
    if isinstance(long_break, dict) and "enforcement" not in long_break:
        if "real_lock" in long_break:
            long_break["enforcement"] = LOCK if long_break.pop("real_lock") else OVERLAY
    return raw


def load_config() -> Config:
    """Read config.json, healing anything that is missing or silly."""
    raw: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}   # a corrupt file falls back to defaults rather than dying

    config = _from_dict(Config(), _migrate(raw), prefix="")
    save_config(config)     # write back a complete, well-formed file
    return config


def save_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(_to_dict(config), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# -- dataclass <-> dict ----------------------------------------------------


def _from_dict(target: Any, raw: dict[str, Any], prefix: str) -> Any:
    for f in fields(target):
        value = raw.get(f.name)
        attr = getattr(target, f.name)
        path = f"{prefix}{f.name}"

        if is_dataclass(attr):
            _from_dict(attr, value if isinstance(value, dict) else {}, f"{path}.")
        elif value is not None and isinstance(value, type(attr)):
            setattr(target, f.name, _clamp(path, value, attr))
        elif isinstance(attr, float) and isinstance(value, int):
            setattr(target, f.name, _clamp(path, float(value), attr))
    return target


def _to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {f.name: _to_dict(getattr(value, f.name)) for f in fields(value)}
    return value


def _clamp(path: str, value: Any, default: Any = None) -> Any:
    if isinstance(value, str):
        allowed = CHOICES.get(path)
        if allowed is None or value in allowed:
            return value
        # Fall back to what the dataclass declares, not to allowed[0]: for
        # long breaks that would silently promote a typo into locking the
        # screen, which is the most aggressive setting there is.
        return default

    limits = LIMITS.get(path)
    if limits is None or isinstance(value, bool):
        return value
    low, high = limits
    return type(value)(min(max(value, low), high))

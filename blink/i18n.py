"""Two languages, one dict, no build step.

Qt's .ts/.qm pipeline means recompiling every time a string changes. For
two languages and a hundred strings that is all cost and no benefit, so
this is a plain JSON lookup that can switch language without a restart.
"""

from __future__ import annotations

import json
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locales"
_FALLBACK = "en"

_strings: dict[str, str] = {}
_fallback_strings: dict[str, str] = {}
_current = "th"


def available() -> list[str]:
    return sorted(p.stem for p in _LOCALE_DIR.glob("*.json"))


def load(language: str) -> str:
    """Switch language. Returns the language actually loaded."""
    global _strings, _fallback_strings, _current
    if language not in available():
        language = _FALLBACK
    _strings = _read(language)
    _fallback_strings = _read(_FALLBACK) if language != _FALLBACK else _strings
    _current = language
    return language


def current() -> str:
    return _current


def t(key: str, **kw) -> str:
    """Look up a string. Missing keys surface as the key itself, loudly."""
    if not _strings:
        load(_current)
    text = _strings.get(key) or _fallback_strings.get(key) or key
    if not kw:
        return text
    try:
        return text.format(**kw)
    except (KeyError, IndexError):
        return text


def human_time(seconds: float) -> str:
    """'1 ชม. 5 นาที' / '1h 5m' — whichever language is loaded."""
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        return t("time.hm", hours=seconds // 3600, minutes=(seconds % 3600) // 60)
    if seconds >= 60:
        return t("time.m", minutes=seconds // 60)
    return t("time.s", seconds=seconds)


def _read(language: str) -> dict[str, str]:
    path = _LOCALE_DIR / f"{language}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

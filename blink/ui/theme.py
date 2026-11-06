"""Design tokens, Windows 11 flavoured.

Colours, type scale and window effects all come from one place. The app
follows the system: it reads the accent colour and the light/dark
preference out of the registry rather than inventing its own palette, so
it looks like it belongs on the machine it is running on.

The break overlay is the one deliberate exception — it stays dark in
either theme, because a bright screen is the opposite of an eye break.
"""

from __future__ import annotations

import ctypes
import winreg
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase

# --------------------------------------------------------------------------
# Reading the system's mind
# --------------------------------------------------------------------------

_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_ACCENT_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"

_FALLBACK_ACCENT = ("#4CC2FF", "#0067C0")   # (dark ui, light ui)


def system_is_dark() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PERSONALIZE) as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return True


def system_accent(dark: bool) -> QColor:
    """Pull the accent shade Windows itself would use for this theme.

    AccentPalette is eight RGBA swatches from lightest to darkest. Windows
    picks a light one for dark UI and a dark one for light UI so that the
    contrast works either way; we do the same.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _ACCENT_KEY) as key:
            palette = winreg.QueryValueEx(key, "AccentPalette")[0]
        index = 1 if dark else 4
        offset = index * 4
        return QColor(palette[offset], palette[offset + 1], palette[offset + 2])
    except (OSError, IndexError):
        return QColor(_FALLBACK_ACCENT[0] if dark else _FALLBACK_ACCENT[1])


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    dark: bool
    accent: QColor
    bg: QColor            # window base, sits behind the Mica backdrop
    layer: QColor         # cards and panels
    layer_alt: QColor     # hover / selected rows
    stroke: QColor        # hairline borders
    text: QColor
    text_2: QColor        # secondary
    text_3: QColor        # disabled / hints
    success: QColor
    warn: QColor
    danger: QColor

    def alpha(self, colour: QColor, alpha: int) -> QColor:
        out = QColor(colour)
        out.setAlpha(alpha)
        return out


def _dark_palette() -> Palette:
    return Palette(
        dark=True,
        accent=system_accent(True),
        bg=QColor(32, 32, 32),
        layer=QColor(255, 255, 255, 15),
        layer_alt=QColor(255, 255, 255, 26),
        stroke=QColor(255, 255, 255, 20),
        text=QColor(255, 255, 255),
        text_2=QColor(255, 255, 255, 200),
        text_3=QColor(255, 255, 255, 120),
        success=QColor("#6CCB5F"),
        warn=QColor("#FCE100"),
        danger=QColor("#FF99A4"),
    )


def _light_palette() -> Palette:
    return Palette(
        dark=False,
        accent=system_accent(False),
        # Tuned against measured contrast, not by eye: the secondary text
        # used to land at 3:1 on a card, which is under the 4.5:1 floor and
        # is exactly the text every setting description is written in.
        bg=QColor(237, 237, 237),
        layer=QColor(255, 255, 255),
        layer_alt=QColor(246, 246, 246),
        stroke=QColor(0, 0, 0, 38),
        text=QColor(23, 23, 23),
        text_2=QColor(60, 60, 60),
        text_3=QColor(97, 97, 97),
        success=QColor("#0F7B0F"),
        warn=QColor("#9D5D00"),
        danger=QColor("#C42B1C"),
    )


# The break overlay ignores the system theme on purpose.
OVERLAY_BG = QColor(11, 16, 22)
OVERLAY_TEXT = QColor(230, 237, 243)
OVERLAY_MUTED = QColor(139, 148, 158)
OVERLAY_FAINT = QColor(74, 84, 96)

_mode = "system"
_palette: Palette | None = None


def set_mode(mode: str) -> None:
    """mode: 'system' | 'light' | 'dark'"""
    global _mode, _palette
    _mode = mode if mode in ("system", "light", "dark") else "system"
    _palette = None


def is_dark() -> bool:
    if _mode == "system":
        return system_is_dark()
    return _mode == "dark"


def p() -> Palette:
    """The active palette. Short name because it is used everywhere."""
    global _palette
    if _palette is None:
        _palette = _dark_palette() if is_dark() else _light_palette()
    return _palette


def refresh() -> None:
    """Re-read the system after it may have changed."""
    global _palette
    _palette = None


# --------------------------------------------------------------------------
# Type
# --------------------------------------------------------------------------

_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

# Latin from Segoe UI Variable for the Fluent look, Thai from Leelawadee UI
# (or bundled Sarabun). Qt walks this list per glyph, so both get the right
# face without any manual script detection.
_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Leelawadee UI", "Tahoma"]

# Thai stacks vowels above and tone marks below the baseline; the default
# Qt leading lets adjacent rows collide.
LINE_HEIGHT = 1.5

_loaded = False


def load_fonts() -> list[str]:
    global _loaded, _FAMILIES
    if _loaded:
        return _FAMILIES

    for path in sorted(_FONT_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(path))

    installed = set(QFontDatabase.families())
    bundled = [f for f in ("Sarabun",) if f in installed]
    _FAMILIES = bundled + [f for f in _FAMILIES if f in installed] + ["Segoe UI"]
    _loaded = True
    return _FAMILIES


# Fluent's type ramp, in pixels so DPI scaling stays predictable.
CAPTION, BODY, BODY_LG, SUBTITLE, TITLE, TITLE_LG, DISPLAY = 12, 14, 16, 20, 28, 40, 68


def font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(load_fonts())
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


def semibold(size: int) -> QFont:
    return font(size, QFont.Weight.DemiBold)


# --------------------------------------------------------------------------
# Stock widgets
# --------------------------------------------------------------------------


def stylesheet() -> str:
    """Drag Qt's built-in controls into the same design language.

    Short list, because the app paints its own number and choice fields:
    the one text box, scroll bars, the menus those choice fields pop up,
    and tooltips.
    """
    c = p()
    stroke = _rgba(c.stroke)
    text = _rgba(c.text)
    base = _rgba(c.bg, 250)

    return f"""
    QLineEdit {{
        background: {_rgba(c.layer_alt)};
        border: 1px solid {stroke};
        border-radius: 5px;
        padding: 6px 9px;
        color: {text};
        selection-background-color: {c.accent.name()};
        selection-color: {_rgba(c.bg, 255)};
    }}
    QLineEdit:hover {{ border-color: {_rgba(c.accent, 130)}; }}
    QLineEdit:focus {{ border-color: {c.accent.name()}; }}

    QScrollBar:vertical {{
        background: transparent; width: 12px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {_rgba(c.text_3, 70)};
        border-radius: 3px; min-height: 28px; margin: 0 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {_rgba(c.text_3, 140)}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QMenu {{
        background: {base};
        border: 1px solid {stroke};
        border-radius: 7px;
        padding: 5px;
        color: {text};
    }}
    QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {_rgba(c.accent, 55)}; }}
    QMenu::separator {{ height: 1px; background: {stroke}; margin: 5px 8px; }}

    QToolTip {{
        background: {base}; color: {text};
        border: 1px solid {stroke}; border-radius: 5px; padding: 5px 8px;
    }}
    """


def _rgba(colour: QColor, alpha: int | None = None) -> str:
    a = colour.alpha() if alpha is None else alpha
    return f"rgba({colour.red()},{colour.green()},{colour.blue()},{a})"


# --------------------------------------------------------------------------
# Window effects
# --------------------------------------------------------------------------

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_SYSTEMBACKDROP_TYPE = 38
_BACKDROP_MICA = 2
_CORNER_ROUND = 2


def apply_window_effects(widget) -> bool:
    """Dark title bar, rounded corners and a Mica backdrop.

    Returns True when Mica was accepted. The caller paints its own solid
    background when it was not, so this degrades to a plain window rather
    than a transparent one on anything older than Windows 11.
    """
    try:
        hwnd = ctypes.c_void_p(int(widget.winId()))
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                  ctypes.c_void_p, ctypes.c_uint]
        set_attribute.restype = ctypes.c_long
    except Exception:
        return False

    def attr(code: int, value: int) -> int:
        payload = ctypes.c_int(value)
        return set_attribute(hwnd, code, ctypes.byref(payload), ctypes.sizeof(payload))

    attr(_DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if is_dark() else 0)
    attr(_DWMWA_WINDOW_CORNER_PREFERENCE, _CORNER_ROUND)
    return attr(_DWMWA_SYSTEMBACKDROP_TYPE, _BACKDROP_MICA) == 0

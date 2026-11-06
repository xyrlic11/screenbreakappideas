"""Generate assets/blink.ico from the same mark the app draws at runtime.

Keeps one definition of the logo instead of a hand-drawn file that drifts
away from what the tray and window actually show. Run it via tools/build.py,
or on its own after changing the mark.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QIODevice, Qt      # noqa: E402
from PySide6.QtGui import QColor, QPixmap              # noqa: E402
from PySide6.QtWidgets import QApplication             # noqa: E402

from blink.ui.icons import app_icon                    # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUT = ROOT / "assets" / "blink.ico"

# Fixed rather than the live system accent: the file on disk must not change
# depending on who built it.
BRAND = QColor("#4CC2FF")


def png_bytes(pixmap: QPixmap) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def build() -> Path:
    app = QApplication.instance() or QApplication(sys.argv)
    icon = app_icon(BRAND, 256)

    images = []
    for size in SIZES:
        pixmap = icon.pixmap(size, size)
        if pixmap.width() != size:      # redraw rather than upscale
            pixmap = app_icon(BRAND, size).pixmap(size, size)
        images.append((size, png_bytes(pixmap)))

    offset = 6 + 16 * len(images)
    header = struct.pack("<HHH", 0, 1, len(images))
    directory, blobs = b"", b""
    for size, data in images:
        directory += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,   # 0 means 256 in the ICO header
            0 if size >= 256 else size,
            0, 0, 1, 32, len(data), offset,
        )
        blobs += data
        offset += len(data)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(header + directory + blobs)
    del app
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"wrote {path} ({path.stat().st_size:,} bytes, {len(SIZES)} sizes)")

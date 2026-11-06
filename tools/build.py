"""Build the distributable app.

    python tools/build.py

Regenerates the icon, runs PyInstaller and reports where the exe landed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from tools.make_icon import build as build_icon

    icon = build_icon()
    print(f"icon      {icon.relative_to(ROOT)} ({icon.stat().st_size:,} bytes)")

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         str(ROOT / "blink.spec")],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("\nPyInstaller failed. Is it installed?  pip install pyinstaller")
        return result.returncode

    exe = ROOT / "dist" / "Blink" / "Blink.exe"
    if not exe.exists():
        print("\nBuild finished but Blink.exe is missing — check the log above.")
        return 1

    total = sum(f.stat().st_size for f in exe.parent.rglob("*") if f.is_file())
    print(f"\nbuilt     {exe}")
    print(f"size      {total / 1_048_576:.0f} MB in {exe.parent.name}/")
    print("\nNote: the exe is unsigned, so SmartScreen will warn the first time"
          "\nsomeone other than you runs it. Signing needs a certificate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

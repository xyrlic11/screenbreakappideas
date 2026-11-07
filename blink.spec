# PyInstaller build for Blink.  Run it through tools/build.py, which
# regenerates the icon first:  python tools/build.py
#
# --noconsole is set via console=False below, so double-clicking the exe
# does not park a black window behind the tray icon.

import os
import pathlib
from pathlib import Path

ROOT = Path(SPECPATH)

# PyInstaller searches PATH for DLL dependencies. Match the Windows loader's
# preference for System32 so tools on PATH cannot shadow Qt's system ICU.
if os.name == "nt":
    system32 = Path(os.environ["SystemRoot"]) / "System32"
    os.environ["PATH"] = os.pathsep.join((str(system32), os.environ.get("PATH", "")))

# BLINK_CONSOLE=1 builds a console version. Invaluable when something only
# breaks once frozen, since a windowed build has nowhere to print.
CONSOLE = bool(os.environ.get("BLINK_CONSOLE"))

datas = [
    (str(ROOT / "blink" / "locales"), "blink/locales"),
]

# Any font dropped into assets/fonts ships with the build.
fonts = ROOT / "assets" / "fonts"
if list(fonts.glob("*.ttf")):
    datas.append((str(fonts), "assets/fonts"))

analysis = Analysis(
    # launcher.py, not blink/__main__.py: PyInstaller runs the entry script
    # without package context, which breaks every relative import inside it.
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["blink.ui.activities"],
    hookspath=[],
    runtime_hooks=[],
    # Qt modules the app never touches. Audio goes through winsound, so
    # QtMultimedia can go — and with it FFmpeg, and with QtNetwork, OpenSSL.
    # A tray app that promises no network should not be shipping libssl.
    excludes=[
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
        "PySide6.QtQml", "PySide6.QtBluetooth", "PySide6.QtSql", "PySide6.QtTest",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtDesigner",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtNetwork",
        "PySide6.QtPositioning", "PySide6.QtSerialPort", "PySide6.QtSensors",
        # pathlib pulls urllib.request, which pulls ssl, which pulls OpenSSL.
        # Both urllib.request and http.client guard that import with
        # try/except ImportError, so dropping it costs nothing here.
        "ssl", "_ssl",
        "tkinter", "unittest", "pydoc",
    ],
    noarchive=False,
)

# The PySide6 hook copies Qt DLLs generously. These are for QML and Quick,
# which a widgets-only app never loads. opengl32sw stays: it is Qt's software
# renderer fallback, and machines without a GPU driver need it to start.
_UNWANTED = ("qt6qml", "qt6quick", "qt6network")
analysis.binaries = TOC(
    entry for entry in analysis.binaries
    if not pathlib.Path(entry[0]).name.lower().startswith(_UNWANTED)
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Blink",
    debug=False,
    strip=False,
    upx=False,
    console=CONSOLE,            # tray app: no console window by default
    icon=str(ROOT / "assets" / "blink.ico"),
    version_info=None,
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Blink",
)

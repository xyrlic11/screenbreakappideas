"""Frozen-build entry point.

PyInstaller runs its entry script as a bare top-level module, with no
package context — so pointing it straight at blink/__main__.py makes every
relative import inside fail with "attempted relative import with no known
parent package". This file imports the package properly instead.

For development, `python -m blink` remains the way in.
"""

from blink.__main__ import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli())

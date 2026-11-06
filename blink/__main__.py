"""Entry point.

    python -m blink              run it for real
    python -m blink --debug      same thing, 20 seconds instead of 20 minutes
    python -m blink --simulate 8h   replay a day through the core, no UI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.models import CommandKind, Config, SensorReading
from .core.ticker import Ticker
from .storage.config import CONFIG_PATH, load_config

# Per-second chatter; the interesting lines are the state changes.
_NOISE = {CommandKind.TRAY, CommandKind.UPDATE_BREAK, CommandKind.UPDATE_LONG_WARNING}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="blink", description="Screen break reminder")
    parser.add_argument("--debug", action="store_true",
                        help="shrink every interval so a full cycle takes seconds")
    parser.add_argument("--simulate", metavar="DURATION",
                        help="replay N hours (e.g. 8h) through the core and exit")
    parser.add_argument("--idle", type=float, default=2.0,
                        help="idle seconds to simulate per tick (default: 2)")
    parser.add_argument("--tray", action="store_true",
                        help="start in the tray without opening the window")
    return parser.parse_args(argv)


def simulate(config: Config, duration: str, idle_sec: float) -> int:
    """Print the timeline the policy would produce, with no Qt in sight."""
    seconds = _parse_duration(duration)
    if seconds is None:
        print(f"could not read a duration from {duration!r}; try 8h or 90m")
        return 2

    ticker = Ticker(config)
    now, wall = 0.0, 1_700_000_000.0

    print(f"{'time':>9}  event")
    print("-" * 60)
    for _ in range(int(seconds)):
        now += 1.0
        wall += 1.0
        for command in ticker.advance(SensorReading(
            now=now, wall=wall, idle_sec=idle_sec, screen_locked=False,
        )):
            if command.kind not in _NOISE:
                print(f"{_clock(now):>9}  {command!r}")
    print("-" * 60)
    print(f"simulated {duration} of screen time")
    return 0


def _parse_duration(text: str) -> float | None:
    units = {"h": 3600, "m": 60, "s": 1}
    text = text.strip().lower()
    factor = units.get(text[-1:], None)
    number = text[:-1] if factor else text
    try:
        return float(number) * (factor or 1)
    except ValueError:
        return None


def _clock(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    config = load_config()
    if args.debug:
        config = config.debug_preset()

    if args.simulate:
        return simulate(config, args.simulate, args.idle)

    from .ui.app import run   # imported late so --simulate needs no Qt
    print(f"Blink running. Config: {CONFIG_PATH}")
    return run(config, debug=args.debug, show_window=not args.tray)


def _crash_log(error: BaseException) -> Path:
    """Packaged builds have no console, so a crash would otherwise be silent."""
    import traceback
    from datetime import datetime

    path = CONFIG_PATH.parent / "crash.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} "
                      f"(frozen={getattr(sys, 'frozen', False)}) =====\n")
            traceback.print_exception(type(error), error, error.__traceback__, file=log)
    except OSError:
        pass
    return path


def run_cli(argv: list[str] | None = None) -> int:
    """Entry point with the crash log attached. Used by launcher.py too."""
    try:
        return main(argv)
    except SystemExit:
        raise
    except BaseException as error:               # noqa: BLE001 - last resort
        location = _crash_log(error)
        print(f"Blink crashed. Details written to {location}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_cli())

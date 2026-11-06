"""A fake clock and a synthetic timeline driver.

Because blink.core never touches the real clock, a whole working day can
be replayed here in milliseconds.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blink.core.models import Command, CommandKind, Config, SensorReading  # noqa: E402
from blink.core.ticker import Ticker  # noqa: E402


class Driver:
    """Feeds one synthetic second at a time into a Ticker."""

    def __init__(self, config: Config | None = None) -> None:
        self.cfg = config or Config()
        self.ticker = Ticker(self.cfg)
        self.now = 1_000.0
        self.wall = 1_700_000_000.0
        self.ticks = 0
        self.history: list[tuple[int, Command]] = []

    # -- driving -----------------------------------------------------------

    def tick(self, idle: float = 0.0, locked: bool = False,
             wall_gap: float = 1.0) -> list[Command]:
        self.now += 1.0
        self.wall += wall_gap
        self.ticks += 1
        cmds = self.ticker.advance(SensorReading(
            now=self.now, wall=self.wall, idle_sec=idle, screen_locked=locked,
        ))
        self.history.extend((self.ticks, c) for c in cmds)
        return cmds

    def run(self, seconds: float, **kw) -> list[Command]:
        """Hold the same conditions for N seconds."""
        out: list[Command] = []
        for _ in range(int(seconds)):
            out.extend(self.tick(**kw))
        return out

    def idle_for(self, seconds: float) -> list[Command]:
        """Walk away: idle_sec climbs by one each second, as Windows reports it."""
        out: list[Command] = []
        for i in range(1, int(seconds) + 1):
            out.extend(self.tick(idle=float(i)))
        return out

    def sleep_gap(self, gap_sec: float) -> list[Command]:
        """Suspend the machine: the wall clock jumps, the tick stream does not."""
        return self.tick(wall_gap=gap_sec)

    # -- inspecting --------------------------------------------------------

    @property
    def screen_time(self) -> float:
        return self.ticker.machine.screen_time_sec

    @property
    def long_time(self) -> float:
        return self.ticker.machine.long_time_sec

    def first_tick_of(self, kind: CommandKind) -> int | None:
        for tick, cmd in self.history:
            if cmd.kind is kind:
                return tick
        return None

    def payloads(self, kind: CommandKind) -> list[dict]:
        return [c.payload for _, c in self.history if c.kind is kind]


def kinds(cmds: list[Command]) -> list[CommandKind]:
    return [c.kind for c in cmds]


def has(cmds: list[Command], kind: CommandKind) -> bool:
    return any(c.kind is kind for c in cmds)


def only(cmds: list[Command], kind: CommandKind) -> Command:
    matches = [c for c in cmds if c.kind is kind]
    assert len(matches) == 1, f"expected exactly one {kind}, got {matches}"
    return matches[0]

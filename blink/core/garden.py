"""Blink Garden's catalog and progression rules."""

from dataclasses import dataclass
from math import isqrt


@dataclass(frozen=True)
class BreakReward:
    xp: int
    coins: int
    work_sec: int
    rest_sec: int
    daily_cap: int


BREAK_REWARDS = {
    "short": BreakReward(25, 5, 20 * 60, 20, 4),
    "long": BreakReward(60, 15, 2 * 60 * 60, 5 * 60, 1),
}
QUESTS = {"first": 1, "second": 2}
QUEST_XP = 30
QUEST_COINS = 10


@dataclass(frozen=True)
class Cosmetic:
    level: int
    price: int


CATALOG = {
    "sapling": Cosmetic(1, 0),
    "flowers": Cosmetic(1, 10),
    "mushrooms": Cosmetic(2, 15),
    "bench": Cosmetic(2, 25),
    "pond": Cosmetic(3, 35),
    "lantern": Cosmetic(4, 45),
    "cherry": Cosmetic(5, 65),
    "glowing": Cosmetic(7, 100),
}

ACHIEVEMENTS = ("first_rest", "fresh_start", "consistent_care",
                "long_rest", "keeper", "guardian")

COLUMNS, ROWS = 7, 4
STARTER_CELL = (3, 0)
PATH_ROW = 2


def valid_cell(column: int, row: int) -> bool:
    return (isinstance(column, int) and isinstance(row, int)
            and 0 <= column < COLUMNS and 0 <= row < ROWS and row != PATH_ROW)


def level_for(xp: int) -> int:
    return 1 + (isqrt(9 + 4 * (xp // 25)) - 3) // 2


def level_floor(level: int) -> int:
    steps = level - 1
    return 25 * steps * (steps + 3)


@dataclass(frozen=True)
class Progress:
    xp: int = 0
    level: int = 1
    coins: int = 0

    @property
    def level_xp(self) -> int:
        return self.xp - level_floor(self.level)

    @property
    def next_level_xp(self) -> int:
        return level_floor(self.level + 1) - level_floor(self.level)


@dataclass(frozen=True)
class Reward:
    xp: int
    coins: int
    before_level: int
    level: int
    badges: tuple[str, ...]

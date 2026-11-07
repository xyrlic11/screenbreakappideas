"""Local garden save data, sharing the break history connection."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from ..core.garden import (
    BREAK_REWARDS, CATALOG, QUEST_COINS, QUEST_XP, QUESTS, STARTER_CELL,
    Progress, Reward, level_for, valid_cell,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS garden_player (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    xp INTEGER NOT NULL CHECK (xp >= 0),
    level INTEGER NOT NULL CHECK (level >= 1),
    coins INTEGER NOT NULL CHECK (coins >= 0)
);
INSERT OR IGNORE INTO garden_player VALUES (1, 0, 1, 0);
CREATE TABLE IF NOT EXISTS garden_break_rewards (
    break_id INTEGER PRIMARY KEY REFERENCES breaks(id),
    day TEXT NOT NULL,
    kind TEXT NOT NULL,
    earned_at REAL NOT NULL,
    xp INTEGER NOT NULL,
    coins INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS garden_rewards_day ON garden_break_rewards(day, kind);
CREATE INDEX IF NOT EXISTS garden_rewards_recent ON garden_break_rewards(kind, earned_at);
CREATE TABLE IF NOT EXISTS garden_quest_claims (
    day TEXT NOT NULL,
    quest_id TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    PRIMARY KEY (day, quest_id)
);
CREATE TABLE IF NOT EXISTS garden_achievements (
    achievement_id TEXT PRIMARY KEY,
    unlocked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS garden_inventory (
    item_id TEXT PRIMARY KEY,
    col INTEGER,
    row INTEGER,
    CHECK ((col IS NULL) = (row IS NULL)),
    UNIQUE (col, row)
);
"""


class Garden:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        with self._db:
            self._db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA)
            self._db.execute("INSERT OR IGNORE INTO garden_inventory VALUES (?, ?, ?)",
                             ("sapling", *STARTER_CELL))

    def progress(self) -> Progress:
        row = self._db.execute("SELECT xp, level, coins FROM garden_player").fetchone()
        return Progress(*row)

    def quests(self, day: str) -> tuple[int, set[str]]:
        count = self._db.execute(
            "SELECT COUNT(*) FROM garden_break_rewards WHERE day = ?", (day,),
        ).fetchone()[0]
        claimed = self._db.execute(
            "SELECT quest_id FROM garden_quest_claims WHERE day = ?", (day,),
        )
        return count, {row[0] for row in claimed}

    def achievements(self) -> dict[str, str]:
        return dict(self._db.execute("SELECT achievement_id, unlocked_at FROM garden_achievements"))

    def inventory(self) -> dict[str, tuple[int, int] | None]:
        return {key: None if col is None else (col, row) for key, col, row in
                self._db.execute("SELECT item_id, col, row FROM garden_inventory")}

    def grant_break(self, break_id: int, kind: str, day: str, moment: datetime,
                    planned_sec: float, screen_sec: float, interval_sec: float) -> Reward | None:
        """Called inside History's write transaction after inserting the break."""
        rule = BREAK_REWARDS.get(kind)
        if (rule is None or planned_sec < rule.rest_sec or screen_sec < rule.work_sec
                or interval_sec < rule.work_sec):
            return None
        count = self._db.execute(
            "SELECT COUNT(*) FROM garden_break_rewards WHERE day = ? AND kind = ?",
            (day, kind),
        ).fetchone()[0]
        last = self._db.execute(
            "SELECT MAX(earned_at) FROM garden_break_rewards WHERE kind = ?", (kind,),
        ).fetchone()[0]
        now = moment.timestamp()
        if count >= rule.daily_cap or (last is not None and now - last < rule.work_sec):
            return None
        self._db.execute(
            "INSERT INTO garden_break_rewards VALUES (?, ?, ?, ?, ?, ?)",
            (break_id, day, kind, now, rule.xp, rule.coins),
        )
        return self._credit(rule.xp, rule.coins, day, moment)

    def claim(self, quest: str, day: str, moment: datetime) -> Reward | None:
        if quest not in QUESTS:
            return None
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            count, claimed = self.quests(day)
            if count < QUESTS[quest] or quest in claimed:
                return None
            self._db.execute("INSERT INTO garden_quest_claims VALUES (?, ?, ?)",
                             (day, quest, moment.isoformat(timespec="seconds")))
            return self._credit(QUEST_XP, QUEST_COINS, day, moment)

    def _credit(self, xp: int, coins: int, day: str, moment: datetime) -> Reward:
        before = self.progress()
        level = level_for(before.xp + xp)
        self._db.execute(
            "UPDATE garden_player SET xp = xp + ?, level = ?, coins = coins + ?",
            (xp, level, coins),
        )
        total, long_count = self._db.execute(
            "SELECT COUNT(*), COUNT(CASE WHEN kind = 'long' THEN 1 END)"
            " FROM garden_break_rewards",
        ).fetchone()
        today, _ = self.quests(day)
        checks = {
            "first_rest": total >= 1,
            "fresh_start": today >= 3,
            "consistent_care": total >= 10,
            "long_rest": long_count >= 1,
            "keeper": level >= 5,
            "guardian": total >= 50,
        }
        unlocked = []
        for badge, earned in checks.items():
            if earned and self._db.execute(
                "INSERT INTO garden_achievements VALUES (?, ?)"
                " ON CONFLICT(achievement_id) DO NOTHING",
                (badge, moment.isoformat(timespec="seconds")),
            ).rowcount:
                unlocked.append(badge)
        return Reward(xp, coins, before.level, level, tuple(unlocked))

    def buy(self, item_id: str) -> bool:
        item = CATALOG.get(item_id)
        if item is None:
            return False
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            bought = self._db.execute(
                "UPDATE garden_player SET coins = coins - ?"
                " WHERE coins >= ? AND level >= ? AND NOT EXISTS"
                " (SELECT 1 FROM garden_inventory WHERE item_id = ?)",
                (item.price, item.price, item.level, item_id),
            ).rowcount
            if bought:
                self._db.execute("INSERT INTO garden_inventory (item_id) VALUES (?)", (item_id,))
            return bool(bought)

    def place(self, item_id: str, col: int, row: int) -> bool:
        if item_id not in CATALOG or item_id == "sapling" or not valid_cell(col, row):
            return False
        with self._db:
            return bool(self._db.execute(
                "UPDATE OR IGNORE garden_inventory SET col = ?, row = ? WHERE item_id = ?",
                (col, row, item_id),
            ).rowcount)

    def remove(self, item_id: str) -> bool:
        if item_id == "sapling":
            return False
        with self._db:
            return bool(self._db.execute(
                "UPDATE garden_inventory SET col = NULL, row = NULL"
                " WHERE item_id = ? AND col IS NOT NULL", (item_id,),
            ).rowcount)

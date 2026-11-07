"""Break history.

Only what the stats page actually reads back, and nothing that could
identify what you were doing: no window titles, no process names, no
keystrokes. Just when a break was due, what you did about it, and how
long you had been at the screen.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time as time_of_day, timedelta
from pathlib import Path
from uuid import uuid4

from ..core.garden import Reward
from .config import CONFIG_DIR
from .garden import Garden

DB_PATH = CONFIG_DIR / "blink.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS breaks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT    NOT NULL,          -- ISO-8601 local time
    day           TEXT    NOT NULL,          -- logical day, see day_of()
    kind          TEXT    NOT NULL,          -- 'short' | 'long'
    outcome       TEXT    NOT NULL,          -- completed | skipped | emergency
    planned_sec   INTEGER NOT NULL,
    screen_sec    INTEGER NOT NULL           -- screen time it interrupted
);
CREATE INDEX IF NOT EXISTS breaks_day ON breaks(day);
"""

# Added after the first release. A completed break means something different
# depending on whether the screen was taken over or a card appeared in the
# corner, so the record has to say which.
_MIGRATIONS = {
    "mode": "ALTER TABLE breaks ADD COLUMN mode TEXT NOT NULL DEFAULT 'overlay'",
    "event_id": "ALTER TABLE breaks ADD COLUMN event_id TEXT",
}

# 04:00, so a session that runs past midnight still belongs to the day it
# started. Working until 2am is the same day, whatever the calendar says.
DAY_BOUNDARY = time_of_day(4, 0)


def day_of(moment: datetime) -> str:
    logical = moment.date()
    if moment.time() < DAY_BOUNDARY:
        logical -= timedelta(days=1)
    return logical.isoformat()


@dataclass(frozen=True)
class DayStats:
    day: str
    completed: int = 0
    skipped: int = 0
    emergency: int = 0
    long_breaks: int = 0
    screen_sec: int = 0
    enforced: int = 0        # of the completed ones, how many were unavoidable

    @property
    def due(self) -> int:
        return self.completed + self.skipped + self.emergency

    @property
    def compliance(self) -> float:
        """Share of breaks actually taken, 0.0-1.0. No breaks due = a clean 1.0."""
        return 1.0 if self.due == 0 else self.completed / self.due


class History:
    def __init__(self, path: Path | str | None = None, *, rewards_enabled: bool = True) -> None:
        self.path = Path(path) if path is not None else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path))
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._rewards_enabled = rewards_enabled
        self._db.executescript(_SCHEMA)
        self._migrate()
        self.garden = Garden(self._db)

    def _migrate(self) -> None:
        """Add event identity without rewriting historical break rows."""
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            columns = {row["name"] for row in self._db.execute("PRAGMA table_info(breaks)")}
            for column, statement in _MIGRATIONS.items():
                if column not in columns:
                    self._db.execute(statement)
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS breaks_event ON breaks(event_id)")

    def close(self) -> None:
        self._db.close()

    # -- writing -----------------------------------------------------------

    def record_break(self, kind: str, outcome: str, planned_sec: float,
                     screen_sec: float, moment: datetime | None = None,
                     mode: str = "overlay", *, event_id: str | None = None,
                     scheduled: bool = False, reward_screen_sec: float = 0,
                     interval_sec: float = 0) -> Reward | None:
        moment = moment or datetime.now()
        day = day_of(moment)
        with self._db:
            inserted = self._db.execute(
                "INSERT INTO breaks"
                " (started_at, day, kind, outcome, planned_sec, screen_sec, mode, event_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(event_id) DO NOTHING",
                (moment.isoformat(timespec="seconds"), day, kind, outcome,
                 int(planned_sec), int(screen_sec), mode, event_id or uuid4().hex),
            )
            if inserted.rowcount and self._rewards_enabled and scheduled and outcome == "completed":
                return self.garden.grant_break(inserted.lastrowid, kind, day, moment,
                                               planned_sec, reward_screen_sec, interval_sec)
        return None

    def claim_quest(self, quest: str, moment: datetime | None = None) -> Reward | None:
        if not self._rewards_enabled:
            return None
        moment = moment or datetime.now()
        return self.garden.claim(quest, day_of(moment), moment)

    # -- reading -----------------------------------------------------------

    def stats_for(self, day: str) -> DayStats:
        row = self._db.execute(
            """
            SELECT
              SUM(outcome = 'completed')                    AS completed,
              SUM(outcome = 'skipped')                      AS skipped,
              SUM(outcome = 'emergency')                    AS emergency,
              SUM(kind = 'long' AND outcome = 'completed')  AS long_breaks,
              COALESCE(SUM(screen_sec), 0)                  AS screen_sec,
              SUM(outcome = 'completed' AND mode <> 'popup') AS enforced
            FROM breaks WHERE day = ?
            """,
            (day,),
        ).fetchone()
        return DayStats(
            day=day,
            completed=row["completed"] or 0,
            skipped=row["skipped"] or 0,
            emergency=row["emergency"] or 0,
            long_breaks=row["long_breaks"] or 0,
            screen_sec=row["screen_sec"] or 0,
            enforced=row["enforced"] or 0,
        )

    def today(self) -> DayStats:
        return self.stats_for(day_of(datetime.now()))

    def recent(self, days: int = 7) -> list[DayStats]:
        """Oldest first, with empty days filled in so charts have no holes."""
        end = date.fromisoformat(day_of(datetime.now()))
        return [self.stats_for((end - timedelta(days=offset)).isoformat())
                for offset in range(days - 1, -1, -1)]

    def streak(self) -> int:
        """Consecutive days, ending yesterday or today, with nothing skipped.

        A day with no breaks due does not break the streak, but it does not
        extend it either — otherwise a week off would look like discipline.
        """
        count = 0
        today = date.fromisoformat(day_of(datetime.now()))
        for offset in range(0, 366):
            stats = self.stats_for((today - timedelta(days=offset)).isoformat())
            if stats.due == 0:
                if offset == 0:
                    continue      # today has barely started; don't judge it yet
                break
            if stats.skipped or stats.emergency:
                break
            count += 1
        return count

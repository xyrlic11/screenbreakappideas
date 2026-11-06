"""The contract every break activity implements."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter


@dataclass(frozen=True)
class BreakContext:
    remaining: float     # seconds left in the break
    duration: float      # how long the break is in total
    elapsed: float       # seconds since it started
    kind: str            # 'short' | 'long'

    @property
    def fraction_left(self) -> float:
        return max(0.0, min(1.0, self.remaining / max(1.0, self.duration)))


class Activity:
    """Owns the middle of the break screen and nothing else.

    The overlay paints the frame — title, subtitle, clock, buttons and the
    progress bar — then hands over a rectangle.
    """

    key: str = ""
    kinds: tuple[str, ...] = ("short", "long")
    min_duration: float = 0.0

    @property
    def title_key(self) -> str:
        return f"activity.{self.key}.title"

    @property
    def subtitle_key(self) -> str:
        return f"activity.{self.key}.subtitle"

    def paint(self, p: QPainter, rect: QRectF, ctx: BreakContext) -> None:
        raise NotImplementedError

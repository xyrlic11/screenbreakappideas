"""The two pieces of data drawing the app needs."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme


class RingGauge(QWidget):
    """Progress towards the next break, with a caption inside the ring."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.fraction = 0.0
        self.headline = "--"
        self.caption = ""
        self.tone: QColor | None = None
        self.setMinimumSize(220, 220)

    def set_values(self, fraction: float, headline: str, caption: str,
                   tone: QColor | None = None) -> None:
        self.fraction = max(0.0, min(1.0, fraction))
        self.headline = headline
        self.caption = caption
        self.tone = tone
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        colour = self.tone or palette.accent

        side = min(self.width(), self.height())
        thickness = max(8.0, side * 0.055)
        rect = QRectF((self.width() - side) / 2 + thickness,
                      (self.height() - side) / 2 + thickness,
                      side - thickness * 2, side - thickness * 2)

        track = QColor(palette.text_3)
        track.setAlpha(45)
        p.setPen(QPen(track, thickness))
        p.drawEllipse(rect)

        if self.fraction > 0:
            p.setPen(QPen(colour, thickness, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            # Qt angles are sixteenths of a degree, clockwise from 12 o'clock.
            p.drawArc(rect, 90 * 16, int(-360 * 16 * self.fraction))

        p.setPen(palette.text)
        p.setFont(theme.font(int(side * 0.19), QFont.Weight.Light))
        p.drawText(rect.adjusted(0, -side * 0.05, 0, -side * 0.05),
                   Qt.AlignmentFlag.AlignCenter, self.headline)

        p.setPen(palette.text_3)
        p.setFont(theme.font(theme.BODY))
        p.drawText(QRectF(rect.left(), rect.center().y() + side * 0.10,
                          rect.width(), side * 0.2),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   self.caption)
        p.end()


class WeekBars(QWidget):
    """Seven days of compliance. Skips are drawn on top in red.

    Stacked rather than side by side so the height of each bar is the
    number of breaks that came due — a short green bar and a short red one
    tell very different stories.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.days: list[tuple[str, int, int]] = []   # (label, completed, missed)
        self.setMinimumHeight(190)

    def set_days(self, days: list[tuple[str, int, int]]) -> None:
        self.days = days
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        if not self.days:
            return

        label_h, gap = 22, 10
        peak = max((c + m) for _, c, m in self.days) or 1
        plot_h = self.height() - label_h - 6
        slot = self.width() / len(self.days)
        bar_w = min(38.0, slot - gap)

        for index, (label, completed, missed) in enumerate(self.days):
            x = index * slot + (slot - bar_w) / 2
            total_h = plot_h * (completed + missed) / peak
            bottom = plot_h

            if completed + missed == 0:
                empty = QColor(palette.text_3)
                empty.setAlpha(30)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(empty)
                p.drawRoundedRect(QRectF(x, bottom - 3, bar_w, 3), 1.5, 1.5)
            else:
                missed_h = total_h * missed / (completed + missed)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(palette.accent)
                p.drawRoundedRect(QRectF(x, bottom - total_h, bar_w, total_h), 4, 4)
                if missed:
                    p.setBrush(palette.danger)
                    p.drawRoundedRect(
                        QRectF(x, bottom - total_h, bar_w, max(4.0, missed_h)), 4, 4)

            p.setPen(palette.text_3)
            p.setFont(theme.font(theme.CAPTION))
            p.drawText(QRectF(index * slot, plot_h + 6, slot, label_h),
                       Qt.AlignmentFlag.AlignCenter, label)
        p.end()

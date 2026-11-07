"""A scalable, keyboard-operable garden painted with original Qt shapes."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core.garden import COLUMNS, PATH_ROW, ROWS, valid_cell
from . import theme

WIDTH, HEIGHT = 700, 352
LEFT, TOP, CELL_W, CELL_H = 35, 96, 90, 56


def growth_stage(level: int) -> int:
    return sum(level >= milestone for milestone in (3, 5, 7))


def _ellipse(p, color, x, y, width, height):
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(x, y, width, height))


def _rect(p, color, x, y, width, height, radius=3):
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(x, y, width, height), radius, radius)


def _line(p, color, width, x1, y1, x2, y2):
    p.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    p.setPen(Qt.PenStyle.NoPen)


def _pine(p, x, y, scale, shade, light):
    p.save()
    p.translate(x, y)
    p.scale(scale, scale)
    _rect(p, shade, -3, -24, 6, 24, 1)
    for offset, color in ((0, shade), (13, light), (25, light)):
        p.setBrush(QColor(color))
        p.drawPolygon(QPolygonF([QPointF(-21 + offset / 3, -9 - offset),
                                 QPointF(0, -53 - offset / 2),
                                 QPointF(21 - offset / 3, -9 - offset)]))
    p.restore()


def draw_cosmetic(p: QPainter, item: str, x: float, y: float, scale: float = 1,
                  *, growth: int = 0) -> None:
    p.save()
    p.translate(x, y)
    p.scale(scale, scale)
    p.setPen(Qt.PenStyle.NoPen)
    _ellipse(p, "#4c6854", -30, -5, 60, 10)
    if item in ("sapling", "cherry", "glowing"):
        light, shade = {
            "sapling": ("#8dc777", "#39855d"),
            "cherry": ("#f5b9ca", "#bb658d"),
            "glowing": ("#ffeea1", "#b68d48"),
        }[item]
        if growth == 3:
            light, shade = "#e4bb61", "#876841"
        elif growth == 2:
            light, shade = "#aed186", "#487453"
        _rect(p, "#634b3b", -6, -50, 12, 51)
        _rect(p, "#a77950", -2, -49, 5, 49)
        _line(p, "#79573f", 5, 0, -17, -14, -33)
        _line(p, "#79573f", 4, 0, -24, 14, -39)
        _ellipse(p, shade, -34, -61, 67, 39)
        _ellipse(p, shade, -23, -75, 48, 42)
        middle = QColor(light).darker(119)
        _ellipse(p, middle, -29, -62, 33, 29)
        _ellipse(p, middle, 4, -61, 26, 29)
        _ellipse(p, light, -23, -65, 31, 23)
        _ellipse(p, light, -12, -74, 32, 26)
        _ellipse(p, light, 6, -62, 20, 20)
        for px, py in ((-23, -53), (-14, -58), (7, -67), (14, -49), (-5, -42)):
            _rect(p, QColor(light).lighter(113), px, py, 5, 2, 1)
        if item != "sapling" or growth >= 2:
            for dx, dy in ((-26, -49), (-9, -62), (11, -51), (23, -46), (-5, -35)):
                _ellipse(p, "#efbcc8" if growth == 2 else "#fff4d9", dx, dy, 4, 4)
    elif item == "flowers":
        for dx, dy, color in ((-19, -15, "#f1acba"), (-7, -26, "#ffe8a1"),
                              (9, -18, "#d9b4ef"), (21, -23, "#efaa86")):
            _line(p, "#3b7051", 2, dx, 0, dx, dy)
            for px, py in ((-4, 0), (4, 0), (0, -4), (0, 4)):
                _ellipse(p, color, dx + px - 3, dy + py - 3, 6, 6)
            _ellipse(p, "#a97c49", dx - 2, dy - 2, 4, 4)
    elif item == "mushrooms":
        for dx, dy, color in ((-18, -15, "#d16c68"), (1, -27, "#a64f61"),
                              (18, -13, "#e2966b")):
            _rect(p, "#fae3c6", dx - 3, dy, 6, -dy)
            _ellipse(p, color, dx - 10, dy - 8, 20, 12)
            _ellipse(p, "#fff2d0", dx - 5, dy - 5, 3, 3)
            _ellipse(p, "#fff2d0", dx + 2, dy - 3, 3, 3)
    elif item == "bench":
        for dx in (-20, 20):
            _line(p, "#594a43", 5, dx, 0, dx, -28)
        for dy in (-27, -20, -10):
            _rect(p, "#d19b68", -26, dy, 52, 5, 2)
    elif item == "pond":
        _ellipse(p, "#ccc2a3", -34, -23, 68, 28)
        _ellipse(p, "#72bbc6", -30, -21, 60, 22)
        _line(p, "#d0ece0", 2, -22, -12, -7, -12)
        _line(p, "#d0ece0", 2, 1, -6, 14, -6)
        _ellipse(p, "#619773", 12, -15, 12, 6)
        _ellipse(p, "#eaa5ba", 15, -17, 5, 5)
    elif item == "lantern":
        _line(p, "#53463f", 4, 0, 0, 0, -43)
        _rect(p, "#77674e", -10, -48, 20, 24)
        _rect(p, "#ffd886", -7, -45, 14, 17)
        _rect(p, "#53463f", -13, -51, 26, 5)
    p.restore()


class GardenScene(QWidget):
    cell_chosen = Signal(int, int)
    remove_requested = Signal()

    def __init__(self, *, interactive: bool = False) -> None:
        super().__init__()
        self.interactive = interactive
        self.inventory: dict[str, tuple[int, int] | None] = {}
        self.level = 1
        self.selected: str | None = None
        self.hover_cell: tuple[int, int] | None = None
        self.cursor_cell = (0, 0)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        if interactive:
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def heightForWidth(self, width: int) -> int:
        return round(width * HEIGHT / WIDTH)

    def _transform(self) -> tuple[float, float, float]:
        scale = min(self.width() / WIDTH, self.height() / HEIGHT)
        return scale, (self.width() - WIDTH * scale) / 2, (self.height() - HEIGHT * scale) / 2

    def _cell_at(self, position: QPointF) -> tuple[int, int] | None:
        scale, x, y = self._transform()
        if not scale:
            return None
        col = int(((position.x() - x) / scale - LEFT) // CELL_W)
        row = int(((position.y() - y) / scale - TOP) // CELL_H)
        if 0 <= col < COLUMNS and 0 <= row < ROWS:
            return col, row
        return None

    def mousePressEvent(self, event) -> None:
        if not self.interactive or event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        cell = self._cell_at(event.position())
        if cell is not None:
            self.cursor_cell = cell
            self.cell_chosen.emit(*cell)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        cell = self._cell_at(event.position())
        if self.hover_cell != cell:
            self.hover_cell = cell
            self.update()

    def leaveEvent(self, event) -> None:
        self.hover_cell = None
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        key = Qt.Key(event.key())
        directions = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                      Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}
        if key in directions:
            col, row = self.cursor_cell
            dx, dy = directions[key]
            self.cursor_cell = max(0, min(COLUMNS - 1, col + dx)), max(0, min(ROWS - 1, row + dy))
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.cell_chosen.emit(*self.cursor_cell)
        elif key == Qt.Key.Key_Delete:
            self.remove_requested.emit()
        else:
            return super().keyPressEvent(event)
        self.update()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale, x, y = self._transform()
        p.translate(x, y)
        p.scale(scale, scale)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, WIDTH, HEIGHT), 24, 24)
        p.setClipPath(clip)
        p.setPen(Qt.PenStyle.NoPen)
        dark = theme.p().dark
        stage = growth_stage(self.level)
        sky = QLinearGradient(0, 0, 0, 130)
        sky.setColorAt(0, QColor("#273f5d" if dark else "#94c5d7"))
        sky.setColorAt(1, QColor("#627f8d" if dark else "#e8e7ba"))
        p.fillRect(QRectF(0, 0, WIDTH, HEIGHT), sky)
        _ellipse(p, "#ffe4a5", 563, 18, 46, 46)
        for x, y in ((102, 25), (430, 44)):
            cloud = "#92a6a8" if dark else "#f2f0cf"
            _ellipse(p, cloud, x, y + 8, 67, 13)
            _ellipse(p, cloud, x + 15, y, 27, 19)
        _ellipse(p, "#456765" if dark else "#a3bf94", -95, 62, 600, 145)
        _ellipse(p, "#567971" if dark else "#8fb48a", 250, 66, 620, 135)
        for x, y, size in ((10, 112, 1.2), (41, 100, .95), (78, 102, .66),
                           (618, 101, .75), (660, 105, 1.1), (695, 118, 1.33)):
            _pine(p, x, y, size, "#2b524b", "#467b62" if dark else "#64936b")

        meadow = ("#426d57", "#487957", "#517f5d", "#578462") if dark else (
            "#94b779", "#9bbd79", "#a8c67f", "#afca83")
        _rect(p, meadow[stage], -8, 96, WIDTH + 16, HEIGHT - 75, 23)
        path_y = TOP + PATH_ROW * CELL_H
        _rect(p, "#685b4b" if dark else "#b39867", -12, path_y + 5, WIDTH + 24, 46, 14)
        _rect(p, "#82725c" if dark else "#d2b982", -12, path_y + 7, WIDTH + 24, 36, 14)
        for index in range(16):
            x = index * 47 - 9
            y = path_y + 14 + (index % 3) * 3
            _rect(p, "#a19477" if dark else "#e8d3a6", x, y, 31, 14, 4)
        for index in range(117):
            x = (index * 97 + 23) % WIDTH
            y = 101 + (index * 41) % 247
            if not path_y <= y < path_y + CELL_H:
                color = "#78a078" if dark else "#c3d59a"
                _line(p, color, 2, x, y, x + 3, y - 4)
                if index % 4 == 0 or (stage and index % (5 - stage) == 0):
                    _rect(p, ("#efda99", "#e3b2bb", "#efefe0")[index % 3],
                          x + 1, y - 6, 4, 4, 1)
        for x, y in ((12, 129), (686, 147), (15, 302), (677, 322)):
            _ellipse(p, "#64756b" if dark else "#7c8973", x - 12, y, 24, 10)
            _ellipse(p, "#a4b0a0" if dark else "#ccd1ad", x - 8, y, 15, 5)
        for x, y in ((-2, 174), (10, 191), (692, 181), (702, 195),
                     (-1, 346), (20, 354), (684, 351), (700, 340)):
            _ellipse(p, "#365948" if dark else "#6a9260", x - 17, y - 12, 34, 26)
            _ellipse(p, "#67956f" if dark else "#9fb978", x - 11, y - 12, 24, 17)
            for dx, dy in ((-5, -5), (6, -6), (2, 1)):
                _rect(p, "#cda7a7" if stage >= 2 else "#c8ca87", x + dx, y + dy, 4, 3, 1)

        cells = {cell: item for item, cell in self.inventory.items() if cell is not None}
        for row in range(ROWS):
            for col in range(COLUMNS):
                cx, cy = LEFT + col * CELL_W, TOP + row * CELL_H
                item = cells.get((col, row))
                if self.interactive and valid_cell(col, row):
                    selected = item is not None and item == self.selected
                    hovered = self.hover_cell == (col, row)
                    emphasis = selected or hovered
                    color = "#ffe6a2" if emphasis else "#94b599" if dark else "#d8e5b2"
                    p.setPen(QPen(QColor(color), 2 if emphasis else 1,
                                  Qt.PenStyle.SolidLine if emphasis else Qt.PenStyle.DotLine))
                    p.setBrush(QColor(255, 247, 193, 45) if emphasis else Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(QRectF(cx + 4, cy + 4, CELL_W - 8, CELL_H - 8), 8, 8)
                    p.setPen(Qt.PenStyle.NoPen)
        for row in range(ROWS):
            for col in range(COLUMNS):
                item = cells.get((col, row))
                if item:
                    growth = stage if item == "sapling" else 0
                    size = 0.95 + 0.23 * growth
                    draw_cosmetic(p, item, LEFT + (col + 0.5) * CELL_W,
                                  TOP + (row + 1) * CELL_H - 7, size, growth=growth)
        if self.interactive and self.hasFocus():
            col, row = self.cursor_cell
            p.setPen(QPen(QColor("#fff2c6"), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(LEFT + col * CELL_W + 3, TOP + row * CELL_H + 3,
                                     CELL_W - 6, CELL_H - 6), 10, 10)
        p.end()

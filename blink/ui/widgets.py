"""Fluent-flavoured controls.

Qt's stock widgets look like Qt. These are the handful that appear often
enough to be worth drawing properly: the hold-to-skip button, a toggle
switch, and the settings row that wraps a control in a card.
"""

from __future__ import annotations

from PySide6.QtCore import (Property, QEasingCurve, QElapsedTimer, QPointF,
                            QPropertyAnimation, QRectF, Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QVBoxLayout, QWidget)

from . import theme

CARD_RADIUS = 7


class HoldButton(QWidget):
    """A button you must hold down, with the wait drawn into the button.

    The five second hold is the entire cost of skipping a break: long
    enough that you have to decide to do it, short enough not to be spite.
    """

    activated = Signal()

    def __init__(self, text: str, hint: str, hold_sec: float,
                 colour: QColor | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.text = text
        self.hint = hint
        self.hold_sec = max(0.0, hold_sec)
        self.colour = colour or theme.p().text_3

        self._held = QElapsedTimer()
        self._holding = False
        self._progress = 0.0

        self._pulse = QTimer(self)
        self._pulse.setInterval(16)          # ~60fps while held
        self._pulse.timeout.connect(self._advance)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(240, 48)

    def mousePressEvent(self, event) -> None:
        if event.button() is not Qt.MouseButton.LeftButton:
            return
        if self.hold_sec <= 0:
            self.activated.emit()
            return
        self._holding = True
        self._held.restart()
        self._pulse.start()

    def mouseReleaseEvent(self, event) -> None:
        self._reset()

    def leaveEvent(self, event) -> None:
        # Sliding off the button counts as letting go, otherwise you could
        # press and wander off and still skip.
        self._reset()

    def _reset(self) -> None:
        self._holding = False
        self._progress = 0.0
        self._pulse.stop()
        self.update()

    def _advance(self) -> None:
        self._progress = min(1.0, self._held.elapsed() / (self.hold_sec * 1000))
        if self._progress >= 1.0:
            self._reset()
            self.activated.emit()
        else:
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.setClipPath(path)
        if self._progress > 0:
            fill = QColor(self.colour)
            fill.setAlpha(80)
            p.fillRect(QRectF(rect.left(), rect.top(),
                              rect.width() * self._progress, rect.height()), fill)
        p.setClipping(False)

        border = QColor(self.colour)
        border.setAlpha(170 if self.underMouse() else 95)
        p.setPen(QPen(border, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        p.setPen(QColor(self.colour))
        p.setFont(theme.font(theme.BODY))
        p.drawText(rect.adjusted(16, 0, -16, 0),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text)

        if self.hint:
            faint = QColor(self.colour)
            faint.setAlpha(140)
            p.setPen(faint)
            p.setFont(theme.font(theme.CAPTION))
            p.drawText(rect.adjusted(16, 0, -16, 0),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       self.hint)
        p.end()


class FlatButton(QWidget):
    """A quiet outlined button. Easy to click, never inviting."""

    clicked = Signal()

    def __init__(self, text: str, colour: QColor | None = None,
                 accent: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.text = text
        self.colour = colour or theme.p().text
        self.accent = accent
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(140, 40)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() is Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()

    def enterEvent(self, event) -> None:
        self.update()

    def leaveEvent(self, event) -> None:
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        hovered = self.underMouse()

        if self.accent:
            fill = QColor(theme.p().accent)
            if hovered:
                fill = fill.lighter(112)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
            text_colour = QColor(0, 0, 0) if theme.is_dark() else QColor(255, 255, 255)
        else:
            border = QColor(self.colour)
            border.setAlpha(170 if hovered else 95)
            p.setPen(QPen(border, 1))
            p.setBrush(theme.p().layer if hovered else Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
            text_colour = QColor(self.colour)

        p.setPen(text_colour)
        p.setFont(theme.font(theme.BODY))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)
        p.end()


class Toggle(QWidget):
    """The Windows 11 switch: a pill with a thumb that slides and grows."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self._slide = 1.0 if checked else 0.0
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._animation = QPropertyAnimation(self, b"slide", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_slide(self) -> float:
        return self._slide

    def set_slide(self, value: float) -> None:
        self._slide = value
        self.update()

    slide = Property(float, get_slide, set_slide)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, emit: bool = False) -> None:
        if checked == self._checked:
            return
        self._checked = checked
        self._animation.stop()
        self._animation.setStartValue(self._slide)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()
        if emit:
            self.toggled.emit(checked)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked, emit=True)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        palette = theme.p()

        track = QColor(palette.accent)
        if self._slide < 1.0:
            off = QColor(palette.text_3)
            off.setAlpha(60)
            track = _mix(off, track, self._slide)
        p.setBrush(track)
        p.setPen(QPen(palette.stroke, 1))
        p.drawRoundedRect(rect, radius, radius)

        thumb_r = radius - 5
        travel = rect.width() - radius * 2
        centre_x = rect.left() + radius + travel * self._slide
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255) if self._slide > 0.5 or palette.dark
                   else QColor(90, 90, 90))
        p.drawEllipse(QRectF(centre_x - thumb_r, rect.center().y() - thumb_r,
                             thumb_r * 2, thumb_r * 2))
        p.end()


class Card(QWidget):
    """The Fluent settings card: rounded, hairline border, one layer up."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(theme.p().layer)
        p.setPen(QPen(theme.p().stroke, 1))
        p.drawRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
        p.end()


class SettingRow(Card):
    """Label and description on the left, one control on the right."""

    def __init__(self, title: str, description: str, control: QWidget,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = QLabel(title)
        self.title.setFont(theme.font(theme.BODY))
        self.title.setStyleSheet(f"color: {theme.p().text.name()};")
        text.addWidget(self.title)

        self.description = QLabel(description)
        self.description.setFont(theme.font(theme.CAPTION))
        self.description.setStyleSheet(f"color: {theme.p().text_3.name()};")
        self.description.setWordWrap(True)
        self.description.setVisible(bool(description))
        text.addWidget(self.description)

        layout.addLayout(text, 1)
        layout.addWidget(control, 0, Qt.AlignmentFlag.AlignRight)
        self.control = control


class NumberField(QWidget):
    """A spin box that matches the rest of the app.

    QSpinBox is fine functionally, but its arrows come from the platform
    style and cannot be restyled into anything that looks like Fluent, so
    the whole control is painted here instead.
    """

    valueChanged = Signal(int)

    def __init__(self, minimum: int, maximum: int, value: int, suffix: str = "",
                 step: int = 1, unit_key: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.minimum, self.maximum, self.step = minimum, maximum, step
        self.suffix = suffix
        self.unit_key = unit_key   # so the suffix can follow a language change
        self._value = max(minimum, min(maximum, value))
        self._hot = 0        # 0 none, 1 up, -1 down
        self.setFixedSize(148, 36)
        self.setMouseTracking(True)

    def value(self) -> int:
        return self._value

    def setValue(self, value: int, emit: bool = True) -> None:
        value = max(self.minimum, min(self.maximum, int(value)))
        if value == self._value:
            return
        self._value = value
        self.update()
        if emit:
            self.valueChanged.emit(value)

    def _zone(self, pos) -> int:
        if pos.x() < self.width() - _STEPPER_W:
            return 0
        return 1 if pos.y() < self.height() / 2 else -1

    def mouseMoveEvent(self, event) -> None:
        hot = self._zone(event.position())
        if hot != self._hot:
            self._hot = hot
            self.update()

    def leaveEvent(self, event) -> None:
        self._hot = 0
        self.update()

    def mousePressEvent(self, event) -> None:
        direction = self._zone(event.position())
        if direction:
            self.setValue(self._value + direction * self.step)

    def wheelEvent(self, event) -> None:
        delta = 1 if event.angleDelta().y() > 0 else -1
        self.setValue(self._value + delta * self.step)
        event.accept()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        p.setBrush(palette.layer_alt)
        p.setPen(QPen(palette.accent if self.underMouse() else palette.stroke, 1))
        p.drawRoundedRect(rect, 5, 5)

        p.setPen(palette.text)
        p.setFont(theme.font(theme.BODY))
        p.drawText(rect.adjusted(10, 0, -_STEPPER_W - 6, 0),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{self._value}{self.suffix}")

        column = QRectF(rect.right() - _STEPPER_W, rect.top(), _STEPPER_W, rect.height())
        for direction in (1, -1):
            half = QRectF(column.left(),
                          column.top() if direction > 0 else column.center().y(),
                          column.width(), column.height() / 2)
            at_limit = (self._value >= self.maximum if direction > 0
                        else self._value <= self.minimum)
            colour = (palette.text_3 if at_limit
                      else palette.text if self._hot == direction else palette.text_2)
            if self._hot == direction and not at_limit:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(palette.layer)
                p.drawRoundedRect(half.adjusted(1, 1, -3, -1), 3, 3)
            _chevron(p, half.center(), direction, colour)
        p.end()


class ChoiceField(QWidget):
    """A combo box whose popup is a themed QMenu rather than an item view."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], current: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.options = options
        self.current = current
        self.setFixedSize(178, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def label(self) -> str:
        return next((text for value, text in self.options if value == self.current), "")

    def set_options(self, options: list[tuple[str, str]], current: str) -> None:
        self.options, self.current = options, current
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() is not Qt.MouseButton.LeftButton:
            return
        menu = QMenu(self)
        menu.setMinimumWidth(self.width())
        for value, text in self.options:
            action = menu.addAction(("  " if value != self.current else "✓ ") + text)
            action.triggered.connect(lambda _=False, v=value: self._choose(v))
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
        menu.deleteLater()      # parented to self, so it would outlive the click

    def _choose(self, value: str) -> None:
        if value != self.current:
            self.current = value
            self.update()
            self.changed.emit(value)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        p.setBrush(palette.layer_alt)
        p.setPen(QPen(palette.accent if self.underMouse() else palette.stroke, 1))
        p.drawRoundedRect(rect, 5, 5)

        p.setPen(palette.text)
        p.setFont(theme.font(theme.BODY))
        p.drawText(rect.adjusted(11, 0, -30, 0),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.label)

        _chevron(p, QPointF(rect.right() - 16, rect.center().y()), -1, palette.text_2)
        p.end()


_STEPPER_W = 26


def _chevron(p: QPainter, centre: QPointF, direction: int, colour: QColor) -> None:
    """A 'v' or '^' drawn as two strokes — sharper than any font glyph here."""
    w, h = 4.5, 2.6
    tip_y = centre.y() + h * direction * -1
    p.setPen(QPen(colour, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(centre.x() - w, centre.y() + h * direction)
    path.lineTo(centre.x(), tip_y)
    path.lineTo(centre.x() + w, centre.y() + h * direction)
    p.drawPath(path)


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


class TextField(QWidget):
    """A one-line text box.

    Wraps QLineEdit rather than painting an input by hand: it brings the
    caret, selection, undo and — the reason that matters here — a working
    Thai IME, none of which are worth reimplementing for one field.
    """

    edited = Signal(str)

    def __init__(self, value: str = "", placeholder: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line = QLineEdit(value)
        self.line.setPlaceholderText(placeholder)
        self.line.setFixedWidth(178)
        self.line.setFont(theme.font(theme.BODY))
        self.line.setMaxLength(40)
        self.line.textEdited.connect(self._changed)
        layout.addWidget(self.line)

        # Saving on every keystroke would rewrite config.json per letter.
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(400)
        self._settle.timeout.connect(
            lambda: self.edited.emit(self.line.text().strip()))

    def _changed(self, _text: str) -> None:
        self._settle.start()

    def text(self) -> str:
        return self.line.text().strip()

    def setText(self, value: str) -> None:
        self.line.setText(value)

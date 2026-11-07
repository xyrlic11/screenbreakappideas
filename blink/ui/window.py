"""The main window and its Fluent navigation.

Uses the native title bar rather than a hand-drawn one, so snapping,
Aero shake, rounded corners and the dark title bar all come from Windows
instead of being reimplemented badly.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QHBoxLayout, QStackedWidget, QVBoxLayout,
                               QWidget)

from .. import i18n
from ..core.models import Config
from ..core.garden import Reward
from ..storage.db import History, day_of
from . import icons, theme
from .pages import AboutPage, HomePage, SettingsPage, StatsPage
from .pages.garden import AchievementsPage, GardenDashboard, GardenPage, QuestsPage

_SIDEBAR_W = 220
_ITEM_H = 40


class NavItem(QWidget):
    chosen = Signal(int)

    def __init__(self, index: int, glyph: str, key: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index, self.glyph, self.key = index, glyph, key
        self.selected = False
        self.setFixedHeight(_ITEM_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.retranslate()

    def retranslate(self) -> None:
        self.setAccessibleName(i18n.t(self.key))
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self.chosen.emit(self.index)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.chosen.emit(self.index)
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event) -> None:
        self.update()

    def leaveEvent(self, event) -> None:
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.p()
        rect = QRectF(self.rect()).adjusted(4, 2, -4, -2)

        if self.selected or self.underMouse() or self.hasFocus():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(palette.layer_alt if self.selected else palette.layer)
            p.drawRoundedRect(rect, 5, 5)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(palette.accent, 1))
            p.drawRoundedRect(rect, 5, 5)
            p.setPen(Qt.PenStyle.NoPen)

        if self.selected:
            # The accent pill Windows uses to mark the current page.
            p.setBrush(palette.accent)
            p.drawRoundedRect(
                QRectF(rect.left() + 1, rect.center().y() - 8, 3, 16), 1.5, 1.5)

        colour = palette.text if self.selected else palette.text_2
        icons.draw(p, self.glyph, QRectF(rect.left() + 12, rect.top(), 24,
                                         rect.height()), colour, 16)
        p.setPen(colour)
        p.setFont(theme.semibold(theme.BODY) if self.selected else theme.font(theme.BODY))
        p.drawText(rect.adjusted(46, 0, -8, 0),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   i18n.t(self.key))
        p.end()


class MainWindow(QWidget):
    break_now = Signal()
    pause_toggled = Signal()
    settings_changed = Signal()

    def __init__(self, config: Config, history: History, *, debug: bool = False) -> None:
        super().__init__()
        self.cfg = config
        self.history = history
        self._mica = False
        self._quest_day = day_of(datetime.now())
        self._last_status: dict | None = None

        self.setWindowTitle(i18n.t("app.name"))
        self.setWindowIcon(icons.app_icon(theme.p().accent))
        self.resize(920, 660)
        self.setMinimumSize(760, 560)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav_items: list[NavItem] = []
        layout.addWidget(self._sidebar())

        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        self.stack.setStyleSheet("QStackedWidget#pageStack { background: transparent; }")
        self.dashboard = GardenDashboard(history, debug=debug)
        self.home = HomePage(config, garden=self.dashboard)
        self.garden = GardenPage(history)
        self.quests = QuestsPage(history, debug=debug)
        self.achievements = AchievementsPage(history)
        self.stats = StatsPage(history)
        self.settings = SettingsPage(config, self.settings_changed.emit, persist=not debug)
        self.about = AboutPage()
        self.pages = (self.home, self.garden, self.quests, self.achievements,
                      self.stats, self.settings, self.about)
        for page in self.pages:
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        self.home.break_now.connect(self.break_now.emit)
        self.home.pause_toggled.connect(self.pause_toggled.emit)
        self.dashboard.open_garden.connect(lambda: self._select(self.stack.indexOf(self.garden)))
        self.dashboard.open_quests.connect(lambda: self._select(self.stack.indexOf(self.quests)))
        self.garden.changed.connect(self.refresh_garden)
        self.quests.rewarded.connect(self.show_reward)
        self._select(0)

    def _sidebar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedWidth(_SIDEBAR_W)
        bar.setStyleSheet("background:transparent;")
        column = QVBoxLayout(bar)
        column.setContentsMargins(8, 48, 8, 12)   # 48: clear of the title bar
        column.setSpacing(2)

        for index, (glyph, key) in enumerate((
            (icons.HOME, "nav.home"),
            (icons.LEAF, "nav.garden"),
            (icons.LIST, "nav.quests"),
            (icons.AWARD, "nav.achievements"),
            (icons.CHART, "nav.stats"),
            (icons.SETTINGS, "nav.settings"),
            (icons.INFO, "nav.about"),
        )):
            item = NavItem(index, glyph, key)
            item.chosen.connect(self._select)
            self.nav_items.append(item)
            column.addWidget(item)

        column.addStretch(1)
        return bar

    def _select(self, index: int) -> None:
        for item in self.nav_items:
            item.selected = item.index == index
            item.update()
        self.stack.setCurrentIndex(index)
        # The pages paint no background of their own, so the window has to
        # redraw its base or the previous page stays underneath.
        self.update()
        if self.stack.currentWidget() is self.stats:
            self.stats.refresh()

    # -- appearance --------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Needs a real HWND, so it cannot happen in __init__.
        self._mica = theme.apply_window_effects(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, self._mica)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        palette = theme.p()
        if not self._mica:
            # No Mica (older Windows): paint a solid base so the window is
            # not transparent.
            p.fillRect(self.rect(), palette.bg)
        else:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Source, not the default SourceOver. On a translucent window a
            # semi-transparent fill blends into whatever the backing store
            # already held, and since every page is transparent too, nothing
            # ever cleared it — so switching pages stacked the old one under
            # the new. Source replaces those pixels outright.
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(self.rect(), palette.alpha(palette.bg, 190))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Hairline between the nav and the content, the Fluent way.
        p.setPen(QPen(palette.stroke, 1))
        p.drawLine(_SIDEBAR_W, 0, _SIDEBAR_W, self.height())
        p.end()

    def apply_theme(self) -> None:
        theme.refresh()
        self._mica = theme.apply_window_effects(self)
        self.setWindowIcon(icons.app_icon(theme.p().accent))
        self.retranslate()
        self.update()

    def retranslate(self) -> None:
        self.setWindowTitle(i18n.t("app.name"))
        for item in self.nav_items:
            item.retranslate()
        for page in self.pages:
            page.retranslate()
        self.dashboard.retranslate()
        self.refresh_stats()
        self._refresh_home_timer()

    # -- driven by the controller -----------------------------------------

    def update_status(self, payload: dict) -> None:
        self._last_status = payload
        day = day_of(datetime.now())
        if day != self._quest_day:
            self._quest_day = day
            self.refresh_stats()
            self.refresh_garden()
        if self.isVisible():
            self._refresh_home_timer()

    def _refresh_home_timer(self) -> None:
        if self._last_status is not None:
            self.home.update_status(self._last_status, self.cfg.short_break.work_sec)

    def refresh_stats(self) -> None:
        self.home.update_stats(self.history.today())
        if self.stack.currentWidget() is self.stats:
            self.stats.refresh()

    def refresh_garden(self) -> None:
        self.dashboard.refresh()
        self.garden.refresh()
        self.quests.refresh()
        self.achievements.refresh()

    def show_reward(self, reward: Reward) -> None:
        self.refresh_garden()
        self.dashboard.show_reward(reward)

    def set_break_active(self, active: bool) -> None:
        for page in (self.garden, self.quests):
            page.setEnabled(not active)
        if active:
            self.dashboard.stop_animation()

    def reveal(self) -> None:
        self.refresh_stats()
        self.refresh_garden()
        self._refresh_home_timer()
        self.show()
        self.setWindowState(
            self.windowState() & ~Qt.WindowState.WindowMinimized
            | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        # Closing the window leaves the app running in the tray; quitting is
        # a deliberate choice from the tray menu.
        event.ignore()
        self.hide()

    def changeEvent(self, event) -> None:
        if event.type() is QEvent.Type.PaletteChange:
            self.apply_theme()   # the user flipped Windows between light and dark
        super().changeEvent(event)

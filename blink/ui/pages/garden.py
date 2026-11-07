"""Dashboard, garden workshop, daily quests and achievement collection."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from ... import i18n
from ...core.garden import (ACHIEVEMENTS, BREAK_REWARDS, CATALOG, QUEST_COINS,
                            QUEST_XP, QUESTS, Progress, Reward)
from ...storage.db import History, day_of
from .. import icons, theme
from ..garden_scene import GardenScene, draw_cosmetic, growth_stage
from ..widgets import Card
from .base import Page


def _label(*, heading: bool = False) -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setFont(theme.semibold(theme.BODY_LG) if heading else theme.font(theme.BODY))
    return label


def _button() -> QPushButton:
    button = QPushButton()
    button.setFont(theme.semibold(theme.BODY))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _meter(height: int = 9) -> QProgressBar:
    meter = QProgressBar()
    meter.setFixedHeight(height)
    meter.setTextVisible(False)
    return meter


def _card() -> tuple[Card, QVBoxLayout]:
    card = Card()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 13, 16, 13)
    layout.setSpacing(6)
    return card, layout


def _polish(widget: QWidget) -> None:
    palette = theme.p()
    dark = palette.dark
    text = palette.text.name()
    base = "#3d4842" if dark else "#e7eee9"
    muted = "#c7d2cb" if dark else "#45554b"
    mint = "#83c6a4" if dark else "#347a5b"
    hover = "#a5d8ba" if dark else "#286447"
    ink = "#132d23" if dark else "#ffffff"
    widget.setStyleSheet(f"""
        QLabel {{ color: {text}; }}
        QPushButton {{ background: {mint}; color: {ink}; border: 2px solid transparent;
                      border-radius: 8px; padding: 5px 11px; }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:pressed {{ border-color: {ink}; }}
        QPushButton:focus, QComboBox:focus {{ border: 2px solid #b78e42; }}
        QPushButton:disabled {{ background: {base}; color: {muted}; }}
        QPushButton[secondary="true"] {{ background: {base}; color: {text}; }}
        QPushButton[secondary="true"]:hover, QPushButton[secondary="true"]:checked {{
            border-color: {mint};
        }}
        QComboBox {{ background: {base}; color: {text}; border: 2px solid transparent;
                    border-radius: 8px; padding: 5px 12px; }}
        QComboBox QAbstractItemView {{ background: {base}; color: {text};
                                     selection-background-color: {mint}; selection-color: {ink}; }}
        QProgressBar {{ background: {base}; border-radius: 4px; }}
        QProgressBar::chunk {{ background: {mint}; border-radius: 4px; }}
        QProgressBar#gardenXp {{ border-radius: 8px; }}
        QProgressBar#gardenXp::chunk {{ background: {mint}; border-radius: 8px; }}
    """)


class LevelBadge(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(62, 66)
        self.level = 1
        self.pulse = 0.0

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f2cd79").lighter(round(100 + self.pulse * 35)))
        p.drawPolygon(QPolygonF([QPointF(6, 5), QPointF(56, 5), QPointF(56, 47),
                                 QPointF(31, 61), QPointF(6, 47)]))
        p.setPen(QColor("#563a1e"))
        p.setFont(theme.semibold(theme.SUBTITLE))
        p.drawText(QRectF(6, 5, 50, 49), Qt.AlignmentFlag.AlignCenter, str(self.level))
        p.end()


class GardenDashboard(QWidget):
    open_garden = Signal()
    open_quests = Signal()

    def __init__(self, history: History, *, debug: bool = False) -> None:
        super().__init__()
        self.history = history
        self.debug = debug
        self._completed = 0
        self._eligible = 0
        self.last_reward: Reward | None = None
        self.scene = GardenScene()
        self.brand = _label()
        self.stage = _label()
        self.level = _label(heading=True)
        self.badge = LevelBadge()
        self.coins = _label(heading=True)
        self.details = _label()
        self.notice = _label()
        self.notice.hide()
        self.xp = _meter(16)
        self.xp.setObjectName("gardenXp")
        self.open_button = _button()
        self.open_button.clicked.connect(self.open_garden.emit)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        banner = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.brand)
        titles.addWidget(self.stage)
        banner.addLayout(titles, 1)
        banner.addWidget(self.open_button)
        outer.addLayout(banner)
        outer.addWidget(self.scene)

        card, content = _card()
        outer.addWidget(card)
        player = QHBoxLayout()
        player.addWidget(self.badge)
        xp = QVBoxLayout()
        headline = QHBoxLayout()
        headline.addWidget(self.level, 1)
        headline.addWidget(self.coins)
        xp.addLayout(headline)
        xp.addWidget(self.details)
        xp.addWidget(self.xp)
        player.addLayout(xp, 1)
        content.addLayout(player)
        content.addWidget(self.notice)
        self.break_summary = _label()
        content.addWidget(self.break_summary)
        self.rules_button = _button()
        self.rules_button.setCheckable(True)
        self.rules_button.setProperty("secondary", True)
        content.addWidget(self.rules_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.rules = _label()
        self.rules.hide()
        self.rules_button.toggled.connect(self.rules.setVisible)
        content.addWidget(self.rules)

        quest_header = QHBoxLayout()
        self.quest_title = _label(heading=True)
        self.quest_button = _button()
        self.quest_button.clicked.connect(self.open_quests.emit)
        quest_header.addWidget(self.quest_title, 1)
        quest_header.addWidget(self.quest_button)
        outer.addLayout(quest_header)
        self.quest_rows = {}
        for key in QUESTS:
            card, quest = _card()
            row = QHBoxLayout()
            title, payout = _label(heading=True), _label()
            row.addWidget(title, 1)
            row.addWidget(payout)
            quest.addLayout(row)
            objective = _label()
            meter = _meter()
            quest.addWidget(objective)
            quest.addWidget(meter)
            outer.addWidget(card)
            self.quest_rows[key] = title, payout, objective, meter
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(620)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._animate)
        self._progress = Progress()
        self._xp_from = 0
        self.retranslate()

    def _animate(self, value: float) -> None:
        current = self._progress.level_xp
        self.xp.setValue(round(self._xp_from + (current - self._xp_from) * value))
        self.badge.pulse = 1.0 - value
        self.badge.update()
        gold = QColor("#f3d487" if theme.is_dark() else "#825b1b")
        self.notice.setStyleSheet(
            f"color: rgba({gold.red()}, {gold.green()}, {gold.blue()}, {round(150 + 105 * value)});"
        )

    def stop_animation(self) -> None:
        self._animation.stop()
        self._animate(1.0)

    def refresh(self) -> None:
        self._progress = progress = self.history.garden.progress()
        level = i18n.t("garden.level", level=progress.level)
        self.level.setText(level)
        self.badge.level = progress.level
        self.badge.setAccessibleName(level)
        self.badge.update()
        self.coins.setText(i18n.t("garden.coins", coins=progress.coins))
        self.stage.setText(i18n.t(f"garden.stage_{growth_stage(progress.level)}"))
        details = i18n.t("garden.xp", xp=progress.level_xp,
                         needed=progress.next_level_xp, total=progress.xp)
        self.details.setText(details)
        self.xp.setAccessibleName(details)
        self.xp.setRange(0, progress.next_level_xp)
        self.xp.setValue(progress.level_xp)
        self.scene.level = progress.level
        self.scene.inventory = self.history.garden.inventory()
        self.scene.update()
        self.refresh_quests(day_of(datetime.now()))

    def refresh_quests(self, day: str) -> None:
        count, claimed = self.history.garden.quests(day)
        self._eligible = count
        self.update_break_summary(self._completed)
        for key, goal in QUESTS.items():
            title, payout, objective, meter = self.quest_rows[key]
            title.setText(i18n.t(f"quest.{key}"))
            payout.setText(i18n.t("garden.quest_payout", xp=QUEST_XP, coins=QUEST_COINS))
            status = i18n.t("garden.quest_objective", count=min(count, goal), goal=goal)
            if key in claimed:
                status = f"{status}  ·  {i18n.t('garden.claimed')}"
            elif count >= goal:
                status = f"{status}  ·  {i18n.t('garden.ready')}"
            objective.setText(status)
            meter.setAccessibleName(status)
            meter.setRange(0, goal)
            meter.setValue(min(count, goal))

    def update_break_summary(self, completed: int) -> None:
        self._completed = completed
        self.break_summary.setText(i18n.t("garden.debug") if self.debug else i18n.t(
            "garden.break_summary", completed=completed, eligible=self._eligible))

    def retranslate(self) -> None:
        _polish(self)
        self.brand.setText("Blink Garden")
        self.brand.setFont(theme.semibold(theme.SUBTITLE))
        self.brand.setStyleSheet(f"color: {'#a5d8ba' if theme.is_dark() else '#347a5b'};")
        self.open_button.setText(i18n.t("nav.garden"))
        self.quest_title.setText(i18n.t("nav.quests"))
        self.quest_button.setText(i18n.t("garden.view_quests"))
        self.rules_button.setText(i18n.t("garden.why_xp"))
        short, long = BREAK_REWARDS["short"], BREAK_REWARDS["long"]
        self.rules.setText(i18n.t(
            "garden.xp_rules", short_work=i18n.human_time(short.work_sec),
            short_rest=i18n.human_time(short.rest_sec), short_cap=short.daily_cap,
            long_work=i18n.human_time(long.work_sec), long_rest=i18n.human_time(long.rest_sec),
            long_cap=long.daily_cap))
        self.scene.setAccessibleName(i18n.t("garden.preview"))
        self.refresh()
        if self.last_reward is not None:
            self.show_reward(self.last_reward, animate=False)

    def show_reward(self, reward: Reward, *, animate: bool = True) -> None:
        self.last_reward = reward
        messages = [i18n.t("garden.earned", xp=reward.xp, coins=reward.coins)]
        if reward.level > reward.before_level:
            messages.append(i18n.t("garden.level_up", level=reward.level))
            for item_id, item in CATALOG.items():
                if reward.before_level < item.level <= reward.level:
                    messages.append(i18n.t("garden.shop_unlocked", item=i18n.t(f"item.{item_id}")))
        messages.extend(i18n.t(f"badge.{badge}") for badge in reward.badges)
        self.notice.setText("  ·  ".join(messages))
        self.notice.show()
        self.stop_animation()
        if animate and self.isVisible():
            self._xp_from = (max(0, self._progress.level_xp - reward.xp)
                             if reward.level == reward.before_level else 0)
            self._animate(0.0)
            self._animation.setStartValue(0.0)
            self._animation.setEndValue(1.0)
            self._animation.start()


class GardenPage(Page):
    changed = Signal()

    def __init__(self, history: History) -> None:
        super().__init__("nav.garden")
        self.garden = history.garden
        self.scene = GardenScene(interactive=True)
        self.scene.cell_chosen.connect(self._choose_cell)
        self.scene.remove_requested.connect(self._remove)
        self._status: tuple[str, dict] = ("", {})

        toolbar = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.stage = _label(heading=True)
        self.next_unlock = _label()
        titles.addWidget(self.stage)
        titles.addWidget(self.next_unlock)
        toolbar.addLayout(titles, 1)
        self.balance = _label(heading=True)
        toolbar.addWidget(self.balance)
        self.shop_button = _button()
        self.shop_button.clicked.connect(self._show_shop)
        toolbar.addWidget(self.shop_button)
        self.body.addLayout(toolbar)

        row = QHBoxLayout()
        self.items = QComboBox()
        self.items.setFont(theme.font(theme.BODY))
        self.items.currentIndexChanged.connect(self._select_item)
        row.addWidget(self.items, 1)
        self.remove = _button()
        self.remove.clicked.connect(self._remove)
        row.addWidget(self.remove)
        self.body.addLayout(row)
        self.body.addWidget(self.scene)
        self.status = _label()
        self.body.addWidget(self.status)
        self.shop_heading = self.section("garden.shop")
        self.shop_rows = {}
        for item_id in CATALOG:
            card, content = _card()
            row = QHBoxLayout()
            artwork = QLabel()
            pixmap = QPixmap(54, 55)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            draw_cosmetic(painter, item_id, 27, 49, 0.65)
            painter.end()
            artwork.setPixmap(pixmap)
            name = _label(heading=True)
            price = _label()
            button = _button()
            button.clicked.connect(lambda checked=False, key=item_id: self._buy(key))
            row.addWidget(artwork)
            labels = QVBoxLayout()
            labels.addWidget(name)
            labels.addWidget(price)
            row.addLayout(labels, 1)
            row.addWidget(button)
            content.addLayout(row)
            self.body.addWidget(card)
            self.shop_rows[item_id] = name, price, button
        self.body.addStretch()
        self.retranslate()

    def _feedback(self, key: str, **values) -> None:
        self._status = key, values
        self.status.setText(i18n.t(key or "garden.hint", **values))

    def _show_shop(self) -> None:
        self.scroll.ensureWidgetVisible(self.shop_heading, 0, 12)
        # Pin the shop heading at the top of the viewport.
        self.scroll.verticalScrollBar().setValue(self.shop_heading.y())

    def _select_item(self) -> None:
        item_id = self.items.currentData()
        self.scene.selected = item_id
        self.remove.setEnabled(item_id is not None and self.scene.inventory.get(item_id) is not None)
        self.scene.update()

    def _choose_cell(self, col: int, row: int) -> None:
        cell = (col, row)
        occupied = next((item for item, placement in self.scene.inventory.items()
                         if placement == cell), None)
        if occupied is not None and occupied != "sapling":
            self.items.setCurrentIndex(self.items.findData(occupied))
            self._feedback("garden.selected", item=i18n.t(f"item.{occupied}"))
        elif occupied == "sapling":
            self._feedback("garden.starter_fixed")
        elif self.scene.selected is None:
            self._feedback("garden.choose_item")
        elif self.garden.place(self.scene.selected, col, row):
            self._feedback("garden.placed", item=i18n.t(f"item.{self.scene.selected}"))
            self.changed.emit()
        else:
            self._feedback("garden.invalid_cell")

    def _remove(self) -> None:
        if self.scene.selected and self.garden.remove(self.scene.selected):
            self._feedback("garden.removed", item=i18n.t(f"item.{self.scene.selected}"))
            self.changed.emit()

    def _buy(self, item_id: str) -> None:
        if self.garden.buy(item_id):
            self._feedback("garden.purchased", item=i18n.t(f"item.{item_id}"))
            self.changed.emit()
            self.items.setCurrentIndex(self.items.findData(item_id))
            self.scroll.verticalScrollBar().setValue(0)
            self.scene.setFocus()
        else:
            self.refresh()

    def refresh(self) -> None:
        progress = self.garden.progress()
        self.balance.setText(i18n.t("garden.coins", coins=progress.coins))
        self.scene.level = progress.level
        self.stage.setText(i18n.t(f"garden.stage_{growth_stage(progress.level)}"))
        next_item = next(((key, item) for key, item in CATALOG.items()
                          if item.level > progress.level), None)
        if next_item is not None:
            key, item = next_item
            self.next_unlock.setText(i18n.t("garden.next_unlock",
                                           level=item.level, item=i18n.t(f"item.{key}")))
        self.next_unlock.setVisible(next_item is not None)
        self.scene.inventory = owned = self.garden.inventory()
        current = self.items.currentData()
        self.items.blockSignals(True)
        self.items.clear()
        self.items.addItem(i18n.t("garden.pick"), None)
        for item_id, cosmetic in CATALOG.items():
            name, price, button = self.shop_rows[item_id]
            item_name = i18n.t(f"item.{item_id}")
            name.setText(item_name)
            price.setText(i18n.t("garden.price", level=cosmetic.level, coins=cosmetic.price))
            if item_id in owned and item_id != "sapling":
                self.items.addItem(item_name, item_id)
            key = ("garden.owned" if item_id in owned else
                   "garden.locked" if progress.level < cosmetic.level else
                   "garden.need_coins" if progress.coins < cosmetic.price else "garden.buy")
            button.setText(i18n.t(key))
            button.setAccessibleName(f"{item_name} · {i18n.t(key)}")
            button.setEnabled(key == "garden.buy")
        self.items.setCurrentIndex(max(0, self.items.findData(current)))
        self.items.blockSignals(False)
        self._select_item()

    def retranslate(self) -> None:
        super().retranslate()
        _polish(self)
        self.shop_button.setText(i18n.t("garden.shop"))
        self.scene.setAccessibleName(i18n.t("nav.garden"))
        self.scene.setAccessibleDescription(i18n.t("garden.hint"))
        self.items.setAccessibleName(i18n.t("garden.inventory"))
        self.remove.setText(i18n.t("garden.remove"))
        key, values = self._status
        if "item" in values:
            self._feedback("")
        else:
            self._feedback(key, **values)
        self.refresh()


class QuestsPage(Page):
    rewarded = Signal(object)

    def __init__(self, history: History, *, debug: bool = False) -> None:
        super().__init__("nav.quests")
        self.history = history
        self.debug = debug
        self.intro = _label()
        self.body.addWidget(self.intro)
        self.notice = _label()
        self.notice.hide()
        self.body.addWidget(self.notice)
        self.rows = {}
        for key in QUESTS:
            card, content = _card()
            title, progress, meter, claim = _label(heading=True), _label(), _meter(), _button()
            claim.clicked.connect(lambda checked=False, quest=key: self._claim(quest))
            content.addWidget(title)
            content.addWidget(progress)
            content.addWidget(meter)
            content.addWidget(claim, alignment=Qt.AlignmentFlag.AlignLeft)
            self.body.addWidget(card)
            self.rows[key] = title, progress, meter, claim
        self.body.addStretch()
        self.retranslate()

    def _claim(self, key: str) -> None:
        reward = self.history.claim_quest(key)
        if reward is not None:
            self.notice.setText(i18n.t("garden.earned", xp=reward.xp, coins=reward.coins))
            self.notice.show()
            self.rewarded.emit(reward)
        self.refresh()

    def refresh(self, day: str | None = None) -> None:
        count, claimed = self.history.garden.quests(day or day_of(datetime.now()))
        for key, goal in QUESTS.items():
            title, progress, meter, claim = self.rows[key]
            name = i18n.t(f"quest.{key}")
            title.setText(name)
            status = i18n.t("garden.quest_progress", count=min(count, goal), goal=goal)
            progress.setText(status)
            meter.setAccessibleName(f"{name} · {status}")
            meter.setRange(0, goal)
            meter.setValue(min(count, goal))
            claim.setEnabled(not self.debug and count >= goal and key not in claimed)
            label = i18n.t("garden.claimed" if key in claimed else "garden.claim")
            claim.setText(label)
            claim.setAccessibleName(f"{name} · {label}")

    def retranslate(self) -> None:
        super().retranslate()
        _polish(self)
        self.intro.setText(i18n.t("garden.debug" if self.debug else "garden.quest_intro"))
        self.notice.hide()
        self.refresh()


_BADGE_ICONS = (icons.EYE, icons.FLAME, icons.CHECK, icons.TIMER, icons.HOME, icons.LOCK)


class AchievementsPage(Page):
    def __init__(self, history: History) -> None:
        super().__init__("nav.achievements")
        self.history = history
        self.summary = _label()
        self.body.addWidget(self.summary)
        self.rows = {}
        for key, glyph in zip(ACHIEVEMENTS, _BADGE_ICONS):
            card, content = _card()
            row = QHBoxLayout()
            icon = QLabel()
            title, detail, status = _label(heading=True), _label(), _label()
            column = QVBoxLayout()
            for label in (title, detail, status):
                column.addWidget(label)
            row.addWidget(icon)
            row.addLayout(column, 1)
            content.addLayout(row)
            self.body.addWidget(card)
            self.rows[key] = glyph, icon, title, detail, status
        self.body.addStretch()
        self.retranslate()

    def refresh(self) -> None:
        unlocked = self.history.garden.achievements()
        self.summary.setText(i18n.t("garden.badge_summary", count=len(unlocked), total=len(ACHIEVEMENTS)))
        for key, (glyph, icon, title, detail, status) in self.rows.items():
            title.setText(i18n.t(f"badge.{key}"))
            detail.setText(i18n.t(f"badge.{key}_desc"))
            date = unlocked.get(key)
            status.setText(i18n.t("garden.unlocked_on", date=date[:10]) if date
                           else i18n.t("garden.locked"))
            pixmap = QPixmap(40, 40)
            pixmap.fill(Qt.GlobalColor.transparent)
            p = QPainter(pixmap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#e8cb8c") if date else theme.p().layer_alt)
            bounds = QRectF(1, 1, 38, 38)
            p.drawEllipse(bounds)
            icons.draw(p, glyph, bounds, QColor("#694b20") if date else theme.p().text_3, 18)
            p.end()
            icon.setPixmap(pixmap)

    def retranslate(self) -> None:
        super().retranslate()
        _polish(self)
        self.refresh()

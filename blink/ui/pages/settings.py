"""Every setting that lives in config.json, with a control instead of JSON.

Changes save immediately and take effect on the next tick — there is no
Apply button, because there is nothing here that needs one.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QWidget

from ... import i18n
from ...core.models import (Config, HUD_CORNERS, LONG_ENFORCEMENT,
                            SHORT_ENFORCEMENT)
from ...storage.config import CONFIG_PATH, save_config
from .. import theme
from ..autostart import is_enabled as autostart_enabled, set_enabled as set_autostart
from ..widgets import (ChoiceField, FlatButton, NumberField, SettingRow,
                       TextField, Toggle)
from .base import Page


class SettingsPage(Page):
    def __init__(self, config: Config, on_change: Callable[[], None],
                 parent: QWidget | None = None, *, persist: bool = True) -> None:
        super().__init__("nav.settings", parent)
        self.cfg = config
        self._on_change = on_change
        self._persist = persist
        self._rows: list[SettingRow] = []
        self._build()

    # -- wiring ------------------------------------------------------------

    def _row(self, title_key: str, desc_key: str, control: QWidget) -> SettingRow:
        row = SettingRow(i18n.t(title_key), i18n.t(desc_key), control)
        row.title_key, row.desc_key = title_key, desc_key
        self._rows.append(row)
        self.body.addWidget(row)
        return row

    def _save(self) -> None:
        if self._persist:
            save_config(self.cfg)
        self._on_change()

    def _minutes(self, get: Callable[[], int], put: Callable[[int], None],
                 low: int, high: int):
        box = NumberField(low, high, round(get() / 60), " " + i18n.t("unit.min"),
                          unit_key="unit.min")
        box.valueChanged.connect(lambda v: (put(v * 60), self._save()))
        return box

    def _seconds(self, get: Callable[[], int], put: Callable[[int], None],
                 low: int, high: int):
        box = NumberField(low, high, get(), " " + i18n.t("unit.sec"),
                          unit_key="unit.sec")
        box.valueChanged.connect(lambda v: (put(v), self._save()))
        return box

    def _toggle(self, get: Callable[[], bool], put: Callable[[bool], None]):
        switch = Toggle(get())
        switch.toggled.connect(lambda v: (put(v), self._save()))
        return switch

    def _enforcement_field(self, modes: tuple[str, ...], current: str,
                           put: Callable[[str], None]) -> ChoiceField:
        field = ChoiceField([(m, i18n.t(f"enforcement.{m}")) for m in modes], current)
        field.modes = modes
        field.changed.connect(lambda value: (put(value), self._save()))
        return field

    # -- the page ----------------------------------------------------------

    def _build(self) -> None:
        cfg = self.cfg
        short, long, idle, grace = cfg.short_break, cfg.long_break, cfg.idle, cfg.grace

        self.section("settings.eye_breaks")
        self._row("settings.work", "settings.work_desc",
                  self._minutes(lambda: short.work_sec,
                                lambda v: setattr(short, "work_sec", v), 1, 120))
        self._row("settings.break", "settings.break_desc",
                  self._seconds(lambda: short.break_sec,
                                lambda v: setattr(short, "break_sec", v), 5, 600))
        self._row("settings.toast_lead", "settings.toast_lead_desc",
                  self._seconds(lambda: short.toast_lead_sec,
                                lambda v: setattr(short, "toast_lead_sec", v), 0, 600))
        self.short_mode = self._enforcement_field(
            SHORT_ENFORCEMENT, short.enforcement,
            lambda value: setattr(short, "enforcement", value))
        self._row("settings.short_enforcement", "settings.short_enforcement_desc",
                  self.short_mode)
        self._row("settings.hold", "settings.hold_desc",
                  self._seconds(lambda: cfg.skip.hold_sec,
                                lambda v: setattr(cfg.skip, "hold_sec", v), 0, 30))

        self.section("settings.long_breaks")
        self._row("settings.long_enabled", "settings.long_enabled_desc",
                  self._toggle(lambda: long.enabled,
                               lambda v: setattr(long, "enabled", v)))
        self._row("settings.long_work", "settings.long_work_desc",
                  self._minutes(lambda: long.work_sec,
                                lambda v: setattr(long, "work_sec", v), 10, 480))
        self._row("settings.long_break", "settings.long_break_desc",
                  self._minutes(lambda: long.break_sec,
                                lambda v: setattr(long, "break_sec", v), 1, 60))
        self.long_mode = self._enforcement_field(
            LONG_ENFORCEMENT, long.enforcement,
            lambda value: setattr(long, "enforcement", value))
        self._row("settings.long_enforcement", "settings.long_enforcement_desc",
                  self.long_mode)

        self.section("settings.behaviour")
        self._row("settings.grace", "settings.grace_desc",
                  self._toggle(lambda: grace.enabled,
                               lambda v: setattr(grace, "enabled", v)))
        self._row("settings.idle_threshold", "settings.idle_threshold_desc",
                  self._seconds(lambda: idle.idle_threshold_sec,
                                lambda v: setattr(idle, "idle_threshold_sec", v),
                                10, 600))
        self._row("settings.reset_threshold", "settings.reset_threshold_desc",
                  self._minutes(lambda: idle.reset_threshold_sec,
                                lambda v: setattr(idle, "reset_threshold_sec", v),
                                1, 60))
        self._row("settings.sound", "settings.sound_desc",
                  self._toggle(lambda: cfg.sound.enabled,
                               lambda v: setattr(cfg.sound, "enabled", v)))
        self._row("settings.hud", "settings.hud_desc",
                  self._toggle(lambda: cfg.hud.enabled,
                               lambda v: setattr(cfg.hud, "enabled", v)))
        self.hud_corner = ChoiceField(
            [(c, i18n.t(f"corner.{c}")) for c in HUD_CORNERS], cfg.hud.corner)
        self.hud_corner.changed.connect(
            lambda value: (setattr(cfg.hud, "corner", value), self._save()))
        self._row("settings.hud_corner", "settings.hud_corner_desc",
                  self.hud_corner)

        self.section("settings.app")
        self.languages = ChoiceField(
            [(code, i18n.t(f"language.{code}")) for code in i18n.available()],
            cfg.language)
        self.languages.changed.connect(
            lambda value: (setattr(cfg, "language", value),
                           i18n.load(value), self._save()))
        self._row("settings.language", "settings.language_desc", self.languages)

        self.appearance = ChoiceField(
            [(m, i18n.t(f"appearance.{m}")) for m in ("system", "light", "dark")],
            cfg.appearance)
        self.appearance.changed.connect(
            lambda value: (setattr(cfg, "appearance", value),
                           theme.set_mode(value), self._save()))
        self._row("settings.appearance", "settings.appearance_desc", self.appearance)

        name = TextField(cfg.display_name, i18n.t("settings.name"))
        name.edited.connect(
            lambda value: (setattr(cfg, "display_name", value), self._save()))
        self._row("settings.name", "settings.name_desc", name)

        startup = Toggle(autostart_enabled())
        startup.toggled.connect(set_autostart)
        startup.setEnabled(self._persist)
        self._row("settings.autostart", "settings.autostart_desc", startup)

        open_config = FlatButton(i18n.t("settings.open_json"))
        open_config.clicked.connect(self._open_config)
        open_config.setEnabled(self._persist)
        self._row("settings.config_file", "settings.config_file_desc", open_config)
        self.body.addStretch(1)

    def _open_config(self) -> None:
        import os
        save_config(self.cfg)
        os.startfile(CONFIG_PATH)   # noqa: S606 - the user's own config file

    def retranslate(self) -> None:
        super().retranslate()
        for row in self._rows:
            row.title.setText(i18n.t(row.title_key))
            row.description.setText(i18n.t(row.desc_key))
            if isinstance(row.control, NumberField) and row.control.unit_key:
                row.control.suffix = " " + i18n.t(row.control.unit_key)
                row.control.update()
            elif isinstance(row.control, FlatButton):
                row.control.text = i18n.t("settings.open_json")
                row.control.update()
        for field in (self.short_mode, self.long_mode):
            field.set_options([(m, i18n.t(f"enforcement.{m}")) for m in field.modes],
                              field.current)
        self.languages.set_options(
            [(c, i18n.t(f"language.{c}")) for c in i18n.available()], self.cfg.language)
        self.hud_corner.set_options(
            [(c, i18n.t(f"corner.{c}")) for c in HUD_CORNERS], self.cfg.hud.corner)
        self.appearance.set_options(
            [(m, i18n.t(f"appearance.{m}")) for m in ("system", "light", "dark")],
            self.cfg.appearance)

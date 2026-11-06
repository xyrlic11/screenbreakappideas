"""config.json is hand-edited, so it has to survive being edited badly."""

from __future__ import annotations

import json

from blink.core.models import Config, LOCK, OVERLAY, POPUP
from blink.storage import config as config_module


def read_back(raw: dict) -> Config:
    return config_module._from_dict(Config(), raw, prefix="")


def test_an_empty_file_gives_the_defaults():
    cfg = read_back({})
    assert cfg.short_break.work_sec == 1200
    assert cfg.long_break.enforcement == OVERLAY   # locking stays opt-in
    assert cfg.language == "th"


def test_partial_files_keep_the_rest_of_the_defaults():
    cfg = read_back({"short_break": {"work_sec": 900}})
    assert cfg.short_break.work_sec == 900
    assert cfg.short_break.break_sec == 20


def test_silly_values_are_clamped_not_rejected():
    cfg = read_back({"short_break": {"work_sec": 3, "break_sec": 99999}})
    assert cfg.short_break.work_sec == 60      # a 3 second interval is a typo
    assert cfg.short_break.break_sec == 600


def test_wrong_types_are_ignored_rather_than_fatal():
    cfg = read_back({"short_break": {"work_sec": "twenty minutes"}, "grace": "yes please"})
    assert cfg.short_break.work_sec == 1200
    assert cfg.grace.enabled is True


def test_booleans_are_not_clamped_into_numbers():
    cfg = read_back({"long_break": {"enabled": False}, "sound": {"enabled": True}})
    assert cfg.long_break.enabled is False
    assert cfg.sound.enabled is True


def test_round_trip_is_stable():
    original = read_back({"short_break": {"work_sec": 900}, "language": "en"})
    as_dict = config_module._to_dict(original)
    assert json.loads(json.dumps(as_dict)) == as_dict
    assert read_back(as_dict) == original


def test_debug_preset_shrinks_everything_but_keeps_the_shape():
    debug = Config().debug_preset()
    assert debug.short_break.work_sec == 20
    assert debug.short_break.toast_lead_sec < debug.short_break.work_sec
    assert debug.short_break.edge_lead_sec < debug.short_break.toast_lead_sec
    assert debug.long_break.work_sec == 120
    assert debug.long_break.enforcement == OVERLAY   # never locks by surprise


# --------------------------------------------------------------------------
# Enforcement mode
# --------------------------------------------------------------------------


def migrate(raw: dict) -> Config:
    return config_module._from_dict(Config(), config_module._migrate(raw), prefix="")


def test_the_old_real_lock_flag_still_means_what_it_meant():
    """Anyone upgrading has real_lock in their config; it must not be lost."""
    assert migrate({"long_break": {"real_lock": True}}).long_break.enforcement == LOCK
    assert migrate({"long_break": {"real_lock": False}}).long_break.enforcement == OVERLAY


def test_migration_does_not_overwrite_a_deliberate_choice():
    cfg = migrate({"long_break": {"real_lock": True, "enforcement": POPUP}})
    assert cfg.long_break.enforcement == POPUP


def test_an_unknown_mode_falls_back_to_the_default_not_the_harshest():
    """A typo must never be what turns screen locking on."""
    assert read_back({"short_break": {"enforcement": "yolo"}}).short_break.enforcement == OVERLAY
    assert read_back({"long_break": {"enforcement": "yolo"}}).long_break.enforcement == OVERLAY


def test_short_breaks_cannot_be_set_to_lock_the_screen():
    """Locking for a 20 second break costs more in retyping than it gives."""
    assert read_back({"short_break": {"enforcement": LOCK}}).short_break.enforcement == OVERLAY


def test_valid_modes_are_kept():
    assert read_back({"short_break": {"enforcement": POPUP}}).short_break.enforcement == POPUP
    assert read_back({"long_break": {"enforcement": LOCK}}).long_break.enforcement == LOCK


def test_appearance_is_policed_too():
    assert read_back({"appearance": "neon"}).appearance == "system"
    assert read_back({"appearance": "dark"}).appearance == "dark"

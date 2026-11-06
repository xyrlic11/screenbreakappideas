"""Guards against the classic two-language bug: a key that only exists in one."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from blink import i18n

ROOT = Path(__file__).resolve().parents[1]
LOCALE_DIR = ROOT / "blink" / "locales"

# Matches i18n.t("some.key") and t("some.key") in the source.
_CALL = re.compile(r"\bt\(\s*\"([a-z0-9_]+(?:\.[a-z0-9_]+)+)\"")


def locale_files() -> list[Path]:
    return sorted(LOCALE_DIR.glob("*.json"))


def test_both_languages_exist():
    assert {p.stem for p in locale_files()} == {"th", "en"}


def test_every_language_defines_exactly_the_same_keys():
    per_file = {p.stem: set(json.loads(p.read_text(encoding="utf-8"))) for p in locale_files()}
    reference = per_file["en"]
    for name, keys in per_file.items():
        assert keys == reference, (
            f"{name}.json differs: missing {sorted(reference - keys)}, "
            f"extra {sorted(keys - reference)}"
        )


def test_every_key_used_in_the_code_is_translated():
    strings = json.loads((LOCALE_DIR / "en.json").read_text(encoding="utf-8"))
    missing: set[str] = set()
    for path in (ROOT / "blink").rglob("*.py"):
        for key in _CALL.findall(path.read_text(encoding="utf-8")):
            if key not in strings:
                missing.add(f"{path.name}: {key}")
    assert not missing, f"untranslated keys in use: {sorted(missing)}"


@pytest.mark.parametrize("language", ["th", "en"])
def test_placeholders_survive_formatting(language):
    i18n.load(language)
    assert "{time}" not in i18n.t("tray.counting", time="5 min")
    assert "{seconds}" not in i18n.t("longwarn.title", seconds=42)
    assert "{count}" not in i18n.t("longwarn.snooze", minutes=5, count=2)


def test_translations_use_the_same_placeholders():
    """A translator dropping or adding a {slot} leaves it raw on screen.

    t() swallows the KeyError so the app cannot crash, which means nothing
    else would catch this.
    """
    per_file = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in locale_files()}
    reference = per_file["en"]
    slots = re.compile(r"\{(\w+)\}")

    for name, strings in per_file.items():
        for key, text in strings.items():
            assert set(slots.findall(text)) == set(slots.findall(reference[key])), (
                f"{name}.json '{key}' has placeholders {sorted(set(slots.findall(text)))}, "
                f"en.json has {sorted(set(slots.findall(reference[key])))}"
            )


def test_unknown_key_shows_itself_rather_than_crashing():
    i18n.load("th")
    assert i18n.t("nope.not.here") == "nope.not.here"


def test_unknown_language_falls_back_to_english():
    assert i18n.load("klingon") == "en"
    i18n.load("th")


def test_human_time_switches_units():
    i18n.load("en")
    assert i18n.human_time(45) == "45s"
    assert i18n.human_time(300) == "5 min"
    assert i18n.human_time(3900) == "1h 5m"

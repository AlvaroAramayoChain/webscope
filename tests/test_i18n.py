import re
import string
from pathlib import Path

import pytest

from webscope.i18n import MESSAGES, SUPPORTED_LANGS, language_name, normalize_lang, t

SRC = Path(__file__).parent.parent / "src" / "webscope"


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_language_has_the_same_keys() -> None:
    reference = set(MESSAGES["en"])
    for lang in SUPPORTED_LANGS:
        assert set(MESSAGES[lang]) == reference, f"claves distintas en {lang}"


def test_placeholders_match_between_languages() -> None:
    for key, text in MESSAGES["en"].items():
        for lang in SUPPORTED_LANGS:
            assert placeholders(MESSAGES[lang][key]) == placeholders(text), f"{lang}:{key}"


def test_translation_and_formatting() -> None:
    assert t("label.topic", "es") == "De qué trata"
    assert t("label.topic", "en") == "About"
    assert t("pages.at_least", "es", count=50, source="x") == "al menos 50 (vía x)"


def test_fallbacks_never_break() -> None:
    assert t("label.topic", "fr") == "About"
    assert t("does.not.exist", "es") == "does.not.exist"
    assert t("pages.exact", "en", wrong=1) == "{count} (via {source})"


def test_messages_are_read_only() -> None:
    with pytest.raises(TypeError):
        MESSAGES["es"]["label.topic"] = "x"  # type: ignore[index]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("ES", "es"), ("en-US", "en"), ("es_AR", "es"), ("fr", None), ("", None), (None, None)],
)
def test_normalize_lang(raw: str | None, expected: str | None) -> None:
    assert normalize_lang(raw) == expected


def test_language_names() -> None:
    assert language_name("es") == "Español"
    assert language_name("en") == "English"


def _codes(pattern: str) -> set[str]:
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        found |= set(re.findall(pattern, path.read_text(encoding="utf-8")))
    return found


def test_all_static_keys_used_in_code_exist() -> None:
    keys = _codes(r"""\bt\(\s*["']([a-z_]+\.[a-z_.]+)["']""")
    assert keys, "no se encontraron claves"
    assert keys <= set(MESSAGES["en"])


def test_all_signal_and_event_codes_are_translated() -> None:
    signals = _codes(r"""Signal\(\s*["'](\w+)["']""")
    events = _codes(r"""on_event\(\s*["'](\w+)["']""")
    assert signals and events
    for code in signals:
        assert f"signal.{code}" in MESSAGES["en"]
    for code in events:
        assert f"event.{code}" in MESSAGES["en"]

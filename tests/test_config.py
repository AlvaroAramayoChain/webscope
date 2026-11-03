import json
from pathlib import Path

import pytest

from webscope import config


def test_config_dir_uses_env_override(isolated_env: Path) -> None:
    assert config.config_dir() == isolated_env
    assert config.config_path() == isolated_env / "config.json"


def test_default_config_dir_by_platform(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WEBSCOPE_CONFIG_DIR")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    expected = tmp_path / ("appdata" if config.os.name == "nt" else "xdg") / "webscope"
    assert config.config_dir() == expected


def test_save_and_load_roundtrip(isolated_env: Path) -> None:
    assert config.load_language() is None
    assert config.save_language("en") is True
    assert config.load_language() == "en"
    assert json.loads((isolated_env / "config.json").read_text())["lang"] == "en"


def test_corrupt_file_is_ignored(isolated_env: Path) -> None:
    isolated_env.mkdir(parents=True)
    (isolated_env / "config.json").write_text("{not json", encoding="utf-8")
    assert config.load_language() is None
    assert config.save_language("es") is True
    assert config.load_language() == "es"


@pytest.mark.parametrize("content", ['["es"]', '{"lang": 3}', '{"lang": "klingon"}'])
def test_invalid_values_are_ignored(isolated_env: Path, content: str) -> None:
    isolated_env.mkdir(parents=True)
    (isolated_env / "config.json").write_text(content, encoding="utf-8")
    assert config.load_language() is None


def test_unwritable_location_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setenv("WEBSCOPE_CONFIG_DIR", str(blocker / "webscope"))
    assert config.save_language("es") is False
    assert config.load_language() is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("es_AR.UTF-8", "es"),
        ("es", "es"),
        ("en_US.UTF-8", "en"),
        ("de_DE", "en"),
        ("Spanish_Spain", "es"),
    ],
)
def test_system_language(monkeypatch: pytest.MonkeyPatch, value: str, expected: str) -> None:
    monkeypatch.setenv("LANG", value)
    assert config.system_language() == expected


def test_system_language_defaults_to_english(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANG", "C")
    monkeypatch.setattr(config.locale, "getlocale", lambda: (None, None))
    assert config.system_language() == "en"

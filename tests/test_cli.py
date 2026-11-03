import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest
import requests
import responses
from typer.testing import CliRunner

from webscope import __version__, cli, config

URL = "zapasrun.example"
SPANISH_LABEL = "De qué trata"
ENGLISH_LABEL = "About"
MENU = "Select language / Elegí idioma"


def invoke(args: list[str], input: str | None = None, help_lang: str = "en"):
    return CliRunner().invoke(cli.build_app(help_lang), args, input=input)


@pytest.fixture
def interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_interactive", lambda: True)


@pytest.fixture
def non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_interactive", lambda: False)


# --- Análisis y salida --------------------------------------------------------------


@pytest.mark.usefixtures("wordpress_site", "non_interactive")
def test_analyze_in_english_assumes_https() -> None:
    result = invoke([URL, "--lang", "en"])
    assert result.exit_code == 0, result.output
    for expected in (
        "🔎 zapasrun.example",
        ENGLISH_LABEL,
        "Website",
        "~3 (via sitemap.xml)",
        "WordPress",
        "zapatillas",
    ):
        assert expected in result.stdout


@pytest.mark.usefixtures("wordpress_site", "non_interactive")
def test_analyze_in_spanish() -> None:
    result = invoke([URL, "--lang", "es"])
    assert result.exit_code == 0, result.output
    assert SPANISH_LABEL in result.stdout
    assert "Sitio web (confianza: alta)" in result.stdout


@pytest.mark.usefixtures("wordpress_site", "non_interactive")
def test_verbose_shows_events_and_signals() -> None:
    result = invoke([URL, "--lang", "es", "--verbose"])
    assert result.exit_code == 0
    assert "Señales" in result.stdout
    assert "robots.txt encontrado" in result.stderr


@pytest.mark.usefixtures("wordpress_site", "interactive")
@pytest.mark.parametrize("lang", ["es", "en"])
def test_json_is_clean_english_keys_and_never_asks(lang: str, isolated_env: Path) -> None:
    result = invoke([URL, "--json", "--lang", lang])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ui_lang"] == lang
    assert data["site_lang"] == "es"
    assert data["pages"] == {"count": 3, "source": "sitemap", "at_least": False}
    assert {"summary", "site_type", "technologies", "keywords"} <= data.keys()
    assert MENU not in result.output


@pytest.mark.usefixtures("wordpress_site", "interactive")
def test_json_without_lang_uses_system_and_does_not_prompt(
    monkeypatch: pytest.MonkeyPatch, isolated_env: Path
) -> None:
    monkeypatch.setenv("LANG", "es_AR.UTF-8")
    result = invoke([URL, "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ui_lang"] == "es"
    assert MENU not in result.output
    assert not (isolated_env / "config.json").exists()


@pytest.mark.usefixtures("wordpress_site", "non_interactive")
def test_no_color_has_no_ansi_codes() -> None:
    result = invoke([URL, "--lang", "en", "--no-color"])
    assert "\x1b[" not in result.stdout


def test_make_console_respects_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    assert cli.make_console(no_color=True).color_system is None
    monkeypatch.setenv("NO_COLOR", "1")
    assert cli.make_console(no_color=False).color_system is None
    assert cli.make_console(no_color=False).width <= 80


# --- Prioridad de idioma: --lang > guardado > menú > sistema ------------------------


@pytest.mark.usefixtures("wordpress_site", "interactive")
def test_first_interactive_run_shows_menu_and_saves(isolated_env: Path) -> None:
    result = invoke([URL], input="2\n")
    assert result.exit_code == 0, result.output
    assert MENU in result.stderr
    assert "1) Español" in result.stderr and "2) English" in result.stderr
    assert ENGLISH_LABEL in result.stdout
    assert config.load_language() == "en"


@pytest.mark.usefixtures("wordpress_site", "interactive")
def test_saved_language_is_reused_without_menu() -> None:
    config.save_language("es")
    result = invoke([URL])
    assert result.exit_code == 0
    assert MENU not in result.output
    assert SPANISH_LABEL in result.stdout


@pytest.mark.usefixtures("wordpress_site", "interactive")
def test_lang_flag_wins_and_does_not_change_saved() -> None:
    config.save_language("es")
    result = invoke([URL, "--lang", "en"])
    assert ENGLISH_LABEL in result.stdout
    assert MENU not in result.output
    assert config.load_language() == "es"


@pytest.mark.usefixtures("wordpress_site", "interactive")
def test_lang_flag_skips_menu_on_first_run(isolated_env: Path) -> None:
    result = invoke([URL, "--lang", "es"])
    assert MENU not in result.output
    assert not (isolated_env / "config.json").exists()


@pytest.mark.usefixtures("wordpress_site", "non_interactive")
@pytest.mark.parametrize(
    ("system", "label"), [("es_ES.UTF-8", SPANISH_LABEL), ("de_DE.UTF-8", ENGLISH_LABEL)]
)
def test_non_interactive_uses_system_language(
    monkeypatch: pytest.MonkeyPatch, isolated_env: Path, system: str, label: str
) -> None:
    monkeypatch.setenv("LANG", system)
    result = invoke([URL])
    assert result.exit_code == 0
    assert MENU not in result.output
    assert label in result.stdout
    assert not (isolated_env / "config.json").exists()


@pytest.mark.usefixtures("wordpress_site", "non_interactive")
def test_saved_language_beats_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANG", "es_ES.UTF-8")
    config.save_language("en")
    assert ENGLISH_LABEL in invoke([URL]).stdout


@pytest.mark.parametrize("answer", ["1", "es", "ES", " Es "])
def test_menu_accepts_spanish(answer: str, interactive: None) -> None:
    result = invoke(["--change-lang"], input=f"{answer}\n")
    assert result.exit_code == 0
    assert config.load_language() == "es"
    assert "Idioma guardado: Español" in result.stderr


@pytest.mark.parametrize("answer", ["2", "en", "EN"])
def test_menu_accepts_english(answer: str, interactive: None) -> None:
    invoke(["--change-lang"], input=f"{answer}\n")
    assert config.load_language() == "en"


@pytest.mark.usefixtures("interactive")
def test_menu_retries_after_invalid_input() -> None:
    result = invoke(["--change-lang"], input="x\n9\n2\n")
    assert result.stderr.count(MENU) == 3
    assert result.stderr.count("Opción inválida / Invalid option") == 2
    assert config.load_language() == "en"


@pytest.mark.usefixtures("interactive")
def test_menu_falls_back_to_spanish_after_three_failures() -> None:
    result = invoke(["--change-lang"], input="x\ny\nz\nen\n")
    assert result.exit_code == 0
    assert result.stderr.count(MENU) == 3
    assert config.load_language() == "es"


@pytest.mark.usefixtures("interactive")
def test_menu_handles_end_of_input() -> None:
    result = invoke(["--change-lang"], input="")
    assert result.exit_code == 0
    assert config.load_language() == "es"


@pytest.mark.usefixtures("wordpress_site", "interactive")
def test_change_lang_with_url_analyzes_in_new_language() -> None:
    config.save_language("es")
    result = invoke(["--change-lang", URL], input="2\n")
    assert result.exit_code == 0
    assert ENGLISH_LABEL in result.stdout
    assert config.load_language() == "en"


@pytest.mark.usefixtures("wordpress_site", "interactive")
def test_corrupt_config_does_not_break(isolated_env: Path) -> None:
    isolated_env.mkdir(parents=True)
    (isolated_env / "config.json").write_text("{{{", encoding="utf-8")
    result = invoke([URL], input="1\n")
    assert result.exit_code == 0
    assert SPANISH_LABEL in result.stdout
    assert config.load_language() == "es"


@pytest.mark.usefixtures("wordpress_site", "interactive")
def test_unwritable_config_still_runs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("WEBSCOPE_CONFIG_DIR", str(blocker / "sub"))
    result = invoke([URL], input="2\n")
    assert result.exit_code == 0
    assert ENGLISH_LABEL in result.stdout
    assert "Could not save the preference" in result.stderr


# --- Errores y exit codes -----------------------------------------------------------


@pytest.mark.usefixtures("non_interactive")
def test_missing_url_is_usage_error() -> None:
    result = invoke(["--lang", "es"])
    assert result.exit_code == 2
    assert "Falta la URL" in result.stderr


@pytest.mark.usefixtures("non_interactive")
def test_invalid_lang_is_usage_error() -> None:
    result = invoke([URL, "--lang", "fr"])
    assert result.exit_code == 2
    assert "'fr'" in result.stderr


@pytest.mark.usefixtures("non_interactive")
def test_invalid_max_pages_is_usage_error() -> None:
    assert invoke([URL, "--max-pages", "0", "--lang", "en"]).exit_code == 2


@pytest.mark.usefixtures("non_interactive")
def test_unknown_option_is_usage_error() -> None:
    assert invoke([URL, "--nope"]).exit_code == 2


@pytest.mark.usefixtures("non_interactive")
@pytest.mark.parametrize(
    ("lang", "expected"),
    [("es", "No se pudo resolver el dominio"), ("en", "Could not resolve the domain")],
)
def test_dns_error_is_translated_without_traceback(
    mocked: responses.RequestsMock, lang: str, expected: str
) -> None:
    error = requests.exceptions.ConnectionError(socket.gaierror(-2, "Name or service not known"))
    mocked.get("https://nope.example/", body=error)
    result = invoke(["nope.example", "--lang", lang])
    assert result.exit_code == 1
    assert expected in result.stderr
    assert "Traceback" not in result.output


@pytest.mark.usefixtures("non_interactive")
def test_invalid_url_exits_with_1() -> None:
    result = invoke(["http://", "--lang", "en"])
    assert result.exit_code == 1
    assert "Invalid URL" in result.stderr


@pytest.mark.usefixtures("non_interactive")
def test_http_and_not_html_errors(mocked: responses.RequestsMock) -> None:
    mocked.get("https://down.example/", status=503)
    mocked.get("https://api.example/", json={"ok": True})
    down = invoke(["down.example", "--lang", "en"])
    api = invoke(["api.example", "--lang", "es"])
    assert (down.exit_code, api.exit_code) == (1, 1)
    assert "503" in down.stderr
    assert "no devuelve una página HTML" in api.stderr


@pytest.mark.usefixtures("non_interactive")
def test_unexpected_errors_are_friendly(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cli, "analyze", boom)
    result = invoke([URL, "--lang", "en"])
    assert result.exit_code == 1
    assert "Unexpected error: kaboom" in result.stderr
    assert "Traceback" not in result.output


# --- Ayuda y versión ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("lang", "expected"),
    [("es", "Muestra esta ayuda y sale"), ("en", "Show this help and exit")],
)
def test_help_is_translated(lang: str, expected: str) -> None:
    result = invoke(["--help"], help_lang=lang)
    assert result.exit_code == 0
    assert expected in result.stdout
    assert "--change-lang" in result.stdout


def test_help_language_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANG", "es_AR.UTF-8")
    assert cli.help_language(["--help"]) == "es"
    assert cli.help_language(["--lang", "en", "--help"]) == "en"
    assert cli.help_language(["--lang=en", "--help"]) == "en"
    config.save_language("en")
    assert cli.help_language(["--help"]) == "en"
    assert cli.help_language(["--lang", "es", "--help"]) == "es"


def test_version() -> None:
    result = invoke(["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_python_dash_m_entry_point() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "webscope", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0
    assert f"webscope {__version__}" in completed.stdout

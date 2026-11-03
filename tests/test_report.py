import io
import json

import pytest
from rich.console import Console

from webscope.fetcher import FetchError
from webscope.models import AnalysisResult, PageCount, Signal, SiteTypeResult, Technology
from webscope.report import (
    format_error,
    format_pages,
    format_site_type,
    format_technologies,
    render,
    to_dict,
    to_json,
)


def make_result(**overrides: object) -> AnalysisResult:
    data: dict[str, object] = {
        "url": "https://ejemplo.com",
        "final_url": "https://ejemplo.com/",
        "domain": "ejemplo.com",
        "summary": "Tienda online de zapatillas deportivas",
        "site_type": SiteTypeResult(
            kind="site",
            confidence="high",
            app_score=1,
            site_score=7,
            signals=(Signal("rich_text", "site", 3), Signal("manifest", "app", 1)),
        ),
        "pages": PageCount(48, "sitemap"),
        "technologies": (
            Technology("HTML", "language"),
            Technology("CSS", "language"),
            Technology("jQuery", "library"),
            Technology("WordPress", "cms"),
        ),
        "keywords": ("zapatillas", "running"),
        "site_lang": "es",
        "server": "nginx",
    }
    data.update(overrides)
    return AnalysisResult(**data)  # type: ignore[arg-type]


def render_text(result: AnalysisResult, lang: str, verbose: bool = False) -> str:
    buffer = io.StringIO()
    console = Console(file=buffer, width=80, color_system=None)
    render(result, lang, console, verbose=verbose)
    return buffer.getvalue()


def test_render_in_spanish() -> None:
    text = render_text(make_result(), "es")
    for expected in (
        "🔎 ejemplo.com",
        "De qué trata",
        "Tipo",
        "Páginas",
        "Tecnologías",
        "Palabras clave",
    ):
        assert expected in text
    assert "Sitio web (confianza: alta)" in text
    assert "~48 (vía sitemap.xml)" in text
    assert "HTML, CSS · WordPress · jQuery" in text
    assert "zapatillas, running" in text


def test_render_in_english() -> None:
    text = render_text(make_result(), "en")
    for expected in ("About", "Type", "Pages", "Technologies", "Keywords"):
        assert expected in text
    assert "Website (confidence: high)" in text
    assert "~48 (via sitemap.xml)" in text
    # El resumen queda en el idioma original de la web.
    assert "Tienda online de zapatillas" in text


def test_render_fits_80_columns() -> None:
    long_summary = "palabra " * 40
    text = render_text(make_result(summary=long_summary), "es", verbose=True)
    assert max(len(line) for line in text.splitlines()) <= 80


@pytest.mark.parametrize("lang", ["es", "en"])
def test_verbose_shows_signals(lang: str) -> None:
    text = render_text(make_result(), lang, verbose=True)
    assert "+3" in text and "+1" in text
    assert "nginx" in text
    assert ("Señales" if lang == "es" else "Signals") in text


def test_web_content_is_not_interpreted_as_markup() -> None:
    text = render_text(make_result(summary="[bold red]hola[/] mundo"), "es")
    assert "[bold red]hola[/] mundo" in text


def test_empty_values_are_translated() -> None:
    text = render_text(make_result(summary="", technologies=(), keywords=()), "es")
    assert "sin descripción disponible" in text
    assert "no se detectaron" in text
    assert "texto insuficiente" in text


@pytest.mark.parametrize(
    ("pages", "lang", "expected"),
    [
        (PageCount(48, "sitemap"), "es", "~48 (vía sitemap.xml)"),
        (PageCount(1200, "sitemap", at_least=True), "en", "at least 1200 (via sitemap.xml)"),
        (PageCount(7, "crawl"), "es", "7 (vía rastreo de links)"),
        (PageCount(50, "crawl", at_least=True), "es", "al menos 50 (vía rastreo de links)"),
        (PageCount(50, "crawl", at_least=True), "en", "at least 50 (via link crawl)"),
    ],
)
def test_format_pages(pages: PageCount, lang: str, expected: str) -> None:
    assert format_pages(pages, lang) == expected


def test_format_site_type_app() -> None:
    result = SiteTypeResult(kind="app", confidence="medium", app_score=5, site_score=2)
    assert format_site_type(result, "es") == "App web (confianza: media)"
    assert format_site_type(result, "en") == "Web app (confidence: medium)"


def test_format_technologies_groups_in_category_order() -> None:
    techs = (
        Technology("nginx", "server"),
        Technology("React", "framework"),
        Technology("HTML", "language"),
    )
    assert format_technologies(techs, "en") == "HTML · React · nginx"


def test_format_error_is_translated() -> None:
    error = FetchError("dns", host="nope.example")
    assert "nope.example" in format_error(error, "es")
    assert format_error(error, "es") != format_error(error, "en")


def test_json_keys_are_english_in_both_languages() -> None:
    result = make_result()
    spanish, english = to_dict(result, "es"), to_dict(result, "en")
    assert spanish.keys() == english.keys()
    assert spanish["site_type"].keys() == english["site_type"].keys()
    assert spanish["ui_lang"] == "es" and english["ui_lang"] == "en"
    assert spanish["site_lang"] == english["site_lang"] == "es"
    # Los códigos no se traducen.
    assert spanish["site_type"]["type"] == english["site_type"]["type"] == "site"
    assert spanish["site_type"]["confidence"] == "high"
    assert spanish["pages"] == {"count": 48, "source": "sitemap", "at_least": False}


def test_to_json_is_valid_and_keeps_accents() -> None:
    text = to_json(make_result(summary="Envío gratis"), "es")
    assert json.loads(text)["summary"] == "Envío gratis"
    assert "Envío" in text

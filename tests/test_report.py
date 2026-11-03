import io
import json
import re

import pytest
from rich.console import Console

from webscope import __version__
from webscope.fetcher import FetchError
from webscope.i18n import t
from webscope.models import AnalysisResult, PageCount, Signal, SiteTypeResult, Technology
from webscope.report import (
    format_error,
    format_pages,
    format_site_type,
    format_summary,
    format_technologies,
    render,
    to_dict,
    to_json,
    to_markdown,
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


# --- v2: bloques, Markdown y JSON ---------------------------------------------------


@pytest.fixture
def full_result(full_site: object) -> AnalysisResult:
    from webscope.core import analyze

    return analyze("zapasrun.example")


@pytest.mark.parametrize(
    ("lang", "titles"),
    [
        ("es", ("GENERAL", "INFRAESTRUCTURA", "TLS", "SEGURIDAD VISIBLE", "HALLAZGOS")),
        ("en", ("GENERAL", "INFRASTRUCTURE", "TLS", "VISIBLE SECURITY", "FINDINGS")),
    ],
)
def test_full_report_has_every_block(full_result: AnalysisResult, lang: str, titles: tuple) -> None:
    text = render_text(full_result, lang)
    for title in titles:
        assert title in text
    assert "AS13335 Cloudflare, Inc. · US" in text
    assert "Let's Encrypt (R11)" in text
    assert ("Reconocimiento pasivo" if lang == "es" else "Passive reconnaissance") in text


def test_findings_use_translated_severity(full_result: AnalysisResult) -> None:
    assert "[MEDIO] Falta Content-Security-Policy" in render_text(full_result, "es")
    assert "[MEDIUM] Missing Content-Security-Policy" in render_text(full_result, "en")


def test_verbose_shows_evidence_and_recommendation(full_result: AnalysisResult) -> None:
    text = render_text(full_result, "en", verbose=True)
    assert "evidence: Content-Security-Policy: -" in text
    assert "→ Define a restrictive CSP" in text
    assert "HDR-CSP-MISSING" in text


def test_report_fits_100_columns(full_result: AnalysisResult) -> None:
    buffer = io.StringIO()
    render(full_result, "es", Console(file=buffer, width=100, color_system=None), verbose=True)
    assert max(len(line) for line in buffer.getvalue().splitlines()) <= 100


def test_unavailable_block_shows_reason() -> None:
    result = make_result(unavailable={"tls": "tls_timeout"})
    assert "no disponible (TLS sin respuesta)" in render_text(result, "es")


def test_brief_only_shows_general(full_result: AnalysisResult) -> None:
    from dataclasses import replace

    text = render_text(replace(full_result, brief=True), "es")
    assert "GENERAL" in text and "INFRAESTRUCTURA" not in text and "HALLAZGOS" not in text


def test_summary_has_category_prefix() -> None:
    from webscope.models import CategoryResult, TopicResult

    topic = TopicResult("Zapatillas con envío gratis", CategoryResult("ecommerce", "high"))
    result = make_result(summary="Zapatillas con envío gratis", topic=topic)
    assert (
        format_summary(result, "es") == "Tienda online (e-commerce) — Zapatillas con envío gratis"
    )
    assert format_summary(result, "en").startswith("Online store (e-commerce) — ")


def test_undetermined_summary_keeps_the_format() -> None:
    from webscope.models import CategoryResult, TopicResult

    unknown = TopicResult("Algo", CategoryResult("unknown", "low"))
    result = make_result(summary="Algo", topic=unknown)
    assert format_summary(result, "es") == "Indeterminada — Algo"
    assert format_summary(result, "en") == "Undetermined — Algo"
    empty = make_result(summary="", topic=unknown)
    assert format_summary(empty, "es") == "Indeterminada — sin descripción disponible"


@pytest.mark.parametrize("code", ["unknown", "ecommerce"])
def test_summary_is_clipped_to_200_chars(code: str) -> None:
    from webscope.models import CategoryResult, TopicResult

    long_text = "palabra " * 60
    topic = TopicResult(long_text, CategoryResult(code, "low"))
    summary = format_summary(make_result(summary=long_text, topic=topic), "es")
    assert len(summary) <= 200
    assert summary.endswith("…")
    assert " — palabra" in summary


def test_summary_without_topic_is_only_the_description() -> None:
    # Resultados sin clasificar (p. ej. construidos a mano) no inventan una categoría.
    assert format_summary(make_result(summary="Algo"), "en") == "Algo"


@pytest.mark.parametrize("lang", ["es", "en"])
def test_markdown_report(full_result: AnalysisResult, lang: str) -> None:
    md = to_markdown(full_result, lang)
    assert md.startswith("# 🔎 zapasrun.example")
    assert ("## INFRAESTRUCTURA" if lang == "es" else "## INFRASTRUCTURE") in md
    assert "|---|---|" in md
    assert "`HDR-CSP-MISSING`" in md
    assert md.rstrip().endswith(t("notice.passive", lang))


def test_markdown_escapes_pipes() -> None:
    md = to_markdown(make_result(summary="a | b"), "es")
    assert r"a \| b" in md


def _keys(value: object, path: str = "") -> set[str]:
    if isinstance(value, dict):
        found = set()
        for key, child in value.items():
            found.add(key)
            found |= _keys(child, f"{path}.{key}")
        return found
    if isinstance(value, list):
        return set().union(*(_keys(item, path) for item in value)) if value else set()
    return set()


def test_json_schema_v2(full_result: AnalysisResult) -> None:
    data = json.loads(to_json(full_result, "es"))
    assert data["schema_version"] == "2.0"
    assert data["webscope_version"] == __version__
    for section in ("general", "infrastructure", "tls", "security", "findings", "unavailable"):
        assert section in data
    finding = data["findings"][0]
    assert set(finding) == {"id", "severity", "title", "evidence", "recommendation"}
    assert data["infrastructure"]["asn"]["104.16.1.1"]["asn"] == 13335
    assert data["general"]["technologies"][0].keys() == {"name", "category", "version"}


def test_json_keys_are_english_and_identical_between_languages(full_result: AnalysisResult) -> None:
    spanish, english = to_dict(full_result, "es"), to_dict(full_result, "en")
    keys_es, keys_en = _keys(spanish), _keys(english)
    # Las claves de nivel de datos de usuario (IPs, nombres de header) se excluyen.
    assert keys_es == keys_en
    words = {k for k in keys_es if re.fullmatch(r"[a-z_]+", k)}
    assert not words & {"resumen", "categoria", "hallazgos", "infraestructura", "seguridad"}
    assert spanish["findings"][0]["id"] == english["findings"][0]["id"]
    assert spanish["findings"][0]["title"] != english["findings"][0]["title"]

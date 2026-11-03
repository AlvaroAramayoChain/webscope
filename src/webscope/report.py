"""Presentación del resultado: texto con ``rich`` (traducido) o JSON estable.

Es el único lugar donde los códigos de los analizadores (``site``, ``high``,
``sitemap``...) se convierten en texto del idioma de la interfaz.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from webscope import __version__
from webscope.analyzers.tech import CATEGORY_ORDER
from webscope.fetcher import FetchError
from webscope.i18n import t
from webscope.models import AnalysisResult, PageCount, SiteTypeResult, Technology

MAX_WIDTH = 80
LABEL_STYLE = "bold cyan"


def format_pages(pages: PageCount, lang: str) -> str:
    """``~48 (vía sitemap.xml)``, ``al menos 50 (vía rastreo de links)``..."""
    source = t(f"source.{pages.source}", lang)
    if pages.at_least:
        key = "pages.at_least"
    else:
        key = "pages.approx" if pages.source == "sitemap" else "pages.exact"
    return t(key, lang, count=pages.count, source=source)


def format_site_type(site_type: SiteTypeResult, lang: str) -> str:
    """``Sitio web (confianza: alta)``."""
    return t(
        "type.value",
        lang,
        kind=t(f"type.{site_type.kind}", lang),
        confidence=t(f"confidence.{site_type.confidence}", lang),
    )


def format_technologies(technologies: tuple[Technology, ...], lang: str) -> str:
    """Tecnologías agrupadas por categoría: ``HTML, CSS · WordPress · jQuery``."""
    groups = [
        ", ".join(tech.name for tech in technologies if tech.category == category)
        for category in CATEGORY_ORDER
    ]
    return " · ".join(group for group in groups if group) or t("tech.none", lang)


def format_error(error: FetchError, lang: str) -> str:
    """Mensaje de error traducido, sin stack trace."""
    return t(f"error.{error.code}", lang, **error.params)


def format_event(code: str, lang: str, **params: object) -> str:
    """Texto de un evento de progreso del crawler (para ``--verbose``)."""
    return t(f"event.{code}", lang, **params)


def _grid() -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=LABEL_STYLE, no_wrap=True)
    table.add_column(overflow="fold")
    return table


def summary_table(result: AnalysisResult, lang: str) -> Table:
    """Tabla principal: una línea por dato."""
    table = _grid()
    keywords = ", ".join(result.keywords) or t("keywords.none", lang)
    table.add_row(t("label.topic", lang), Text(result.summary or t("topic.none", lang)))
    table.add_row(t("label.type", lang), Text(format_site_type(result.site_type, lang)))
    table.add_row(t("label.pages", lang), Text(format_pages(result.pages, lang)))
    table.add_row(t("label.tech", lang), Text(format_technologies(result.technologies, lang)))
    table.add_row(t("label.keywords", lang), Text(keywords))
    return table


def details_table(result: AnalysisResult, lang: str) -> Table:
    """Tabla de ``--verbose``: datos HTTP, idiomas, puntaje y señales."""
    table = _grid()
    unknown = t("verbose.unknown", lang)
    site_type = result.site_type
    scores = t("verbose.scores_value", lang, app=site_type.app_score, site=site_type.site_score)
    table.add_row(t("verbose.final_url", lang), Text(result.final_url))
    table.add_row(t("verbose.status", lang), Text(str(result.status_code)))
    table.add_row(t("verbose.server", lang), Text(result.server or unknown))
    table.add_row(t("verbose.elapsed", lang), Text(f"{result.elapsed_ms} ms"))
    table.add_row(t("verbose.site_lang", lang), Text(result.site_lang))
    table.add_row(t("verbose.ui_lang", lang), Text(lang))
    table.add_row(t("verbose.scores", lang), Text(scores))
    lines = [_signal_line(s.code, s.target, s.weight, lang) for s in site_type.signals]
    signals = "\n".join(lines) if lines else t("verbose.no_signals", lang)
    table.add_row(t("verbose.signals", lang), Text(signals))
    return table


def _signal_line(code: str, target: str, weight: int, lang: str) -> str:
    return f"+{weight} {t(f'target.{target}', lang)}: {t(f'signal.{code}', lang)}"


def render(result: AnalysisResult, lang: str, console: Console, verbose: bool = False) -> None:
    """Imprime el reporte de texto en ``console`` en el idioma ``lang``."""
    console.print(Text.assemble("🔎 ", (result.domain, "bold")))
    console.print(Rule(style="dim"))
    console.print(summary_table(result, lang))
    if verbose:
        console.print()
        console.print(Rule(t("verbose.title", lang), style="dim"))
        console.print(details_table(result, lang))


def to_dict(result: AnalysisResult, ui_lang: str) -> dict[str, Any]:
    """Representación JSON: claves siempre en inglés, independientes del idioma."""
    site_type = result.site_type
    return {
        "url": result.url,
        "final_url": result.final_url,
        "domain": result.domain,
        "ui_lang": ui_lang,
        "site_lang": result.site_lang,
        "summary": result.summary,
        "site_type": {
            "type": site_type.kind,
            "confidence": site_type.confidence,
            "scores": {"app": site_type.app_score, "site": site_type.site_score},
            "signals": [
                {"code": s.code, "target": s.target, "weight": s.weight} for s in site_type.signals
            ],
        },
        "pages": {
            "count": result.pages.count,
            "source": result.pages.source,
            "at_least": result.pages.at_least,
        },
        "technologies": [{"name": x.name, "category": x.category} for x in result.technologies],
        "keywords": list(result.keywords),
        "http": {
            "status": result.status_code,
            "server": result.server,
            "elapsed_ms": result.elapsed_ms,
        },
        "webscope_version": __version__,
    }


def to_json(result: AnalysisResult, ui_lang: str) -> str:
    """JSON con indentación y caracteres no ASCII legibles."""
    return json.dumps(to_dict(result, ui_lang), ensure_ascii=False, indent=2)

"""Orquesta el análisis: descarga la home, cuenta páginas y corre los analizadores."""

from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import urlparse

import requests

from webscope.analyzers import (
    classify,
    detect_language,
    detect_technologies,
    extract_keywords,
    summarize,
)
from webscope.crawler import CrawlOptions, EventCallback, count_pages, site_key
from webscope.fetcher import create_session, fetch_page, normalize_url
from webscope.models import AnalysisResult


def _noop(code: str, **params: object) -> None:
    """Callback de eventos por defecto: no hace nada."""


def analyze(
    url: str,
    max_pages: int = 50,
    *,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
    on_event: EventCallback = _noop,
) -> AnalysisResult:
    """Analiza ``url`` y devuelve un ``AnalysisResult``; lanza ``FetchError`` si falla."""
    normalized = normalize_url(url)
    session = session or create_session()
    on_event("fetch_home", url=normalized)
    home = fetch_page(normalized, session)
    site_lang = detect_language(home.html)
    pages = count_pages(
        home, session, CrawlOptions(max_pages=max_pages), sleep=sleep, on_event=on_event
    )
    return AnalysisResult(
        url=normalized,
        final_url=home.final_url,
        domain=site_key(urlparse(home.final_url).hostname) or normalized,
        summary=summarize(home.html),
        site_type=classify(home.html),
        pages=pages,
        technologies=detect_technologies(home.html, home.headers),
        keywords=extract_keywords(home.html, site_lang),
        site_lang=site_lang,
        status_code=home.status_code,
        server=home.headers.get("server"),
        elapsed_ms=home.elapsed_ms,
    )

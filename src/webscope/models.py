"""Modelos de datos inmutables que comparten analizadores, crawler y reporte.

Todos los campos son datos o códigos estables (por ejemplo ``"site"``, ``"high"``);
nunca texto traducido. La traducción ocurre únicamente en ``report.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SiteKind = Literal["site", "app"]
Confidence = Literal["low", "medium", "high"]
PageSource = Literal["sitemap", "crawl"]


@dataclass(frozen=True)
class Technology:
    """Una tecnología detectada y su categoría (``base``, ``cms``, ``framework``...)."""

    name: str
    category: str


@dataclass(frozen=True)
class Signal:
    """Una pista que sumó puntos a ``site`` o ``app`` en la clasificación."""

    code: str
    target: SiteKind
    weight: int


@dataclass(frozen=True)
class SiteTypeResult:
    """Resultado de la clasificación sitio web / app web."""

    kind: SiteKind
    confidence: Confidence
    app_score: int
    site_score: int
    signals: tuple[Signal, ...] = ()


@dataclass(frozen=True)
class PageCount:
    """Cantidad de páginas encontradas y de dónde salió el número."""

    count: int
    source: PageSource
    at_least: bool = False


@dataclass(frozen=True)
class AnalysisResult:
    """Resultado completo del análisis de una URL."""

    url: str
    final_url: str
    domain: str
    summary: str
    site_type: SiteTypeResult
    pages: PageCount
    technologies: tuple[Technology, ...]
    keywords: tuple[str, ...]
    site_lang: str
    status_code: int = 200
    server: str | None = None
    elapsed_ms: int = 0
    details: dict[str, str] = field(default_factory=dict)

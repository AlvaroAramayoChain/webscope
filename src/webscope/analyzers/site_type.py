"""Clasificación sitio web / app web por puntaje de heurísticas con nivel de confianza."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from bs4 import BeautifulSoup

from webscope.models import Confidence, Signal, SiteKind, SiteTypeResult
from webscope.parsing import make_soup, visible_text

_SPA_ROOT_IDS = re.compile(r"^(root|app|__next|__nuxt|svelte|main-app|application)$", re.I)
_BUNDLE_RE = re.compile(r"(chunk|bundle|main|app|runtime|vendor|index)[.-][0-9a-z_-]{6,}\.js", re.I)
_APP_ROUTE_RE = re.compile(
    r"/(login|log-in|signin|sign-in|signup|sign-up|register|dashboard|app|account|admin)(?:/|$|\?)"
    r"|/api/",
    re.I,
)
_BLOG_RE = re.compile(
    r"/(blog|news|noticias|novedades|articulos?|articles?|posts?|prensa|press)(?:/|$)", re.I
)
_INFO_RE = re.compile(
    r"/(about|about-us|contact|contacto|contact-us|nosotros|quienes-somos|sobre-nosotros|"
    r"servicios|services|faq|preguntas-frecuentes|equipo|team|empresa|company)(?:/|$|\.html?)",
    re.I,
)
_GENERATOR_RE = re.compile(
    r"wordpress|drupal|joomla|hugo|jekyll|ghost|wix|squarespace|webflow|gatsby|astro|"
    r"docusaurus|hexo|eleventy|mkdocs|sphinx",
    re.I,
)


@dataclass(frozen=True)
class _Page:
    """Datos precalculados del HTML que usan las heurísticas."""

    soup: BeautifulSoup
    html: str
    text: str
    links: tuple[str, ...]
    scripts: tuple[str, ...]


def _prepare(html: str) -> _Page:
    soup = make_soup(html)
    links = tuple(str(a["href"]) for a in soup.find_all("a", href=True))
    scripts = tuple(str(s["src"]) for s in soup.find_all("script", src=True))
    return _Page(soup=soup, html=html, text=visible_text(html), links=links, scripts=scripts)


# --- Heurísticas que suman a "app" -------------------------------------------------


def _app_signals(page: _Page) -> Iterator[Signal]:
    root = page.soup.find(id=_SPA_ROOT_IDS)
    if root is not None and len(page.text) < 200:
        yield Signal("spa_root", "app", 3)
    if len(page.text) < 300:
        yield Signal("little_text", "app", 2)
    if len(page.scripts) >= 8:
        yield Signal("many_scripts", "app", 2)
    elif len(page.scripts) >= 5:
        yield Signal("many_scripts", "app", 1)
    module = page.soup.find("script", attrs={"type": "module"})
    if module is not None or any(_BUNDLE_RE.search(src) for src in page.scripts):
        yield Signal("module_scripts", "app", 1)
    if page.soup.find("link", rel="manifest") is not None:
        yield Signal("manifest", "app", 1)
    if "serviceWorker.register" in page.html or "navigator.serviceWorker" in page.html:
        yield Signal("service_worker", "app", 2)
    routes = {
        m.group(0).lower()
        for ref in (*page.links, *page.scripts)
        if (m := _APP_ROUTE_RE.search(ref))
    }
    if routes:
        yield Signal("app_routes", "app", min(2, len(routes)))
    noscript = " ".join(tag.get_text(" ") for tag in page.soup.find_all("noscript"))
    if "javascript" in noscript.lower():
        yield Signal("noscript_js", "app", 2)
    if page.soup.find("input", attrs={"type": "password"}) is not None:
        yield Signal("password_form", "app", 2)


# --- Heurísticas que suman a "site" ------------------------------------------------


def _site_signals(page: _Page) -> Iterator[Signal]:
    if len(page.text) >= 2000:
        yield Signal("rich_text", "site", 3)
    elif len(page.text) >= 700:
        yield Signal("some_text", "site", 2)
    paragraphs = [p for p in page.soup.find_all("p") if len(p.get_text(strip=True)) >= 60]
    if len(paragraphs) >= 5:
        yield Signal("paragraphs", "site", 2)
    nav_links = sum(len(nav.find_all("a", href=True)) for nav in page.soup.find_all("nav"))
    if nav_links >= 5 or len(page.links) >= 30:
        yield Signal("nav_links", "site", 2)
    elif len(page.links) >= 15:
        yield Signal("nav_links", "site", 1)
    if len(page.soup.find_all(["h2", "h3"])) >= 6:
        yield Signal("headings", "site", 1)
    if len(page.soup.find_all("article")) >= 2 or any(_BLOG_RE.search(h) for h in page.links):
        yield Signal("blog", "site", 2)
    info = {m.group(1).lower() for h in page.links if (m := _INFO_RE.search(h))}
    if info:
        yield Signal("info_pages", "site", 2 if len(info) >= 3 else 1)
    generator = page.soup.find("meta", attrs={"name": "generator"})
    content = generator.get("content") if generator else None
    if isinstance(content, str) and _GENERATOR_RE.search(content):
        yield Signal("cms_generator", "site", 2)


def confidence_for(margin: int) -> Confidence:
    """Confianza según la diferencia de puntaje entre ``app`` y ``site``."""
    if margin >= 5:
        return "high"
    if margin >= 2:
        return "medium"
    return "low"


HEURISTICS: tuple[Callable[[_Page], Iterator[Signal]], ...] = (_app_signals, _site_signals)


def classify(html: str) -> SiteTypeResult:
    """Clasifica el HTML como ``site`` o ``app`` y devuelve las señales usadas."""
    page = _prepare(html)
    signals = tuple(signal for heuristic in HEURISTICS for signal in heuristic(page))
    app_score = sum(s.weight for s in signals if s.target == "app")
    site_score = sum(s.weight for s in signals if s.target == "site")
    kind: SiteKind = "app" if app_score > site_score else "site"
    return SiteTypeResult(
        kind=kind,
        confidence=confidence_for(abs(app_score - site_score)),
        app_score=app_score,
        site_score=site_score,
        signals=signals,
    )

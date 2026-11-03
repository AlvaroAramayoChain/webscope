"""Conteo de páginas: sitemap.xml (vía robots.txt) y, si no hay, rastreo BFS.

Respeta ``robots.txt``, deduplica URLs (sin fragmentos y sin barra final) y hace una
pausa entre requests. Los eventos de progreso se emiten como códigos por
``on_event`` para que el CLI los traduzca.
"""

from __future__ import annotations

import gzip
import html as html_lib
import io
import re
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests

from webscope.fetcher import FetchedPage, FetchError, fetch_bytes, fetch_page
from webscope.models import PageCount
from webscope.parsing import make_soup

EventCallback = Callable[..., None]

ROBOTS_AGENT = "webscope"
_LOC_RE = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</loc>", re.I | re.S)
_SITEMAP_INDEX_RE = re.compile(r"<sitemapindex[\s>]", re.I)
_SKIP_EXTENSIONS = frozenset(
    [
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".avif",
        ".ico",
        ".bmp",
        ".css",
        ".js",
        ".mjs",
        ".json",
        ".xml",
        ".rss",
        ".txt",
        ".csv",
        ".zip",
        ".rar",
        ".7z",
        ".gz",
        ".tar",
        ".mp3",
        ".mp4",
        ".webm",
        ".avi",
        ".mov",
        ".wav",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".exe",
        ".dmg",
        ".apk",
    ]
)


@dataclass(frozen=True)
class CrawlOptions:
    """Límites del conteo de páginas."""

    max_pages: int = 50
    delay: float = 0.3
    max_sitemaps: int = 25
    max_sitemap_depth: int = 2


def _noop(code: str, **params: object) -> None:
    """Callback de eventos por defecto: no hace nada."""


def site_key(host: str | None) -> str:
    """Host normalizado para comparar dominios (minúsculas y sin ``www.``)."""
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def normalize_link(url: str) -> str | None:
    """Normaliza una URL http(s) para deduplicar; ``None`` si no es una página."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    path = parsed.path or "/"
    if any(path.lower().endswith(ext) for ext in _SKIP_EXTENSIONS):
        return None
    path = path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def extract_links(html: str, base_url: str) -> list[str]:
    """Links internos (mismo dominio) normalizados y sin repetir, en orden de aparición."""
    domain = site_key(urlparse(base_url).hostname)
    links: dict[str, None] = {}
    for anchor in make_soup(html).find_all("a", href=True):
        href = str(anchor["href"]).strip()
        normalized = normalize_link(urljoin(base_url, href))
        if normalized and site_key(urlparse(normalized).hostname) == domain:
            links.setdefault(normalized, None)
    return list(links)


def origin_of(url: str) -> str:
    """``https://host`` de una URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def load_robots(
    origin: str, session: requests.Session, on_event: EventCallback = _noop
) -> RobotFileParser | None:
    """Descarga y parsea ``robots.txt``; ``None`` si no existe (todo permitido)."""
    url = f"{origin}/robots.txt"
    body = fetch_bytes(url, session)
    if body is None:
        on_event("robots_missing")
        return None
    parser = RobotFileParser(url)
    parser.parse(body.decode("utf-8", errors="replace").splitlines())
    on_event("robots_found", url=url)
    return parser


def _decompress(body: bytes) -> bytes:
    if not body.startswith(b"\x1f\x8b"):
        return body
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as archive:
            return archive.read(20 * 1024 * 1024)
    except (OSError, EOFError):
        return b""


def parse_sitemap(body: bytes) -> tuple[bool, list[str]]:
    """Devuelve ``(es_index, locs)`` de un sitemap XML (o .xml.gz)."""
    text = _decompress(body).decode("utf-8", errors="replace")
    locs = [html_lib.unescape(loc) for loc in _LOC_RE.findall(text) if loc]
    return bool(_SITEMAP_INDEX_RE.search(text)), locs


def read_sitemaps(
    start_urls: Iterable[str],
    session: requests.Session,
    options: CrawlOptions,
    on_event: EventCallback = _noop,
) -> tuple[set[str], bool]:
    """Recorre sitemaps e índices; devuelve ``(urls_de_páginas, quedó_incompleto)``."""
    queue = deque((url, 0) for url in start_urls)
    visited: set[str] = set()
    pages: set[str] = set()
    truncated = False
    while queue:
        url, depth = queue.popleft()
        if url in visited:
            continue
        if len(visited) >= options.max_sitemaps:
            truncated = True
            on_event("sitemap_limit")
            break
        visited.add(url)
        on_event("sitemap_try", url=url)
        body = fetch_bytes(url, session)
        if body is None:
            continue
        is_index, locs = parse_sitemap(body)
        if is_index:
            on_event("sitemap_index", url=url, count=len(locs))
            if depth >= options.max_sitemap_depth:
                truncated = truncated or bool(locs)
                continue
            queue.extend((loc, depth + 1) for loc in locs)
            continue
        new_pages = {link for loc in locs if (link := normalize_link(loc))}
        on_event("sitemap_found", url=url, count=len(new_pages))
        pages |= new_pages
    return pages, truncated


def crawl(
    home: FetchedPage,
    session: requests.Session,
    robots: RobotFileParser | None,
    options: CrawlOptions,
    *,
    sleep: Callable[[float], None] = time.sleep,
    on_event: EventCallback = _noop,
) -> PageCount:
    """Cuenta páginas siguiendo links internos (BFS) hasta ``options.max_pages``."""
    start = normalize_link(home.final_url) or home.final_url
    seen = {start}
    queue: deque[str] = deque()
    _enqueue(extract_links(home.html, home.final_url), seen, queue)
    count = 1
    on_event("crawl_page", n=count, max=options.max_pages, url=start)
    while queue and count < options.max_pages:
        url = queue.popleft()
        if robots is not None and not robots.can_fetch(ROBOTS_AGENT, url):
            on_event("crawl_blocked", url=url)
            continue
        sleep(options.delay)
        try:
            page = fetch_page(url, session)
        except FetchError:
            on_event("crawl_error", url=url)
            continue
        count += 1
        on_event("crawl_page", n=count, max=options.max_pages, url=url)
        seen.add(normalize_link(page.final_url) or page.final_url)
        _enqueue(extract_links(page.html, page.final_url), seen, queue)
    at_least = bool(queue) and count >= options.max_pages
    if at_least:
        on_event("crawl_limit", max=options.max_pages)
    return PageCount(count=count, source="crawl", at_least=at_least)


def _enqueue(links: Iterable[str], seen: set[str], queue: deque[str]) -> None:
    for link in links:
        if link not in seen:
            seen.add(link)
            queue.append(link)


def count_pages(
    home: FetchedPage,
    session: requests.Session,
    options: CrawlOptions | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
    on_event: EventCallback = _noop,
) -> PageCount:
    """Cuenta las páginas del sitio: primero por sitemap y, si no hay, rastreando."""
    options = options or CrawlOptions()
    origin = origin_of(home.final_url)
    robots = load_robots(origin, session, on_event)
    declared = robots.site_maps() if robots is not None else None
    sitemap_urls = list(declared or [f"{origin}/sitemap.xml"])
    pages, truncated = read_sitemaps(sitemap_urls, session, options, on_event)
    domain = site_key(urlparse(home.final_url).hostname)
    pages = {page for page in pages if site_key(urlparse(page).hostname) == domain}
    if pages:
        return PageCount(count=len(pages), source="sitemap", at_least=truncated)
    on_event("sitemap_missing")
    return crawl(home, session, robots, options, sleep=sleep, on_event=on_event)


__all__ = [
    "CrawlOptions",
    "count_pages",
    "crawl",
    "extract_links",
    "normalize_link",
    "parse_sitemap",
    "read_sitemaps",
]

"""Orquesta el análisis: descarga la home y junta en paralelo crawl, DNS, TLS y archivos.

Solo la descarga de la home es obligatoria (si falla, ``FetchError``). Todo lo demás
falla de forma independiente: el bloque afectado queda en ``unavailable`` con un
código de motivo y el resto del reporte sale igual.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeVar
from urllib.parse import urlparse

import requests

from webscope import dnsinfo, tlsprobe
from webscope.analyzers import (
    classify,
    detect_language,
    detect_technologies,
    extract_keywords,
)
from webscope.analyzers.findings import FindingContext, evaluate
from webscope.analyzers.infra import build_infra, parse_rdap
from webscope.analyzers.security import build_security
from webscope.analyzers.tls import analyze_certificate
from webscope.analyzers.topic import describe, pick_internal_pages
from webscope.crawler import (
    ROBOTS_AGENT,
    CrawlOptions,
    CrawlResult,
    EventCallback,
    Robots,
    discover,
    extract_links,
    fetch_robots,
    origin_of,
    site_key,
)
from webscope.fetcher import (
    DEFAULT_TIMEOUT,
    FetchedPage,
    FetchError,
    create_session,
    fetch_page,
    fetch_resource,
    normalize_url,
)
from webscope.models import (
    AnalysisResult,
    DnsRecords,
    HttpRedirect,
    PageCount,
    RdapInfo,
    TlsResult,
)

T = TypeVar("T")
RDAP_URL = "https://rdap.org/domain/{domain}"
SECURITY_TXT_PATH = "/.well-known/security.txt"
MAX_WORKERS = 6


def _noop(code: str, **params: object) -> None:
    """Callback de eventos por defecto: no hace nada."""


@dataclass(frozen=True)
class AnalyzeOptions:
    """Qué partes del análisis correr y con qué límites."""

    max_pages: int = 50
    brief: bool = False
    crawl: bool = True
    rdap: bool = False
    timeout: float = DEFAULT_TIMEOUT
    delay: float = 0.3


class _Unavailable(Exception):
    """Un bloque no se pudo completar; ``reason`` es un código traducible."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _outcome(future: Future[T] | None, block: str, unavailable: dict[str, str]) -> T | None:
    """Resultado de una tarea o ``None`` registrando el motivo en ``unavailable``."""
    if future is None:
        return None
    try:
        return future.result()
    except _Unavailable as exc:
        unavailable[block] = exc.reason
    except Exception:  # cada bloque falla por su cuenta, nunca un stack trace
        unavailable[block] = "error"
    return None


# --- Tareas -------------------------------------------------------------------------


def _crawl_task(
    home: FetchedPage,
    session: requests.Session,
    opts: AnalyzeOptions,
    sleep: Callable[[float], None],
    on_event: EventCallback,
) -> CrawlResult | Robots:
    if not opts.crawl:
        return fetch_robots(origin_of(home.final_url), session, on_event, opts.timeout)
    crawl_opts = CrawlOptions(max_pages=opts.max_pages, delay=opts.delay, timeout=opts.timeout)
    return discover(home, session, crawl_opts, sleep=sleep, on_event=on_event)


def _dns_task(host: str, opts: AnalyzeOptions, on_event: EventCallback) -> DnsRecords:
    if dnsinfo.is_local_host(host):
        raise _Unavailable("local_host")
    on_event("dns_start", host=host)
    try:
        query = dnsinfo.make_query(min(opts.timeout, dnsinfo.DEFAULT_TIMEOUT))
    except dnsinfo.DnsError as exc:
        raise _Unavailable(f"dns_{exc.code}") from exc
    records = dnsinfo.collect(host, query, is_target_ip=dnsinfo.is_ip(host))
    if records.error:
        raise _Unavailable(f"dns_{records.error}")
    return records


def _tls_task(host: str, port: int, opts: AnalyzeOptions, on_event: EventCallback) -> TlsResult:
    on_event("tls_start", host=host, port=port)
    try:
        probe = tlsprobe.probe(host, port, opts.timeout)
    except tlsprobe.TlsError as exc:
        raise _Unavailable(f"tls_{exc.code}") from exc
    return analyze_certificate(
        probe.cert,
        protocol=probe.protocol,
        cipher=probe.cipher,
        verified=probe.verified,
        verify_error=probe.verify_error,
        peer_ip=probe.peer_ip,
    )


def _security_txt_task(origin: str, opts: AnalyzeOptions) -> str | None:
    resource = fetch_resource(origin + SECURITY_TXT_PATH, create_session(), opts.timeout)
    if resource is None:
        raise _Unavailable("no_response")
    if resource.status_code != 200:
        return None
    return resource.text


def _http_probe_task(netloc: str, opts: AnalyzeOptions, on_event: EventCallback) -> HttpRedirect:
    url = f"http://{netloc}/"
    on_event("http_probe", url=url)
    resource = fetch_resource(url, create_session(), opts.timeout, limit=4096)
    if resource is None:
        raise _Unavailable("no_response")
    first = resource.redirects[0].status if resource.redirects else resource.status_code
    return HttpRedirect(
        redirects_to_https=resource.final_url.lower().startswith("https://"),
        status=first,
        final_url=resource.final_url,
    )


def _rdap_task(host: str, opts: AnalyzeOptions, on_event: EventCallback) -> RdapInfo:
    if dnsinfo.is_ip(host) or dnsinfo.is_local_host(host):
        raise _Unavailable("not_applicable")
    domain = dnsinfo.registrable_domain(host)
    on_event("rdap_start", domain=domain)
    session = create_session()
    session.headers["Accept"] = "application/rdap+json, application/json"
    resource = fetch_resource(
        RDAP_URL.format(domain=domain), session, opts.timeout, limit=1024 * 1024
    )
    if resource is None or resource.status_code != 200:
        raise _Unavailable("rdap_failed")
    try:
        data = json.loads(resource.body.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise _Unavailable("rdap_failed") from exc
    return parse_rdap(domain, data)


# --- Páginas internas ---------------------------------------------------------------


def _internal_pages(
    home: FetchedPage,
    crawl: CrawlResult | None,
    robots: Robots,
    session: requests.Session,
    opts: AnalyzeOptions,
    sleep: Callable[[float], None],
    on_event: EventCallback,
) -> list[str]:
    """HTML de hasta 5 páginas internas útiles, reutilizando lo que ya bajó el crawler."""
    known = list(crawl.urls) if crawl else []
    cached: Mapping[str, str] = crawl.html if crawl else {}
    candidates = [*extract_links(home.html, home.final_url), *known]
    pages: list[str] = []
    for url in pick_internal_pages(candidates, home.final_url):
        if url in cached:
            pages.append(cached[url])
            continue
        if robots.parser is not None and not robots.parser.can_fetch(ROBOTS_AGENT, url):
            continue
        sleep(opts.delay)
        on_event("topic_page", url=url)
        try:
            pages.append(fetch_page(url, session, opts.timeout).html)
        except FetchError:
            continue
    return pages


# --- Análisis -----------------------------------------------------------------------


def _now_iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def analyze(
    url: str,
    max_pages: int = 50,
    *,
    options: AnalyzeOptions | None = None,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] | None = None,
    on_event: EventCallback = _noop,
) -> AnalysisResult:
    """Analiza ``url`` y devuelve un ``AnalysisResult``; lanza ``FetchError`` si la home falla."""
    opts = options or AnalyzeOptions(max_pages=max_pages)
    sleep = sleep or time.sleep
    started = datetime.now(timezone.utc)
    normalized = normalize_url(url)
    session = session or create_session()
    on_event("fetch_home", url=normalized)
    home = fetch_page(normalized, session, opts.timeout)
    final = urlparse(home.final_url)
    host = (final.hostname or "").lower()
    https = final.scheme == "https"
    unavailable: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        crawl_job = pool.submit(_crawl_task, home, session, opts, sleep, on_event)
        dns_job = tls_job = sectxt_job = http_job = rdap_job = None
        if not opts.brief:
            dns_job = pool.submit(_dns_task, host, opts, on_event)
            if https:
                tls_job = pool.submit(_tls_task, host, final.port or 443, opts, on_event)
            else:
                unavailable["tls"] = "http_only"
            sectxt_job = pool.submit(_security_txt_task, origin_of(home.final_url), opts)
            if https and not final.port:
                http_job = pool.submit(_http_probe_task, final.netloc, opts, on_event)
            if opts.rdap:
                rdap_job = pool.submit(_rdap_task, host, opts, on_event)

        crawled = _outcome(crawl_job, "pages", unavailable)
        crawl = crawled if isinstance(crawled, CrawlResult) else None
        robots = crawl.robots if crawl else (crawled if isinstance(crawled, Robots) else Robots())
        extra_pages = _internal_pages(home, crawl, robots, session, opts, sleep, on_event)

        dns = _outcome(dns_job, "dns", unavailable)
        tls = _outcome(tls_job, "tls", unavailable)
        security_txt = _outcome(sectxt_job, "security_txt", unavailable)
        http_redirect = _outcome(http_job, "http_redirect", unavailable)
        rdap = _outcome(rdap_job, "rdap", unavailable)

    technologies = detect_technologies(home.html, home.headers)
    topic = describe(
        home.html,
        host,
        extra_pages=extra_pages,
        technologies=[tech.name for tech in technologies],
    )
    site_lang = detect_language(home.html)
    pages: PageCount | None = crawl.pages if crawl else None
    if not opts.crawl:
        unavailable["pages"] = "no_crawl"

    infra = security = None
    findings = ()
    if not opts.brief:
        infra = build_infra(
            dns,
            home.headers,
            connected_ip=home.peer_ip or (tls.peer_ip if tls else None),
            rdap=rdap,
        )
        crawl_checked = crawl is not None or isinstance(crawled, Robots)
        security = build_security(
            page_url=home.final_url,
            headers=home.headers,
            html=home.html,
            set_cookies=home.set_cookies,
            dns=dns,
            robots_text=robots.text,
            robots_checked=crawl_checked,
            security_txt=security_txt,
            security_txt_checked="security_txt" not in unavailable,
            sitemap=crawl.sitemap_found if crawl else None,
            http_redirect=http_redirect,
            sans=tls.sans if tls else (),
        )
        findings = evaluate(FindingContext(home.final_url, security, tls, infra, technologies))

    return AnalysisResult(
        url=normalized,
        final_url=home.final_url,
        domain=site_key(host) or normalized,
        summary=topic.description,
        site_type=classify(home.html),
        pages=pages,
        technologies=technologies,
        keywords=extract_keywords(home.html, site_lang),
        site_lang=site_lang,
        status_code=home.status_code,
        server=home.headers.get("server"),
        elapsed_ms=home.elapsed_ms,
        topic=topic,
        redirects=home.redirects,
        infra=infra,
        tls=tls,
        security=security,
        findings=findings,
        unavailable=unavailable,
        scanned_at=_now_iso(started),
        brief=opts.brief,
    )


__all__ = ["AnalyzeOptions", "analyze"]

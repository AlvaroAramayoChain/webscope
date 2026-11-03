"""Postura de seguridad visible: headers, fugas, cookies, email, archivos y contenido.

Funciones puras que reciben datos ya obtenidos (headers, HTML, ``Set-Cookie``,
registros DNS, ``robots.txt``, ``security.txt``). No hacen red ni sondean rutas:
los endpoints y subdominios se listan solo si aparecen referenciados en el contenido.

Puntaje de headers (máximo 8):
- HSTS: 2 si ``max-age`` >= 6 meses, 1 si es menor (solo en HTTPS).
- CSP: 2 si no usa ``unsafe-inline``/``unsafe-eval``/comodines, 1 si los usa.
- X-Frame-Options o ``frame-ancestors``, X-Content-Type-Options ``nosniff``,
  Referrer-Policy y Permissions-Policy: 1 cada uno.
Nota: A = 7–8, B = 6, C = 4–5, D = 2–3, F = 0–1. COOP, CORP y COEP se informan
pero no suman (todavía son poco comunes y su ausencia no es un problema en sí).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Final
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, Tag

from webscope.dnsinfo import is_null_mx, registrable_domain
from webscope.models import (
    ContentInfo,
    CookieInfo,
    DnsRecords,
    EmailPosture,
    FilesInfo,
    FormsInfo,
    HeaderCheck,
    HeadersReport,
    HttpRedirect,
    Leak,
    SecurityResult,
    SecurityTxt,
    SurfaceInfo,
)
from webscope.parsing import make_soup

HSTS_MIN_AGE: Final = 15552000  # 180 días
GRADES: Final = ((7, "A"), (6, "B"), (4, "C"), (2, "D"), (0, "F"))
EXTRA_HEADERS: Final = (
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "cross-origin-embedder-policy",
)
SENSITIVE_ROBOTS: Final = re.compile(
    r"admin|backup|\.bak|/old|private|privado|config|/db|database|\.sql|staging|/test|"
    r"/dev|/tmp|internal|secret|login|cgi-bin|\.git|\.env|phpmyadmin|/api|dashboard|panel",
    re.I,
)
SURFACE_SEGMENTS: Final = frozenset(
    "api graphql admin administrator login signin sign-in wp-admin wp-json wp-login.php "
    "dashboard console swagger swagger-ui openapi.json actuator phpmyadmin cpanel "
    "xmlrpc.php panel".split()
)
_VERSION = re.compile(r"\d+\.\d+")
_COMMENT_HINT = re.compile(
    r"wordpress|yoast|powered by|generator|version|\bver\b|built with|plugin|theme|drupal|"
    r"joomla|wp rocket|w3 total cache|litespeed|elementor|seo|cache",
    re.I,
)
_SRC_ATTRS: Final = (
    ("script", "src"),
    ("link", "href"),
    ("img", "src"),
    ("iframe", "src"),
    ("audio", "src"),
    ("video", "src"),
    ("source", "src"),
    ("embed", "src"),
    ("object", "data"),
)
_PATH_RE = re.compile(r"""["'(=\s](/[A-Za-z0-9_\-./~%]{1,150})(?=["'?#\s)<>])""")
_ABS_URL_RE = re.compile(r"""https?://[A-Za-z0-9.\-]+(?::\d+)?(/[A-Za-z0-9_\-./~%]{0,150})?""")
MAX_ITEMS: Final = 25


# --- Headers ------------------------------------------------------------------------


def parse_hsts(value: str) -> tuple[int | None, bool, bool]:
    """``(max_age, includeSubDomains, preload)`` de un header HSTS."""
    match = re.search(r"max-age\s*=\s*\"?(\d+)", value, re.I)
    lowered = value.lower()
    return (
        int(match.group(1)) if match else None,
        "includesubdomains" in lowered,
        "preload" in lowered,
    )


def csp_issues(value: str) -> tuple[str, ...]:
    """Problemas de una CSP: ``unsafe-inline``, ``unsafe-eval``, ``wildcard``."""
    issues: list[str] = []
    directives = {
        part.split()[0].lower(): part.split()[1:] for part in value.split(";") if part.strip()
    }
    sources = directives.get("script-src") or directives.get("default-src") or []
    lowered = [s.lower() for s in sources]
    has_nonce = any(s.startswith(("'nonce-", "'sha256-", "'sha384-", "'sha512-")) for s in lowered)
    if "'unsafe-inline'" in lowered and not has_nonce:
        issues.append("unsafe-inline")
    if "'unsafe-eval'" in lowered:
        issues.append("unsafe-eval")
    if any(s in ("*", "http:", "https:", "data:") for s in lowered):
        issues.append("wildcard")
    return tuple(issues)


def frame_ancestors(csp: str) -> bool:
    """La CSP define ``frame-ancestors`` (equivale a X-Frame-Options)."""
    return bool(re.search(r"(?:^|;)\s*frame-ancestors\s", csp, re.I))


def grade_for(score: int) -> str:
    """Nota A–F según el puntaje sobre 8."""
    return next(grade for minimum, grade in GRADES if score >= minimum)


def analyze_headers(headers: Mapping[str, str], https: bool) -> HeadersReport:
    """Evalúa los security headers y calcula puntaje y nota."""
    h = {k.lower(): v for k, v in headers.items()}
    checks: list[HeaderCheck] = []

    hsts = h.get("strict-transport-security")
    hsts_points, hsts_issues = 0, ()
    if hsts and https:
        max_age, _, _ = parse_hsts(hsts)
        weak = max_age is None or max_age < HSTS_MIN_AGE
        hsts_points, hsts_issues = (1, ("short-max-age",)) if weak else (2, ())
    checks.append(
        HeaderCheck(
            "Strict-Transport-Security", bool(hsts and https), hsts_points, 2, hsts, hsts_issues
        )
    )

    csp = h.get("content-security-policy")
    issues = csp_issues(csp) if csp else ()
    checks.append(
        HeaderCheck(
            "Content-Security-Policy", bool(csp), (1 if issues else 2) if csp else 0, 2, csp, issues
        )
    )

    xfo = h.get("x-frame-options")
    has_frame = bool(xfo) or bool(csp and frame_ancestors(csp))
    checks.append(
        HeaderCheck(
            "X-Frame-Options", has_frame, int(has_frame), 1, xfo or (csp and "frame-ancestors")
        )
    )

    xcto = h.get("x-content-type-options")
    nosniff = bool(xcto and "nosniff" in xcto.lower())
    checks.append(HeaderCheck("X-Content-Type-Options", nosniff, int(nosniff), 1, xcto))

    for name in ("Referrer-Policy", "Permissions-Policy"):
        value = h.get(name.lower())
        checks.append(HeaderCheck(name, bool(value), int(bool(value)), 1, value))

    score = sum(c.points for c in checks)
    extra = {name: h[name] for name in EXTRA_HEADERS if name in h}
    if "content-security-policy-report-only" in h:
        extra["content-security-policy-report-only"] = h["content-security-policy-report-only"]
    return HeadersReport(
        checks=tuple(checks),
        score=score,
        max_score=sum(c.max_points for c in checks),
        grade=grade_for(score),
        extra=extra,
    )  # fmt: skip


# --- Fugas de información -----------------------------------------------------------


def html_comments(html: str, limit: int = 5) -> tuple[str, ...]:
    """Comentarios HTML que parecen revelar software y versión."""
    soup = make_soup(html)
    found: list[str] = []
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        text = " ".join(str(comment).split())
        if text.startswith("[if") or not _VERSION.search(text) or not _COMMENT_HINT.search(text):
            continue
        found.append(text[:100])
        if len(found) >= limit:
            break
    return tuple(dict.fromkeys(found))


def find_leaks(headers: Mapping[str, str], html: str) -> tuple[Leak, ...]:
    """Headers, ``meta generator`` y comentarios que revelan software o versiones."""
    h = {k.lower(): v for k, v in headers.items()}
    leaks: list[Leak] = []
    server = h.get("server")
    if server and _VERSION.search(server):
        leaks.append(Leak("server", server))
    for name in ("x-powered-by", "x-aspnet-version", "x-aspnetmvc-version", "x-generator"):
        if h.get(name):
            leaks.append(Leak(name, h[name]))
    generator = make_soup(html).find("meta", attrs={"name": "generator"})
    content = generator.get("content") if generator else None
    if isinstance(content, str) and content.strip():
        leaks.append(Leak("meta-generator", content.strip()))
    leaks.extend(Leak("html-comment", text) for text in html_comments(html))
    return tuple(leaks)


# --- Cookies ------------------------------------------------------------------------


def parse_cookie(raw: str) -> CookieInfo | None:
    """Atributos de seguridad de un header ``Set-Cookie``."""
    parts = [p.strip() for p in raw.split(";")]
    name = parts[0].split("=", 1)[0].strip() if parts and "=" in parts[0] else ""
    if not name:
        return None
    attrs = {
        p.split("=", 1)[0].strip().lower(): p.split("=", 1)[1].strip() if "=" in p else ""
        for p in parts[1:]
    }
    prefix = next((p for p in ("__Host-", "__Secure-") if name.startswith(p)), None)
    samesite = attrs.get("samesite")
    return CookieInfo(
        name=name,
        secure="secure" in attrs,
        httponly="httponly" in attrs,
        samesite=samesite.capitalize() if samesite else None,
        prefix=prefix,
    )  # fmt: skip


def parse_cookies(set_cookies: Iterable[str]) -> tuple[CookieInfo, ...]:
    """Cookies únicas por nombre (la última definición gana)."""
    cookies = {c.name: c for raw in set_cookies if (c := parse_cookie(raw))}
    return tuple(cookies.values())


# --- Email --------------------------------------------------------------------------


def spf_qualifier(record: str) -> str | None:
    """``-all``, ``~all``, ``?all``, ``+all``, ``redirect`` o ``None`` si no define política."""
    match = re.search(r"(?:^|\s)([+~?-]?)all(?:\s|$)", record, re.I)
    if match:
        return (match.group(1) or "+") + "all"
    if re.search(r"(?:^|\s)redirect=", record, re.I):
        return "redirect"
    return None


def dmarc_policy(record: str) -> str | None:
    """Valor de ``p=`` de un registro DMARC."""
    match = re.search(r"(?:^|;)\s*p\s*=\s*(\w+)", record, re.I)
    return match.group(1).lower() if match else None


def analyze_email(dns: DnsRecords) -> EmailPosture:
    """SPF (política ``all``), DMARC (``p=``), selectores DKIM, MTA-STS y BIMI."""
    spf_records = [t for t in dns.txt if t.lower().startswith("v=spf1")]
    spf = spf_records[0] if spf_records else None
    dmarc = dns.dmarc[0] if dns.dmarc else None
    return EmailPosture(
        has_mx=any(not is_null_mx(mx) for mx in dns.mx),
        unanswered=tuple(k for k in dns.unanswered if k in ("mx", "txt", "dmarc", "dkim")),
        spf=spf,
        spf_all=spf_qualifier(spf) if spf else None,
        spf_records=len(spf_records),
        dmarc=dmarc,
        dmarc_policy=dmarc_policy(dmarc) if dmarc else None,
        dkim_selectors=dns.dkim,
        mta_sts=bool(dns.mta_sts),
        bimi=bool(dns.bimi),
    )


# --- Archivos y políticas -----------------------------------------------------------


def parse_security_txt(text: str, now: datetime | None = None) -> SecurityTxt | None:
    """Contactos y vencimiento de ``security.txt``; ``None`` si no parece uno real."""
    if "<html" in text[:500].lower():
        return None
    contacts: list[str] = []
    expires: str | None = None
    for line in text.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "contact" and value:
            contacts.append(value)
        elif key == "expires" and value:
            expires = value
    if not contacts:
        return None
    expired = False
    if expires:
        try:
            date = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            date = date if date.tzinfo else date.replace(tzinfo=timezone.utc)
            expired = date < (now or datetime.now(timezone.utc))
        except ValueError:
            pass
    return SecurityTxt(contacts=tuple(contacts), expires=expires, expired=expired)


def sensitive_robots_paths(robots_text: str) -> tuple[str, ...]:
    """Rutas ``Disallow`` de ``robots.txt`` que suenan sensibles (solo como dato)."""
    paths: list[str] = []
    for line in robots_text.splitlines():
        key, _, value = line.partition(":")
        value = value.split("#", 1)[0].strip()
        if key.strip().lower() == "disallow" and value and SENSITIVE_ROBOTS.search(value):
            paths.append(value)
    return tuple(dict.fromkeys(paths))[:MAX_ITEMS]


# --- Contenido ----------------------------------------------------------------------


def _same_site(host: str | None, site: str) -> bool:
    host = (host or "").lower()
    return host == site or host.endswith("." + site)


def _rel_has(tag: Tag, *values: str) -> bool:
    rel = tag.get("rel")
    tokens = rel if isinstance(rel, list) else str(rel or "").split()
    return any(v in (t.lower() for t in tokens) for v in values)


def analyze_content(html: str, page_url: str) -> ContentInfo:
    """Recursos de terceros, SRI, contenido mixto, formularios y links ``_blank``."""
    soup = make_soup(html)
    https = page_url.lower().startswith("https://")
    site = registrable_domain(urlparse(page_url).hostname or "")
    third_party: dict[str, None] = {}
    scripts_no_sri: list[str] = []
    styles_no_sri: list[str] = []
    mixed: list[str] = []
    for tag_name, attr in _SRC_ATTRS:
        for tag in soup.find_all(tag_name):
            raw = tag.get(attr)
            if not isinstance(raw, str) or not raw.strip():
                continue
            if tag_name == "link" and not _rel_has(
                tag, "stylesheet", "preload", "modulepreload", "icon"
            ):
                continue
            url = urljoin(page_url, raw.strip())
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                continue
            if https and parsed.scheme == "http":
                mixed.append(url)
            if _same_site(parsed.hostname, site):
                continue
            third_party.setdefault(parsed.hostname or "", None)
            if tag.get("integrity"):
                continue
            if tag_name == "script":
                scripts_no_sri.append(url)
            elif tag_name == "link" and _rel_has(tag, "stylesheet"):
                styles_no_sri.append(url)
    blank = [
        a
        for a in soup.find_all("a", target=True)
        if str(a.get("target")).lower() == "_blank" and not _rel_has(a, "noopener", "noreferrer")
    ]
    return ContentInfo(
        third_party=tuple(sorted(third_party))[:MAX_ITEMS],
        scripts_without_sri=tuple(dict.fromkeys(scripts_no_sri)),
        styles_without_sri=tuple(dict.fromkeys(styles_no_sri)),
        mixed=tuple(dict.fromkeys(mixed))[:MAX_ITEMS],
        forms=analyze_forms(soup, page_url, site),
        blank_without_noopener=len(blank),
    )  # fmt: skip


def analyze_forms(soup: BeautifulSoup, page_url: str, site: str) -> FormsInfo:
    """Cantidad de formularios, de login, ``action`` inseguros o externos y autocomplete."""
    forms = soup.find_all("form")
    login = 0
    insecure_urls: list[str] = []
    external_urls: list[str] = []
    for form in forms:
        if form.find("input", attrs={"type": "password"}) is not None:
            login += 1
        action = str(form.get("action") or "").strip()
        target = urljoin(page_url, action) if action else page_url
        parsed = urlparse(target)
        if parsed.scheme == "http":
            insecure_urls.append(target)
        if parsed.scheme in ("http", "https") and not _same_site(parsed.hostname, site):
            external_urls.append(target)
    passwords = soup.find_all("input", attrs={"type": "password"})
    autocomplete = sum(
        1 for field in passwords if str(field.get("autocomplete", "")).lower() in ("", "on")
    )
    return FormsInfo(
        count=len(forms),
        login=login,
        insecure_actions=tuple(dict.fromkeys(insecure_urls)),
        external_actions=tuple(dict.fromkeys(external_urls)),
        password_autocomplete=autocomplete,
    )


# --- Superficie visible -------------------------------------------------------------


def find_surface(html: str, page_url: str, sans: Sequence[str] = ()) -> SurfaceInfo:
    """Subdominios (SANs y contenido) y endpoints sensibles referenciados en el HTML/JS."""
    host = (urlparse(page_url).hostname or "").lower()
    site = registrable_domain(host)
    subdomains: dict[str, None] = {}
    if site:
        pattern = re.compile(
            r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+" + re.escape(site) + r")\b", re.I
        )
        for name in (*sans, *pattern.findall(html)):
            name = name.lower().lstrip(".")
            wildcard = name.startswith("*")
            if not wildcard and name.endswith(site) and name not in (host, site, f"www.{site}"):
                subdomains.setdefault(name, None)
    paths = list(_PATH_RE.findall(html))
    for match in _ABS_URL_RE.finditer(html):
        if _same_site(urlparse(match.group(0)).hostname, site) and match.group(1):
            paths.append(match.group(1))
    endpoints: dict[str, None] = {}
    for path in paths:
        segments = [s.lower() for s in path.split("/") if s]
        if any(s in SURFACE_SEGMENTS for s in segments) and not path.startswith("//"):
            endpoints.setdefault(path.rstrip("/") or "/", None)
    return SurfaceInfo(
        subdomains=tuple(sorted(subdomains))[:MAX_ITEMS],
        endpoints=tuple(sorted(endpoints))[:MAX_ITEMS],
    )  # fmt: skip


# --- Ensamblado ---------------------------------------------------------------------


def build_security(
    *,
    page_url: str,
    headers: Mapping[str, str],
    html: str,
    set_cookies: Sequence[str] = (),
    dns: DnsRecords | None = None,
    robots_text: str | None = None,
    robots_checked: bool = False,
    security_txt: str | None = None,
    security_txt_checked: bool = False,
    sitemap: bool | None = None,
    http_redirect: HttpRedirect | None = None,
    sans: Sequence[str] = (),
    now: datetime | None = None,
) -> SecurityResult:
    """Arma el ``SecurityResult`` con todo lo que se pudo obtener."""
    https = page_url.lower().startswith("https://")
    files = FilesInfo(
        security_txt=parse_security_txt(security_txt, now) if security_txt else None,
        security_txt_checked=security_txt_checked,
        robots=(robots_text is not None) if robots_checked else None,
        robots_sensitive=sensitive_robots_paths(robots_text) if robots_text else (),
        sitemap=sitemap,
    )
    return SecurityResult(
        https=https,
        headers=analyze_headers(headers, https),
        leaks=find_leaks(headers, html),
        cookies=parse_cookies(set_cookies),
        email=analyze_email(dns) if dns is not None and dns.error is None else None,
        files=files,
        http_redirect=http_redirect,
        content=analyze_content(html, page_url),
        surface=find_surface(html, page_url, sans),
    )

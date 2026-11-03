"""Modelos de datos inmutables que comparten analizadores, crawler y reporte.

Todos los campos son datos o códigos estables (por ejemplo ``"site"``, ``"high"``);
nunca texto traducido. La traducción ocurre únicamente en ``report.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

SiteKind = Literal["site", "app"]
Confidence = Literal["low", "medium", "high"]
PageSource = Literal["sitemap", "crawl"]
Severity = Literal["critical", "high", "medium", "low", "info"]

SEVERITY_ORDER: tuple[Severity, ...] = ("critical", "high", "medium", "low", "info")


@dataclass(frozen=True)
class Technology:
    """Una tecnología detectada, su categoría y la versión si es visible."""

    name: str
    category: str
    version: str | None = None


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


# --- De qué trata ------------------------------------------------------------------


@dataclass(frozen=True)
class CategorySignal:
    """Una pista que sumó puntos a una categoría (``reason`` es un dato, p. ej. ``kw:cart``)."""

    category: str
    reason: str
    weight: int


@dataclass(frozen=True)
class CategoryResult:
    """Categoría del sitio (``unknown`` si la confianza no alcanza) y sus señales."""

    code: str
    confidence: Confidence
    score: int = 0
    signals: tuple[CategorySignal, ...] = ()


@dataclass(frozen=True)
class TopicResult:
    """Descripción concreta del sitio, su categoría, nombre y pistas de país."""

    description: str
    category: CategoryResult
    site_name: str = ""
    description_source: str = ""
    country: str | None = None
    country_source: str | None = None
    pages_analyzed: int = 1


# --- Infraestructura ---------------------------------------------------------------


@dataclass(frozen=True)
class Redirect:
    """Un salto de la cadena de redirecciones."""

    url: str
    status: int


@dataclass(frozen=True)
class AsnInfo:
    """Sistema autónomo de una IP según Team Cymru."""

    asn: int
    org: str = ""
    country: str = ""
    prefix: str = ""
    registry: str = ""


@dataclass(frozen=True)
class DnsRecords:
    """Registros DNS crudos. ``error`` se completa si todas las consultas fallaron."""

    a: tuple[str, ...] = ()
    aaaa: tuple[str, ...] = ()
    cname: Mapping[str, str] = field(default_factory=dict)
    ns: tuple[str, ...] = ()
    mx: tuple[str, ...] = ()
    txt: tuple[str, ...] = ()
    caa: tuple[str, ...] = ()
    dmarc: tuple[str, ...] = ()
    dkim: tuple[str, ...] = ()
    mta_sts: tuple[str, ...] = ()
    bimi: tuple[str, ...] = ()
    ptr: Mapping[str, str] = field(default_factory=dict)
    asn: Mapping[str, AsnInfo] = field(default_factory=dict)
    failed: int = 0
    error: str | None = None
    unanswered: tuple[str, ...] = ()


@dataclass(frozen=True)
class CdnMatch:
    """Un CDN, WAF o hosting inferido y la evidencia que lo delató."""

    name: str
    kind: str
    evidence: str


@dataclass(frozen=True)
class RdapInfo:
    """Datos de registro del dominio (solo con ``--rdap``)."""

    domain: str
    registrar: str = ""
    created: str | None = None
    expires: str | None = None
    age_days: int | None = None


@dataclass(frozen=True)
class InfraResult:
    """IPs, red, CDN/WAF, registros DNS y redirecciones del objetivo."""

    ipv4: tuple[str, ...] = ()
    ipv6: tuple[str, ...] = ()
    connected_ip: str | None = None
    ptr: Mapping[str, str] = field(default_factory=dict)
    asn: Mapping[str, AsnInfo] = field(default_factory=dict)
    cdn: tuple[CdnMatch, ...] = ()
    dns: DnsRecords | None = None
    rdap: RdapInfo | None = None


# --- TLS ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TlsResult:
    """Certificado y parámetros negociados en una conexión TLS estándar."""

    subject: str = ""
    issuer: str = ""
    sans: tuple[str, ...] = ()
    not_before: str | None = None
    not_after: str | None = None
    days_left: int | None = None
    protocol: str | None = None
    cipher: str | None = None
    verified: bool = False
    verify_error: str | None = None
    peer_ip: str | None = None


# --- Seguridad visible -------------------------------------------------------------


@dataclass(frozen=True)
class HeaderCheck:
    """Un security header evaluado: puntos obtenidos sobre el máximo."""

    name: str
    present: bool
    points: int
    max_points: int
    value: str | None = None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class HeadersReport:
    """Security headers con puntaje y nota (A–F)."""

    checks: tuple[HeaderCheck, ...] = ()
    score: int = 0
    max_score: int = 0
    grade: str = "F"
    extra: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Leak:
    """Dato que revela software o versiones (``source`` es header, meta o comentario)."""

    source: str
    value: str


@dataclass(frozen=True)
class CookieInfo:
    """Atributos de seguridad de una cookie."""

    name: str
    secure: bool
    httponly: bool
    samesite: str | None
    prefix: str | None = None


@dataclass(frozen=True)
class EmailPosture:
    """SPF, DMARC, DKIM, MTA-STS y BIMI según DNS."""

    has_mx: bool = False
    unanswered: tuple[str, ...] = ()
    spf: str | None = None
    spf_all: str | None = None
    spf_records: int = 0
    dmarc: str | None = None
    dmarc_policy: str | None = None
    dkim_selectors: tuple[str, ...] = ()
    mta_sts: bool = False
    bimi: bool = False


@dataclass(frozen=True)
class SecurityTxt:
    """Contenido relevante de ``/.well-known/security.txt``."""

    contacts: tuple[str, ...] = ()
    expires: str | None = None
    expired: bool = False


@dataclass(frozen=True)
class FilesInfo:
    """``security.txt``, ``robots.txt`` y sitemap. ``None`` = no se pudo comprobar."""

    security_txt: SecurityTxt | None = None
    security_txt_checked: bool = False
    robots: bool | None = None
    robots_sensitive: tuple[str, ...] = ()
    sitemap: bool | None = None


@dataclass(frozen=True)
class HttpRedirect:
    """Resultado de pedir la versión ``http://`` del sitio."""

    redirects_to_https: bool
    status: int | None = None
    final_url: str | None = None


@dataclass(frozen=True)
class FormsInfo:
    """Formularios de la home y sus atributos de riesgo."""

    count: int = 0
    login: int = 0
    insecure_actions: tuple[str, ...] = ()
    external_actions: tuple[str, ...] = ()
    password_autocomplete: int = 0


@dataclass(frozen=True)
class ContentInfo:
    """Recursos externos, SRI, contenido mixto, formularios y links ``_blank``."""

    third_party: tuple[str, ...] = ()
    scripts_without_sri: tuple[str, ...] = ()
    styles_without_sri: tuple[str, ...] = ()
    mixed: tuple[str, ...] = ()
    forms: FormsInfo = field(default_factory=FormsInfo)
    blank_without_noopener: int = 0


@dataclass(frozen=True)
class SurfaceInfo:
    """Subdominios y endpoints referenciados en el contenido (no se sondean)."""

    subdomains: tuple[str, ...] = ()
    endpoints: tuple[str, ...] = ()


@dataclass(frozen=True)
class SecurityResult:
    """Postura de seguridad visible del sitio."""

    https: bool
    headers: HeadersReport
    leaks: tuple[Leak, ...] = ()
    cookies: tuple[CookieInfo, ...] = ()
    email: EmailPosture | None = None
    files: FilesInfo = field(default_factory=FilesInfo)
    http_redirect: HttpRedirect | None = None
    content: ContentInfo = field(default_factory=ContentInfo)
    surface: SurfaceInfo = field(default_factory=SurfaceInfo)


@dataclass(frozen=True)
class Finding:
    """Una observación priorizada. ``params`` completa el título traducido."""

    id: str
    severity: Severity
    evidence: str = ""
    params: Mapping[str, object] = field(default_factory=dict)


# --- Resultado completo ------------------------------------------------------------


@dataclass(frozen=True)
class AnalysisResult:
    """Resultado completo del análisis de una URL.

    ``unavailable`` mapea un bloque (``infrastructure``, ``tls``...) al código del
    motivo por el que no se pudo completar; el resto del reporte sale igual.
    """

    url: str
    final_url: str
    domain: str
    summary: str
    site_type: SiteTypeResult
    pages: PageCount | None
    technologies: tuple[Technology, ...]
    keywords: tuple[str, ...]
    site_lang: str
    status_code: int = 200
    server: str | None = None
    elapsed_ms: int = 0
    details: dict[str, str] = field(default_factory=dict)
    topic: TopicResult | None = None
    redirects: tuple[Redirect, ...] = ()
    infra: InfraResult | None = None
    tls: TlsResult | None = None
    security: SecurityResult | None = None
    findings: tuple[Finding, ...] = ()
    unavailable: Mapping[str, str] = field(default_factory=dict)
    scanned_at: str = ""
    brief: bool = False

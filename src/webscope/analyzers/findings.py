"""Catálogo declarativo de hallazgos priorizados.

Cada regla tiene un ``id`` estable, una severidad y una función pura que devuelve
``(evidencia, parámetros)`` si la observación aplica. El título y la recomendación
se traducen en ``report.py`` con las claves ``finding.<id>.title`` y
``finding.<id>.rec`` de ``i18n.py``.

Son observaciones de reconocimiento pasivo, no un escáner de vulnerabilidades: el
texto usa lenguaje prudente ("posible", "no se observó").
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

from webscope.analyzers.tls import is_expired, is_expiring
from webscope.models import (
    SEVERITY_ORDER,
    EmailPosture,
    Finding,
    InfraResult,
    SecurityResult,
    Severity,
    Technology,
    TlsResult,
)

Hit = tuple[str, dict[str, object]] | None


@dataclass(frozen=True)
class FindingContext:
    """Todo lo que las reglas pueden mirar."""

    final_url: str
    security: SecurityResult | None = None
    tls: TlsResult | None = None
    infra: InfraResult | None = None
    technologies: tuple[Technology, ...] = ()

    @property
    def https(self) -> bool:
        return self.final_url.lower().startswith("https://")


@dataclass(frozen=True)
class Rule:
    """Una regla del catálogo."""

    id: str
    severity: Severity
    check: Callable[[FindingContext], Hit]


def _short(items: tuple[str, ...] | list[str], limit: int = 3) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" (+{len(items) - limit})" if len(items) > limit else "")


def _hosts(urls: tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(urlparse(u).hostname or u for u in urls))


def _header(ctx: FindingContext, name: str) -> tuple[bool, tuple[str, ...], str | None]:
    if ctx.security is None:
        return True, (), None
    check = next(c for c in ctx.security.headers.checks if c.name == name)
    return check.present, check.issues, check.value


# --- TLS y HTTPS --------------------------------------------------------------------


def _tls_invalid(ctx: FindingContext) -> Hit:
    tls = ctx.tls
    if tls and not tls.verified and not is_expired(tls):
        return tls.verify_error or "verify failed", {}
    return None


def _tls_expired(ctx: FindingContext) -> Hit:
    tls = ctx.tls
    if tls and is_expired(tls):
        return f"notAfter {tls.not_after}", {"date": tls.not_after or "?"}
    return None


def _tls_expiring(ctx: FindingContext) -> Hit:
    tls = ctx.tls
    if tls and is_expiring(tls):
        return f"notAfter {tls.not_after}", {"days": tls.days_left}
    return None


def _tls_old(ctx: FindingContext) -> Hit:
    tls = ctx.tls
    if tls and tls.protocol in ("TLSv1", "TLSv1.1", "SSLv3"):
        return tls.protocol, {"protocol": tls.protocol}
    return None


def _https_missing(ctx: FindingContext) -> Hit:
    return (ctx.final_url, {}) if not ctx.https else None


def _http_no_redirect(ctx: FindingContext) -> Hit:
    probe = ctx.security.http_redirect if ctx.security else None
    if ctx.https and probe is not None and not probe.redirects_to_https:
        return f"http:// -> {probe.status} {probe.final_url or ''}".strip(), {}
    return None


# --- Headers ------------------------------------------------------------------------


def _hsts_missing(ctx: FindingContext) -> Hit:
    present, _, _ = _header(ctx, "Strict-Transport-Security")
    return ("Strict-Transport-Security: -", {}) if ctx.https and not present else None


def _hsts_weak(ctx: FindingContext) -> Hit:
    present, issues, value = _header(ctx, "Strict-Transport-Security")
    return (f"Strict-Transport-Security: {value}", {}) if present and issues else None


def _csp_missing(ctx: FindingContext) -> Hit:
    present, _, _ = _header(ctx, "Content-Security-Policy")
    return ("Content-Security-Policy: -", {}) if not present else None


def _csp_unsafe(ctx: FindingContext) -> Hit:
    present, issues, _ = _header(ctx, "Content-Security-Policy")
    if present and issues:
        return ", ".join(issues), {"issues": ", ".join(issues)}
    return None


def _simple_missing(name: str) -> Callable[[FindingContext], Hit]:
    def check(ctx: FindingContext) -> Hit:
        present, _, _ = _header(ctx, name)
        return (f"{name}: -", {}) if not present else None

    return check


# --- Fugas --------------------------------------------------------------------------


def _leak(*sources: str) -> Callable[[FindingContext], Hit]:
    def check(ctx: FindingContext) -> Hit:
        leaks = [
            leak for leak in (ctx.security.leaks if ctx.security else ()) if leak.source in sources
        ]
        if not leaks:
            return None
        values = [leak.value for leak in leaks]
        return " · ".join(values)[:120], {"value": values[0][:60], "count": len(values)}

    return check  # fmt: skip


# --- Cookies ------------------------------------------------------------------------


def _cookies(attr: str) -> Callable[[FindingContext], Hit]:
    def check(ctx: FindingContext) -> Hit:
        if ctx.security is None or (attr == "secure" and not ctx.https):
            return None
        if attr == "samesite":
            names = [c.name for c in ctx.security.cookies if not c.samesite]
        else:
            names = [c.name for c in ctx.security.cookies if not getattr(c, attr)]
        return (_short(names), {"count": len(names)}) if names else None

    return check


# --- Email --------------------------------------------------------------------------


def _email(ctx: FindingContext) -> EmailPosture | None:
    return ctx.security.email if ctx.security else None


def _spf_missing(ctx: FindingContext) -> Hit:
    email = _email(ctx)
    if email and not email.spf and "txt" not in email.unanswered:
        return "TXT v=spf1: -", {}
    return None


def _spf_permissive(ctx: FindingContext) -> Hit:
    email = _email(ctx)
    return (email.spf or "", {}) if email and email.spf_all == "+all" else None


def _spf_neutral(ctx: FindingContext) -> Hit:
    email = _email(ctx)
    return (email.spf or "", {}) if email and email.spf_all == "?all" else None


def _spf_multiple(ctx: FindingContext) -> Hit:
    email = _email(ctx)
    if email and email.spf_records > 1:
        return f"{email.spf_records} x v=spf1", {"count": email.spf_records}
    return None


def _dmarc_missing(ctx: FindingContext) -> Hit:
    email = _email(ctx)
    if email and not email.dmarc and "dmarc" not in email.unanswered:
        return "_dmarc TXT: -", {}
    return None


def _dmarc_none(ctx: FindingContext) -> Hit:
    email = _email(ctx)
    return (email.dmarc or "", {}) if email and email.dmarc_policy == "none" else None


def _dkim_not_found(ctx: FindingContext) -> Hit:
    email = _email(ctx)
    if email and email.has_mx and not email.dkim_selectors and "dkim" not in email.unanswered:
        return "selectors: default, google, selector1, selector2, k1...", {}
    return None


# --- Archivos -----------------------------------------------------------------------


def _sectxt_missing(ctx: FindingContext) -> Hit:
    files = ctx.security.files if ctx.security else None
    if files and files.security_txt_checked and files.security_txt is None:
        return "/.well-known/security.txt: -", {}
    return None


def _sectxt_expired(ctx: FindingContext) -> Hit:
    files = ctx.security.files if ctx.security else None
    sec = files.security_txt if files else None
    return (f"Expires: {sec.expires}", {}) if sec and sec.expired else None


def _robots_sensitive(ctx: FindingContext) -> Hit:
    paths = list(ctx.security.files.robots_sensitive) if ctx.security else []
    return (_short(paths, 5), {"count": len(paths)}) if paths else None


# --- Contenido ----------------------------------------------------------------------


def _mixed(ctx: FindingContext) -> Hit:
    mixed = list(ctx.security.content.mixed) if ctx.security else []
    return (_short(mixed, 2), {"count": len(mixed)}) if mixed and ctx.https else None


def _no_sri(ctx: FindingContext) -> Hit:
    if ctx.security is None:
        return None
    content = ctx.security.content
    urls = content.scripts_without_sri + content.styles_without_sri
    if not urls:
        return None
    return _short(urls, 2), {
        "count": len(urls),
        "scripts": len(content.scripts_without_sri),
        "hosts": _short(_hosts(urls), 2),
    }


def _form_insecure(ctx: FindingContext) -> Hit:
    urls = list(ctx.security.content.forms.insecure_actions) if ctx.security else []
    return (_short(urls, 2), {"count": len(urls)}) if urls and ctx.https else None


def _password_http(ctx: FindingContext) -> Hit:
    forms = ctx.security.content.forms if ctx.security else None
    if forms and forms.login and not ctx.https:
        return ctx.final_url, {"count": forms.login}
    return None


def _form_external(ctx: FindingContext) -> Hit:
    urls = list(ctx.security.content.forms.external_actions) if ctx.security else []
    return (_short(_hosts(tuple(urls)), 3), {"count": len(urls)}) if urls else None


def _password_autocomplete(ctx: FindingContext) -> Hit:
    count = ctx.security.content.forms.password_autocomplete if ctx.security else 0
    return (f'input type="password" x{count}', {"count": count}) if count else None


def _blank_noopener(ctx: FindingContext) -> Hit:
    count = ctx.security.content.blank_without_noopener if ctx.security else 0
    return (f'target="_blank" x{count}', {"count": count}) if count else None


# --- Superficie e inventario --------------------------------------------------------


def _endpoints(ctx: FindingContext) -> Hit:
    endpoints = list(ctx.security.surface.endpoints) if ctx.security else []
    return (_short(endpoints, 5), {"count": len(endpoints)}) if endpoints else None


def _tech_versions(ctx: FindingContext) -> Hit:
    versioned = [f"{t.name} {t.version}" for t in ctx.technologies if t.version]
    return (_short(versioned, 5), {"count": len(versioned)}) if versioned else None


def _no_caa(ctx: FindingContext) -> Hit:
    dns = ctx.infra.dns if ctx.infra else None
    unanswered = dns.unanswered if dns is not None else ()
    if dns is not None and dns.error is None and dns.a and not dns.caa and "caa" not in unanswered:
        return "CAA: -", {}
    return None


RULES: Final[tuple[Rule, ...]] = (
    Rule("TLS-EXPIRED", "high", _tls_expired),
    Rule("TLS-CERT-INVALID", "high", _tls_invalid),
    Rule("HTTPS-MISSING", "high", _https_missing),
    Rule("FORM-PASSWORD-HTTP", "high", _password_http),
    Rule("FORM-INSECURE-ACTION", "high", _form_insecure),
    Rule("SPF-PERMISSIVE", "high", _spf_permissive),
    Rule("TLS-EXPIRING", "medium", _tls_expiring),
    Rule("TLS-OLD-PROTOCOL", "medium", _tls_old),
    Rule("HTTP-NO-REDIRECT", "medium", _http_no_redirect),
    Rule("HDR-HSTS-MISSING", "medium", _hsts_missing),
    Rule("HDR-CSP-MISSING", "medium", _csp_missing),
    Rule("CONTENT-MIXED", "medium", _mixed),
    Rule("COOKIE-NO-SECURE", "medium", _cookies("secure")),
    Rule("DMARC-MISSING", "medium", _dmarc_missing),
    Rule("HDR-HSTS-WEAK", "low", _hsts_weak),
    Rule("HDR-CSP-UNSAFE", "low", _csp_unsafe),
    Rule("HDR-XFO-MISSING", "low", _simple_missing("X-Frame-Options")),
    Rule("HDR-XCTO-MISSING", "low", _simple_missing("X-Content-Type-Options")),
    Rule("LEAK-SERVER-VERSION", "low", _leak("server")),
    Rule("LEAK-POWERED-BY", "low", _leak("x-powered-by")),
    Rule("LEAK-ASPNET-VERSION", "low", _leak("x-aspnet-version", "x-aspnetmvc-version")),
    Rule("COOKIE-NO-HTTPONLY", "low", _cookies("httponly")),
    Rule("COOKIE-NO-SAMESITE", "low", _cookies("samesite")),
    Rule("SPF-MISSING", "low", _spf_missing),
    Rule("SPF-NEUTRAL", "low", _spf_neutral),
    Rule("SPF-MULTIPLE", "low", _spf_multiple),
    Rule("DMARC-NONE", "low", _dmarc_none),
    Rule("SECTXT-EXPIRED", "low", _sectxt_expired),
    Rule("HDR-REFERRER-MISSING", "info", _simple_missing("Referrer-Policy")),
    Rule("HDR-PERMISSIONS-MISSING", "info", _simple_missing("Permissions-Policy")),
    Rule("LEAK-GENERATOR", "info", _leak("meta-generator", "x-generator")),
    Rule("LEAK-HTML-COMMENT", "info", _leak("html-comment")),
    Rule("DKIM-NOT-FOUND", "info", _dkim_not_found),
    Rule("SECTXT-MISSING", "info", _sectxt_missing),
    Rule("ROBOTS-SENSITIVE", "info", _robots_sensitive),
    Rule("CONTENT-NO-SRI", "info", _no_sri),
    Rule("FORM-EXTERNAL-ACTION", "info", _form_external),
    Rule("FORM-PASSWORD-AUTOCOMPLETE", "info", _password_autocomplete),
    Rule("LINK-NO-NOOPENER", "info", _blank_noopener),
    Rule("SURFACE-ENDPOINTS", "info", _endpoints),
    Rule("TECH-VERSIONS", "info", _tech_versions),
    Rule("DNS-NO-CAA", "info", _no_caa),
)


def evaluate(ctx: FindingContext, rules: tuple[Rule, ...] = RULES) -> tuple[Finding, ...]:
    """Hallazgos que aplican, ordenados por severidad y luego por orden del catálogo."""
    findings: list[Finding] = []
    for rule in rules:
        try:
            hit = rule.check(ctx)
        except Exception:  # una regla rota no debe tumbar el reporte
            continue
        if hit is not None:
            evidence, params = hit
            findings.append(Finding(rule.id, rule.severity, evidence, params))
    return tuple(sorted(findings, key=lambda f: SEVERITY_ORDER.index(f.severity)))

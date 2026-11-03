"""Presentación del resultado: texto con ``rich``, Markdown o JSON estable.

Es el único lugar donde los códigos de los analizadores (``site``, ``high``,
``sitemap``, ids de hallazgos...) se convierten en texto del idioma de la interfaz.
``build_blocks()`` arma las filas de cada bloque una sola vez; la salida de texto y
la de Markdown solo cambian el formato.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from webscope import __version__
from webscope.analyzers.tech import CATEGORY_ORDER
from webscope.analyzers.tls import is_expired
from webscope.dnsinfo import is_null_mx
from webscope.fetcher import FetchError
from webscope.i18n import t
from webscope.models import (
    AnalysisResult,
    Finding,
    InfraResult,
    PageCount,
    SecurityResult,
    SiteTypeResult,
    Technology,
    TlsResult,
    TopicResult,
)

SCHEMA_VERSION = "2.0"
MAX_WIDTH = 100
LABEL_STYLE = "bold cyan"
SUMMARY_CHARS = 200
SEVERITY_STYLES = {
    "critical": "bold white on red",
    "high": "bold red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
}
_HEADER_SHORT = {
    "Strict-Transport-Security": "HSTS",
    "Content-Security-Policy": "CSP",
}

Row = tuple[str, str]


@dataclass(frozen=True)
class Block:
    """Un bloque del reporte: clave estable, título traducido y filas ``(etiqueta, valor)``."""

    key: str
    title: str
    rows: tuple[Row, ...]


# --- Formateo de valores ------------------------------------------------------------


def format_pages(pages: PageCount | None, lang: str) -> str:
    """``~48 (vía sitemap.xml)``, ``al menos 50 (vía rastreo de links)``..."""
    if pages is None:
        return t("pages.skipped", lang)
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


def _tech_label(tech: Technology) -> str:
    return f"{tech.name} {tech.version}" if tech.version else tech.name


def format_technologies(technologies: tuple[Technology, ...], lang: str) -> str:
    """Tecnologías agrupadas por categoría: ``HTML, CSS · WordPress 6.4 · jQuery 3.6``."""
    groups = [
        ", ".join(_tech_label(tech) for tech in technologies if tech.category == category)
        for category in CATEGORY_ORDER
    ]
    return " · ".join(group for group in groups if group) or t("tech.none", lang)


def format_summary(result: AnalysisResult, lang: str) -> str:
    """``<Categoría> — <descripción>``; solo la descripción si la categoría es indeterminada."""
    description = result.summary
    topic = result.topic
    if topic is None or topic.category.code == "unknown":
        return description or t("topic.none", lang)
    label = t(f"category.{topic.category.code}", lang)
    if not description:
        return label
    text = f"{label} — {description}"
    return text if len(text) <= SUMMARY_CHARS else text[: SUMMARY_CHARS - 1].rstrip() + "…"


def format_error(error: FetchError, lang: str) -> str:
    """Mensaje de error traducido, sin stack trace."""
    return t(f"error.{error.code}", lang, **error.params)


def format_event(code: str, lang: str, **params: object) -> str:
    """Texto de un evento de progreso (para ``--verbose``)."""
    return t(f"event.{code}", lang, **params)


def format_unavailable(reason: str, lang: str) -> str:
    """``no disponible (DNS sin respuesta)``."""
    return t("unavailable", lang, reason=t(f"reason.{reason}", lang))


def finding_title(finding: Finding, lang: str) -> str:
    """Título traducido del hallazgo con sus parámetros."""
    return t(f"finding.{finding.id}.title", lang, **finding.params)


def finding_recommendation(finding: Finding, lang: str) -> str:
    """Recomendación corta traducida del hallazgo."""
    return t(f"finding.{finding.id}.rec", lang)


def _short(items: Sequence[str], limit: int = 3) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" (+{len(items) - limit})" if len(items) > limit else "")


def _header_line(result: AnalysisResult, lang: str) -> str:
    hops = len(result.redirects)
    if hops == 0:
        return result.final_url
    note = t("header.redirect_one", lang) if hops == 1 else t("header.redirects", lang, count=hops)
    return f"{result.final_url} ({note})"


# --- Bloques ------------------------------------------------------------------------


def _site_row(topic: TopicResult | None, result: AnalysisResult, lang: str) -> Row | None:
    if topic is None:
        return None
    name = topic.site_name or result.domain
    if topic.country:
        source = t(f"country.{topic.country_source}", lang)
        value = t(
            "site.country",
            lang,
            name=name,
            site_lang=result.site_lang,
            country=topic.country,
            source=source,
        )
    else:
        value = t("site.value", lang, name=name, site_lang=result.site_lang)
    return t("label.site", lang), value


def general_rows(result: AnalysisResult, lang: str, verbose: bool = False) -> list[Row]:
    """Filas del bloque GENERAL."""
    keywords = ", ".join(result.keywords) or t("keywords.none", lang)
    rows: list[Row] = [
        (t("label.topic", lang), format_summary(result, lang)),
        (t("label.type", lang), format_site_type(result.site_type, lang)),
    ]
    site = _site_row(result.topic, result, lang)
    if site:
        rows.append(site)
    rows += [
        (t("label.pages", lang), format_pages(result.pages, lang)),
        (t("label.tech", lang), format_technologies(result.technologies, lang)),
        (t("label.keywords", lang), keywords),
    ]
    topic = result.topic
    if verbose and topic is not None:
        category = t(
            "category.value",
            lang,
            name=t(f"category.{topic.category.code}", lang),
            confidence=t(f"confidence.{topic.category.confidence}", lang),
        )
        signals = ", ".join(f"+{s.weight} {s.reason}" for s in topic.category.signals[:8])
        rows += [
            (t("label.category", lang), category),
            (t("label.category_signals", lang), signals or t("value.none", lang)),
            (t("label.description_source", lang), topic.description_source or "-"),
            (t("label.pages_analyzed", lang), str(topic.pages_analyzed)),
        ]
    return rows


def _ips(infra: InfraResult, lang: str) -> str:
    v4 = [f"{ip} ({t('ip.v4', lang)})" for ip in infra.ipv4[:2]]
    v6 = [f"{ip} ({t('ip.v6', lang)})" for ip in infra.ipv6[:2]]
    extra = len(infra.ipv4) + len(infra.ipv6) - len(v4) - len(v6)
    text = " · ".join(v4 + v6)
    return text + (f" (+{extra})" if extra > 0 else "")


def infrastructure_rows(result: AnalysisResult, lang: str, verbose: bool = False) -> list[Row]:
    """Filas del bloque INFRAESTRUCTURA."""
    infra = result.infra or InfraResult()
    dns = infra.dns
    none = t("value.none", lang)
    dns_down = result.unavailable.get("dns")
    rows: list[Row] = []
    ips = _ips(infra, lang)
    if ips:
        rows.append((t("label.ips", lang), ips))
    if infra.connected_ip and infra.connected_ip not in (*infra.ipv4, *infra.ipv6):
        rows.append((t("label.connected_ip", lang), infra.connected_ip))
    if dns_down:
        rows.append((t("label.dns", lang), format_unavailable(dns_down, lang)))
    if infra.ptr:
        rows.append((t("label.ptr", lang), _short(list(dict.fromkeys(infra.ptr.values())))))
    networks = {
        info.asn: t(
            "network.asn", lang, asn=info.asn, org=info.org or "?", country=info.country or "?"
        )
        for info in infra.asn.values()
    }
    if networks:
        rows.append((t("label.network", lang), " · ".join(networks.values())))
    cdn = ", ".join(dict.fromkeys(m.name for m in infra.cdn))
    rows.append((t("label.cdn", lang), cdn or t("value.not_detected", lang)))
    if dns is not None and not dns_down:
        rows.append((t("label.ns", lang), ", ".join(dns.ns[:4]) or none))
        mx_hosts = [value.partition(" ")[2] or value for value in dns.mx]
        if any(is_null_mx(value) for value in dns.mx):
            mx = t("email.null_mx", lang)
        elif len(mx_hosts) > 1:
            mx = t("mx.more", lang, host=mx_hosts[0], more=len(mx_hosts) - 1)
        else:
            mx = mx_hosts[0] if mx_hosts else t("email.no_mx", lang)
        rows.append((t("label.mx", lang), mx))
    if infra.rdap is not None:
        rdap = infra.rdap
        years = (rdap.age_days or 0) // 365
        rows.append(
            (
                t("label.rdap", lang),
                t(
                    "rdap.value",
                    lang,
                    registrar=rdap.registrar or "?",
                    created=rdap.created or "?",
                    years=years,
                    expires=rdap.expires or "?",
                ),
            )
        )
    elif "rdap" in result.unavailable:
        rows.append((t("label.rdap", lang), format_unavailable(result.unavailable["rdap"], lang)))
    if verbose:
        chain = [f"{r.status} {r.url}" for r in result.redirects] + [result.final_url]
        rows.append((t("label.redirect_chain", lang), " → ".join(chain)))
        if dns is not None:
            cnames = [f"{name} → {target}" for name, target in dns.cname.items()]
            rows.append((t("label.cname", lang), "; ".join(cnames) or none))
            rows.append((t("label.txt", lang), _short([v[:60] for v in dns.txt], 4) or none))
            rows.append((t("label.caa", lang), ", ".join(dns.caa) or none))
        if infra.cdn:
            evidence = "; ".join(f"{m.name}: {m.evidence}" for m in infra.cdn)
            rows.append((t("label.cdn_evidence", lang), evidence))
    return rows


def tls_rows(tls: TlsResult, lang: str, verbose: bool = False) -> list[Row]:
    """Filas del bloque TLS."""
    issuer = tls.issuer or "?"
    protocol = (tls.protocol or "?").replace("TLSv", "TLS ")
    if is_expired(tls):
        value = t(
            "tls.expired", lang, issuer=issuer, days=abs(tls.days_left or 0), protocol=protocol
        )
    else:
        days = tls.days_left if tls.days_left is not None else "?"
        value = t("tls.value", lang, issuer=issuer, days=days, protocol=protocol)
    if not tls.verified:
        value += " · " + t("tls.unverified", lang, error=tls.verify_error or "?")
    rows: list[Row] = [
        (t("label.certificate", lang), value),
        (t("label.sans", lang), _short(list(tls.sans), 4) or t("value.none", lang)),
    ]
    if verbose:
        rows += [
            (t("label.subject", lang), tls.subject or "?"),
            (
                t("label.validity", lang),
                t("tls.validity", lang, start=tls.not_before or "?", end=tls.not_after or "?"),
            ),
            (t("label.cipher", lang), tls.cipher or "?"),
        ]
    return rows


def _yes_no(value: bool | None, lang: str) -> str:
    if value is None:
        return t("value.unknown", lang)
    return t("value.yes" if value else "value.no", lang)


def _email_value(security: SecurityResult, result: AnalysisResult, lang: str) -> str:
    email = security.email
    if email is None:
        reason = result.unavailable.get("dns", "error")
        return format_unavailable(reason, lang)
    unknown = t("value.unknown", lang)
    if email.spf:
        spf = t("email.ok", lang) + (f" ({email.spf_all})" if email.spf_all else "")
    else:
        spf = unknown if "txt" in email.unanswered else t("email.missing", lang)
    if email.dmarc_policy == "none":
        dmarc = t("email.monitoring", lang)
    elif email.dmarc:
        dmarc = f"p={email.dmarc_policy or '?'}"
    else:
        dmarc = unknown if "dmarc" in email.unanswered else t("email.missing", lang)
    parts = [t("email.spf", lang, value=spf), t("email.dmarc", lang, value=dmarc)]
    if email.dkim_selectors:
        parts.append(t("email.dkim", lang, value=", ".join(email.dkim_selectors)))
    extras = [name for name, on in (("MTA-STS", email.mta_sts), ("BIMI", email.bimi)) if on]
    return " · ".join(parts + extras)


def _cookies_value(security: SecurityResult, lang: str) -> str:
    cookies = security.cookies
    if not cookies:
        return t("cookies.none", lang)
    parts = [t("cookies.count", lang, count=len(cookies))]
    for key, missing in (
        ("cookies.no_secure", sum(1 for c in cookies if not c.secure) if security.https else 0),
        ("cookies.no_httponly", sum(1 for c in cookies if not c.httponly)),
        ("cookies.no_samesite", sum(1 for c in cookies if not c.samesite)),
    ):
        if missing:
            parts.append(t(key, lang, count=missing))
    return " · ".join(parts)


def _headers_value(security: SecurityResult, lang: str) -> str:
    report = security.headers
    value = t("headers.value", lang, grade=report.grade, score=report.score, max=report.max_score)
    missing = [_HEADER_SHORT.get(c.name, c.name) for c in report.checks if not c.present]
    weak = [_HEADER_SHORT.get(c.name, c.name) for c in report.checks if c.present and c.issues]
    if missing:
        value += " · " + t("headers.missing", lang, names=", ".join(missing))
    if weak:
        value += " · " + t("headers.weak", lang, names=", ".join(weak))
    return value


def security_rows(result: AnalysisResult, lang: str, verbose: bool = False) -> list[Row]:
    """Filas del bloque SEGURIDAD VISIBLE."""
    security = result.security
    assert security is not None
    files = security.files
    if files.security_txt is not None:
        sectxt = t("value.yes", lang)
    elif files.security_txt_checked:
        sectxt = t("value.no", lang)
    else:
        sectxt = t("value.unknown", lang)
    redirect = security.http_redirect
    https_redirect = (
        f"{_yes_no(redirect.redirects_to_https, lang)} ({redirect.status})"
        if redirect
        else t("value.unknown", lang)
    )
    forms = security.content.forms
    other = [
        t("other.security_txt", lang, value=sectxt),
        t("other.https_redirect", lang, value=https_redirect),
        t("other.forms", lang, count=forms.count),
    ]
    if forms.login:
        other.append(t("other.login_forms", lang, count=forms.login))
    rows: list[Row] = [
        (t("label.headers", lang), _headers_value(security, lang)),
        (t("label.cookies", lang), _cookies_value(security, lang)),
        (t("label.email", lang), _email_value(security, result, lang)),
        (t("label.other", lang), " · ".join(other)),
    ]
    third = security.content.third_party
    if third:
        rows.append(
            (
                t("label.third_party", lang),
                t("third_party.value", lang, count=len(third), list=_short(list(third))),
            )
        )
    surface = security.surface
    if surface.subdomains or surface.endpoints:
        parts = []
        if surface.subdomains:
            parts.append(t("surface.subdomains", lang, count=len(surface.subdomains)))
        if surface.endpoints:
            parts.append(t("surface.endpoints", lang, list=_short(list(surface.endpoints), 4)))
        rows.append((t("label.surface", lang), " · ".join(parts)))
    if verbose:
        rows += _security_details(security, lang)
    return rows


def _security_details(security: SecurityResult, lang: str) -> list[Row]:
    none = t("value.none", lang)
    values = [f"{c.name}: {c.value}" for c in security.headers.checks if c.present and c.value]
    values += [f"{name}: {value}" for name, value in security.headers.extra.items()]
    leaks = [f"{leak.source}: {leak.value}" for leak in security.leaks]
    cookies = [
        f"{c.name} [{'Secure' if c.secure else '-'} {'HttpOnly' if c.httponly else '-'} "
        f"SameSite={c.samesite or '-'}]"
        for c in security.cookies
    ]
    no_sri = list(security.content.scripts_without_sri + security.content.styles_without_sri)
    rows: list[Row] = [
        (t("label.header_values", lang), "\n".join(v[:120] for v in values) or none),
        (t("label.leaks", lang), "\n".join(leaks) or none),
        (t("label.cookie_list", lang), "\n".join(cookies) or none),
        (t("label.robots", lang), ", ".join(security.files.robots_sensitive) or none),
        (t("label.mixed", lang), _short(list(security.content.mixed), 5) or none),
        (t("label.no_sri", lang), _short(no_sri, 5) or none),
    ]
    if security.surface.subdomains:
        rows.append((t("label.surface", lang), _short(list(security.surface.subdomains), 10)))
    return rows


def build_blocks(result: AnalysisResult, lang: str, verbose: bool = False) -> list[Block]:
    """Bloques con datos (los que no corren o fallaron muestran el motivo)."""
    blocks = [
        Block("general", t("block.general", lang), tuple(general_rows(result, lang, verbose)))
    ]
    if result.brief:
        return blocks
    if result.infra is not None:
        rows = infrastructure_rows(result, lang, verbose)
        blocks.append(Block("infrastructure", t("block.infrastructure", lang), tuple(rows)))
    if result.tls is not None:
        blocks.append(
            Block("tls", t("block.tls", lang), tuple(tls_rows(result.tls, lang, verbose)))
        )
    elif "tls" in result.unavailable:
        reason = format_unavailable(result.unavailable["tls"], lang)
        blocks.append(Block("tls", t("block.tls", lang), ((t("label.certificate", lang), reason),)))
    if result.security is not None:
        rows = security_rows(result, lang, verbose)
        blocks.append(Block("security", t("block.security", lang), tuple(rows)))
    return blocks


# --- Texto (rich) -------------------------------------------------------------------


def _grid(label_width: int = 0) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=LABEL_STYLE, no_wrap=True, min_width=label_width)
    table.add_column(overflow="fold")
    return table


def summary_table(result: AnalysisResult, lang: str) -> Table:
    """Tabla del bloque GENERAL (una línea por dato)."""
    table = _grid()
    for label, value in general_rows(result, lang):
        table.add_row(label, Text(value))
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


def findings_table(findings: Iterable[Finding], lang: str, verbose: bool) -> Table:
    """Hallazgos con la severidad coloreada; en ``--verbose`` suma evidencia y recomendación."""
    table = Table.grid(padding=(0, 1))
    table.add_column(no_wrap=True)
    table.add_column(overflow="fold")
    for finding in findings:
        tag = Text(" ")
        tag.append(
            f"[{t(f'severity.{finding.severity}', lang)}]", SEVERITY_STYLES[finding.severity]
        )
        body = Text(finding_title(finding, lang))
        if verbose:
            if finding.evidence:
                body.append(f"\n{t('findings.evidence', lang)}: {finding.evidence}", style="dim")
            body.append(f"\n→ {finding_recommendation(finding, lang)}", style="dim")
            body.append(f"\n{finding.id}", style="dim")
        table.add_row(tag, body)
    return table


def render(result: AnalysisResult, lang: str, console: Console, verbose: bool = False) -> None:
    """Imprime el reporte de texto en ``console`` en el idioma ``lang``."""
    console.print(
        Text.assemble("🔎 ", (result.domain, "bold"), ("  ·  " + _header_line(result, lang), "dim"))
    )
    console.print(Rule(style="dim", characters="═"))
    blocks = build_blocks(result, lang, verbose)
    width = max((len(label) for block in blocks for label, _ in block.rows), default=0) + 1
    for index, block in enumerate(blocks):
        if index:
            console.print()
        console.print(Text(" " + block.title, style="bold"))
        table = _grid(width)
        for label, value in block.rows:
            table.add_row(" " + label, Text(value))
        console.print(table)
    if not result.brief:
        console.print()
        console.print(Text(" " + t("block.findings", lang), style="bold"))
        if result.findings:
            console.print(findings_table(result.findings, lang, verbose))
        else:
            console.print(Text(" " + t("findings.none", lang)))
    if verbose:
        console.print()
        console.print(Rule(t("verbose.title", lang), style="dim"))
        console.print(details_table(result, lang))
    console.print()
    console.print(Text(t("notice.passive", lang), style="dim italic"))


# --- Markdown -----------------------------------------------------------------------


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def to_markdown(result: AnalysisResult, lang: str, verbose: bool = False) -> str:
    """Reporte en Markdown con encabezados y tablas, listo para pegar en un informe."""
    lines = [
        f"# 🔎 {result.domain}",
        "",
        f"**URL:** {_md(_header_line(result, lang))}  ",
        f"**{t('md.scanned', lang)}:** {result.scanned_at or '-'} · webscope {__version__}",
        "",
    ]
    for block in build_blocks(result, lang, verbose):
        lines += [
            f"## {block.title}",
            "",
            f"| {t('md.field', lang)} | {t('md.value', lang)} |",
            "|---|---|",
        ]
        lines += [f"| {_md(label)} | {_md(value)} |" for label, value in block.rows]
        lines.append("")
    if not result.brief:
        lines += [f"## {t('block.findings', lang)}", ""]
        if result.findings:
            lines += [
                f"| {t('md.severity', lang)} | ID | {t('md.finding', lang)} | "
                f"{t('findings.evidence', lang).capitalize()} | {t('md.recommendation', lang)} |",
                "|---|---|---|---|---|",
            ]
            lines += [
                f"| {t(f'severity.{f.severity}', lang)} | `{f.id}` | "
                f"{_md(finding_title(f, lang))} | {_md(f.evidence)} | "
                f"{_md(finding_recommendation(f, lang))} |"
                for f in result.findings
            ]
        else:
            lines.append(t("findings.none", lang))
        lines.append("")
    lines.append(f"> {t('notice.passive', lang)}")
    return "\n".join(lines) + "\n"


# --- JSON ---------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    """Convierte dataclasses, mappings y tuplas en tipos JSON."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def _pages_dict(pages: PageCount | None) -> dict[str, Any] | None:
    if pages is None:
        return None
    return {"count": pages.count, "source": pages.source, "at_least": pages.at_least}


def _site_type_dict(site_type: SiteTypeResult) -> dict[str, Any]:
    return {
        "type": site_type.kind,
        "confidence": site_type.confidence,
        "scores": {"app": site_type.app_score, "site": site_type.site_score},
        "signals": [
            {"code": s.code, "target": s.target, "weight": s.weight} for s in site_type.signals
        ],
    }


def _general_dict(result: AnalysisResult, ui_lang: str) -> dict[str, Any]:
    topic = result.topic
    return {
        "summary": format_summary(result, ui_lang),
        "description": result.summary,
        "description_source": topic.description_source if topic else None,
        "category": _plain(topic.category) if topic else None,
        "site_name": topic.site_name if topic else None,
        "country": topic.country if topic else None,
        "country_source": topic.country_source if topic else None,
        "site_lang": result.site_lang,
        "site_type": _site_type_dict(result.site_type),
        "pages": _pages_dict(result.pages),
        "technologies": [_plain(tech) for tech in result.technologies],
        "keywords": list(result.keywords),
    }


def _finding_dict(finding: Finding, ui_lang: str) -> dict[str, Any]:
    return {
        "id": finding.id,
        "severity": finding.severity,
        "title": finding_title(finding, ui_lang),
        "evidence": finding.evidence,
        "recommendation": finding_recommendation(finding, ui_lang),
    }


def to_dict(result: AnalysisResult, ui_lang: str) -> dict[str, Any]:
    """Representación JSON: claves siempre en inglés, independientes del idioma.

    Las claves de nivel superior de la v0.1 (``summary``, ``site_type``, ``pages``...)
    se mantienen por compatibilidad; el esquema 2.0 agrega una sección por bloque.
    """
    infra = result.infra
    return {
        "schema_version": SCHEMA_VERSION,
        "webscope_version": __version__,
        "scanned_at": result.scanned_at,
        "url": result.url,
        "final_url": result.final_url,
        "domain": result.domain,
        "ui_lang": ui_lang,
        "site_lang": result.site_lang,
        "summary": result.summary,
        "site_type": _site_type_dict(result.site_type),
        "pages": _pages_dict(result.pages),
        "technologies": [{"name": x.name, "category": x.category} for x in result.technologies],
        "keywords": list(result.keywords),
        "http": {
            "status": result.status_code,
            "server": result.server,
            "elapsed_ms": result.elapsed_ms,
        },
        "general": _general_dict(result, ui_lang),
        "infrastructure": None
        if infra is None
        else {**_plain(infra), "redirects": _plain(result.redirects)},
        "tls": _plain(result.tls),
        "security": _plain(result.security),
        "findings": [_finding_dict(f, ui_lang) for f in result.findings],
        "unavailable": dict(result.unavailable),
    }


def to_json(result: AnalysisResult, ui_lang: str) -> str:
    """JSON con indentación y caracteres no ASCII legibles."""
    return json.dumps(to_dict(result, ui_lang), ensure_ascii=False, indent=2)

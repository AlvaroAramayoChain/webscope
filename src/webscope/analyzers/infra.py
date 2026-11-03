"""Infraestructura: CDN/WAF/hosting inferido y datos de registro (RDAP).

Funciones puras sobre headers, CNAMEs, organizaciones de ASN y PTR ya obtenidos.
Agregar un proveedor = sumar una entrada a ``CDN_RULES``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final

from webscope.models import AsnInfo, CdnMatch, DnsRecords, InfraResult, RdapInfo


@dataclass(frozen=True)
class CdnRule:
    """Proveedor detectable. ``headers`` son pares ``(regex del nombre, regex del valor)``."""

    name: str
    kind: str
    headers: tuple[tuple[str, str], ...] = ()
    cnames: tuple[str, ...] = ()
    asn_orgs: tuple[str, ...] = ()
    ptr: tuple[str, ...] = ()


R = CdnRule
CDN_RULES: Final[tuple[CdnRule, ...]] = (
    R("Cloudflare", "cdn+waf", headers=(("cf-ray", ""), ("server", r"^cloudflare"), ("cf-cache-status", "")), cnames=(r"\.cdn\.cloudflare\.net$",), asn_orgs=(r"cloudflare",)),
    R("Akamai", "cdn+waf", headers=(("x-akamai-.*", ""), ("server", r"akamai"), ("akamai-grn", "")), cnames=(r"\.akamaiedge\.net$", r"\.edgekey\.net$", r"\.edgesuite\.net$"), asn_orgs=(r"akamai",), ptr=(r"akamaitechnologies\.com$",)),
    R("Amazon CloudFront", "cdn", headers=(("x-amz-cf-id", ""), ("via", r"cloudfront")), cnames=(r"\.cloudfront\.net$",)),
    R("Fastly", "cdn", headers=(("x-fastly-request-id", ""), ("x-served-by", r"^cache-"), ("fastly-.*", "")), cnames=(r"\.fastly\.net$", r"\.fastlylb\.net$"), asn_orgs=(r"fastly",)),
    R("Sucuri", "waf", headers=(("x-sucuri-id", ""), ("x-sucuri-cache", ""), ("server", r"sucuri")), cnames=(r"\.sucuri\.net$",)),
    R("Imperva", "waf", headers=(("x-iinfo", ""), ("x-cdn", r"incapsula|imperva")), cnames=(r"\.incapdns\.net$", r"\.impervadns\.net$"), asn_orgs=(r"incapsula|imperva",)),
    R("Azure Front Door / CDN", "cdn", headers=(("x-azure-ref", ""), ("x-fd-healthprobe", "")), cnames=(r"\.azureedge\.net$", r"\.azurefd\.net$", r"\.trafficmanager\.net$")),
    R("Google Cloud CDN", "cdn", headers=(("via", r"1\.1 google"),), cnames=(r"\.googlehosted\.com$", r"\.googleusercontent\.com$")),
    R("Bunny CDN", "cdn", headers=(("server", r"bunnycdn"), ("cdn-pullzone", "")), cnames=(r"\.b-cdn\.net$",)),
    R("StackPath", "cdn+waf", headers=(("x-sp-.*", ""),), cnames=(r"\.stackpathdns\.com$",), asn_orgs=(r"stackpath|highwinds",)),
    R("Vercel", "hosting", headers=(("x-vercel-id", ""), ("server", r"^vercel")), cnames=(r"\.vercel-dns\.com$", r"\.vercel\.app$", r"\.now\.sh$")),
    R("Netlify", "hosting", headers=(("x-nf-request-id", ""), ("server", r"^netlify")), cnames=(r"\.netlify\.app$", r"\.netlify\.com$")),
    R("GitHub Pages", "hosting", headers=(("server", r"^(?-i:GitHub\.com)$"),), cnames=(r"\.github\.io$",), ptr=(r"^cdn-[\d-]+\.github\.com$",)),
    R("Heroku", "hosting", headers=(("via", r"vegur"),), cnames=(r"\.herokuapp\.com$", r"\.herokudns\.com$")),
    R("Render", "hosting", headers=(("x-render-origin-server", ""), ("rndr-id", "")), cnames=(r"\.onrender\.com$",)),
    R("Shopify", "hosting", headers=(("x-shopid", ""),), cnames=(r"\.myshopify\.com$", r"shops\.myshopify\.com$")),
    R("Wix", "hosting", headers=(("x-wix-request-id", ""),), cnames=(r"\.wixdns\.net$",)),
    R("Squarespace", "hosting", cnames=(r"\.squarespace\.com$",)),
    R("Amazon Web Services", "hosting", headers=(("x-amz-request-id", ""),), cnames=(r"\.amazonaws\.com$", r"\.elb\.amazonaws\.com$"), asn_orgs=(r"^amazon",)),
    R("Google Cloud", "hosting", asn_orgs=(r"^google",)),
    R("Microsoft Azure", "hosting", asn_orgs=(r"^microsoft",), cnames=(r"\.azurewebsites\.net$", r"\.cloudapp\.net$")),
    R("DigitalOcean", "hosting", asn_orgs=(r"digitalocean",)),
    R("Hetzner", "hosting", asn_orgs=(r"hetzner",)),
    R("OVHcloud", "hosting", asn_orgs=(r"^ovh",)),
    R("Linode / Akamai Cloud", "hosting", asn_orgs=(r"linode",)),
    R("Hostinger", "hosting", asn_orgs=(r"hostinger",)),
    R("GoDaddy", "hosting", asn_orgs=(r"godaddy",), ptr=(r"secureserver\.net$",)),
)  # fmt: skip


def _header_match(rule: CdnRule, headers: Mapping[str, str]) -> str | None:
    for name_re, value_re in rule.headers:
        for name, value in headers.items():
            if re.fullmatch(name_re, name, re.I) and re.search(value_re, value, re.I):
                return f"header {name}" + (f": {value[:40]}" if value_re else "")
    return None


def _first_match(patterns: Iterable[str], values: Iterable[str], label: str) -> str | None:
    for value in values:
        if any(re.search(p, value, re.I) for p in patterns):
            return f"{label} {value}"
    return None


def detect_cdn(
    headers: Mapping[str, str],
    cnames: Iterable[str] = (),
    asn_orgs: Iterable[str] = (),
    ptrs: Iterable[str] = (),
) -> tuple[CdnMatch, ...]:
    """CDN/WAF/hosting inferidos por headers, CNAMEs, organización del ASN y PTR."""
    lowered = {k.lower(): v for k, v in headers.items()}
    cname_list, org_list, ptr_list = list(cnames), list(asn_orgs), list(ptrs)
    matches: list[CdnMatch] = []
    for rule in CDN_RULES:
        evidence = (
            _header_match(rule, lowered)
            or _first_match(rule.cnames, cname_list, "CNAME")
            or _first_match(rule.asn_orgs, org_list, "ASN")
            or _first_match(rule.ptr, ptr_list, "PTR")
        )
        if evidence:
            matches.append(CdnMatch(rule.name, rule.kind, evidence))
    edge = [m for m in matches if m.kind != "hosting"]
    # Un ASN genérico de nube no se informa si ya hay un CDN/hosting más específico.
    specific = [m for m in matches if m.kind == "hosting" and not m.evidence.startswith("ASN")]
    generic = [m for m in matches if m.kind == "hosting" and m.evidence.startswith("ASN")]
    return tuple(edge + specific + ([] if edge or specific else generic))


def build_infra(
    dns: DnsRecords | None,
    headers: Mapping[str, str],
    *,
    connected_ip: str | None = None,
    rdap: RdapInfo | None = None,
) -> InfraResult:
    """Combina DNS, headers y la IP de la conexión en un ``InfraResult``."""
    dns = dns or DnsRecords()
    ptr = dict(dns.ptr)
    asn: dict[str, AsnInfo] = dict(dns.asn)
    cdn = detect_cdn(
        headers,
        cnames=dns.cname.values(),
        asn_orgs=[info.org for info in asn.values() if info.org],
        ptrs=ptr.values(),
    )
    return InfraResult(
        ipv4=dns.a,
        ipv6=dns.aaaa,
        connected_ip=connected_ip,
        ptr=ptr,
        asn=asn,
        cdn=cdn,
        dns=dns,
        rdap=rdap,
    )


# --- RDAP ---------------------------------------------------------------------------


def _vcard_name(entity: Mapping[str, Any]) -> str:
    vcard = entity.get("vcardArray")
    if isinstance(vcard, list) and len(vcard) > 1 and isinstance(vcard[1], list):
        for entry in vcard[1]:
            if isinstance(entry, list) and len(entry) > 3 and entry[0] in ("fn", "org"):
                return str(entry[3])
    return str(entity.get("handle", ""))


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_rdap(domain: str, data: Mapping[str, Any], now: datetime | None = None) -> RdapInfo:
    """Registrador, creación, vencimiento y edad del dominio desde una respuesta RDAP."""
    now = now or datetime.now(timezone.utc)
    events = {
        str(e.get("eventAction", "")).lower(): _parse_date(e.get("eventDate"))
        for e in data.get("events", [])
        if isinstance(e, dict)
    }
    registrar = next(
        (
            _vcard_name(entity)
            for entity in data.get("entities", [])
            if isinstance(entity, dict) and "registrar" in entity.get("roles", [])
        ),
        "",
    )
    created = events.get("registration")
    expires = events.get("expiration")
    return RdapInfo(
        domain=domain,
        registrar=registrar,
        created=created.date().isoformat() if created else None,
        expires=expires.date().isoformat() if expires else None,
        age_days=(now - created).days if created else None,
    )

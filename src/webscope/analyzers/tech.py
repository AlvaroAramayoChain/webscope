"""Detección de tecnologías por firmas declarativas sobre el HTML y los headers.

Agregar una tecnología es sumar una línea a ``SIGNATURES``. El backend solo se
detecta si deja pistas visibles (headers, cookies, tokens en formularios...).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from webscope.models import Technology

# Orden en el que se muestran los grupos en el reporte.
CATEGORY_ORDER: Final = ("language", "cms", "framework", "library", "backend", "server")


@dataclass(frozen=True)
class Signature:
    """Firma de una tecnología: regex sobre el HTML y/o ``(header, regex)``."""

    name: str
    category: str
    html: tuple[str, ...] = ()
    headers: tuple[tuple[str, str], ...] = ()
    implies: tuple[str, ...] = ()


S = Signature
SIGNATURES: Final[tuple[Signature, ...]] = (
    # Lenguajes base del front y del back.
    S("HTML", "language", html=(r"<html", r"<body", r"<!doctype html")),
    S("CSS", "language", html=(r"<link[^>]+stylesheet", r"<style", r"\sstyle=[\"']")),
    S("JavaScript", "language", html=(r"<script",)),
    S("TypeScript", "language", html=(r"\.tsx?[\"'?#]", r"sourceMappingURL=\S+\.tsx?\b")),
    S("PHP", "language", html=(r"\.php\b",), headers=(("x-powered-by", r"php"), ("set-cookie", r"PHPSESSID"))),
    S("Python", "language"),
    S("Ruby", "language"),
    S("Node.js", "language"),
    # CMS, constructores y generadores de sitios.
    S("WordPress", "cms", html=(r"/wp-content/", r"/wp-includes/", r"generator\" content=\"WordPress"), headers=(("link", r"api\.w\.org"),), implies=("PHP",)),
    S("Shopify", "cms", html=(r"cdn\.shopify\.com", r"Shopify\.theme"), headers=(("x-shopid", r""), ("x-shopify-stage", r""))),
    S("Wix", "cms", html=(r"static\.wixstatic\.com", r"generator\" content=\"Wix"), headers=(("x-wix-request-id", r""),)),
    S("Squarespace", "cms", html=(r"static1\.squarespace\.com", r"Static\.SQUARESPACE_CONTEXT")),
    S("Webflow", "cms", html=(r"data-wf-page", r"generator\" content=\"Webflow")),
    S("Drupal", "cms", html=(r"Drupal\.settings", r"/sites/default/files/", r"generator\" content=\"Drupal"), headers=(("x-generator", r"drupal"), ("x-drupal-cache", r"")), implies=("PHP",)),
    S("Joomla", "cms", html=(r"generator\" content=\"Joomla", r"/media/jui/"), implies=("PHP",)),
    S("Ghost", "cms", html=(r"generator\" content=\"Ghost",)),
    S("Hugo", "cms", html=(r"generator\" content=\"Hugo",)),
    S("Jekyll", "cms", html=(r"generator\" content=\"Jekyll",), implies=("Ruby",)),
    S("Docusaurus", "cms", html=(r"generator\" content=\"Docusaurus",), implies=("React",)),
    # Frameworks de frontend.
    S("Next.js", "framework", html=(r"__NEXT_DATA__", r"/_next/static/", r"id=\"__next\""), headers=(("x-powered-by", r"next\.js"),), implies=("React",)),
    S("React", "framework", html=(r"data-reactroot", r"data-reactid", r"react(?:-dom)?(?:\.production|\.development)?(?:\.min)?\.js", r"__REACT_DEVTOOLS_GLOBAL_HOOK__")),
    S("Gatsby", "framework", html=(r"id=\"___gatsby\"", r"generator\" content=\"Gatsby"), implies=("React",)),
    S("Nuxt", "framework", html=(r"__NUXT__", r"/_nuxt/", r"id=\"__nuxt\""), implies=("Vue",)),
    S("Vue", "framework", html=(r"data-v-[0-9a-f]{6,8}", r"vue(?:\.runtime)?(?:\.global)?(?:\.prod)?(?:\.min)?\.js", r"data-server-rendered=\"true\"")),
    S("Angular", "framework", html=(r"ng-version=", r"_nghost-", r"_ngcontent-"), implies=("TypeScript",)),
    S("AngularJS", "framework", html=(r"\bng-app\b", r"angular(?:\.min)?\.js")),
    S("Svelte", "framework", html=(r"\bsvelte-[a-z0-9]{5,}", r"__sveltekit", r"/_app/immutable/")),
    S("Astro", "framework", html=(r"<astro-island", r"generator\" content=\"Astro")),
    # Librerías de UI y utilidades.
    S("jQuery", "library", html=(r"jquery(?:[.-]\d[\d.]*)?(?:\.min)?\.js", r"jQuery\(")),
    S("Bootstrap", "library", html=(r"bootstrap(?:\.bundle)?(?:\.min)?\.(?:css|js)", r"class=\"[^\"]*\b(?:col-(?:xs|sm|md|lg)-\d+|navbar-expand)")),
    S("Tailwind CSS", "library", html=(r"tailwind", r"class=\"[^\"]*\b(?:sm|md|lg|xl):(?:flex|hidden|block|grid|px-\d|py-\d|text-\w+)")),
    S("Alpine.js", "library", html=(r"\sx-data=", r"alpine(?:\.min)?\.js")),
    S("htmx", "library", html=(r"\shx-(?:get|post)=", r"htmx(?:\.min)?\.js")),
    # Frameworks de backend (solo si dejan pistas).
    S("Django", "backend", html=(r"csrfmiddlewaretoken",), headers=(("set-cookie", r"csrftoken="),), implies=("Python",)),
    S("Laravel", "backend", headers=(("set-cookie", r"laravel_session"),), implies=("PHP",)),
    S("Ruby on Rails", "backend", html=(r"name=\"csrf-param\" content=\"authenticity_token\"",), headers=(("x-powered-by", r"phusion"),), implies=("Ruby",)),
    S("Express", "backend", headers=(("x-powered-by", r"express"),), implies=("Node.js",)),
    S("ASP.NET", "backend", html=(r"__VIEWSTATE",), headers=(("x-powered-by", r"asp\.net"), ("x-aspnet-version", r""))),
    # Servidores, CDNs y hosting.
    S("Cloudflare", "server", headers=(("server", r"cloudflare"), ("cf-ray", r""))),
    S("nginx", "server", headers=(("server", r"nginx"),)),
    S("Apache", "server", headers=(("server", r"apache"),)),
    S("LiteSpeed", "server", headers=(("server", r"litespeed"),)),
    S("Microsoft IIS", "server", headers=(("server", r"microsoft-iis"),)),
    S("Vercel", "server", headers=(("server", r"vercel"), ("x-vercel-id", r""))),
    S("Netlify", "server", headers=(("server", r"netlify"), ("x-nf-request-id", r""))),
    S("GitHub Pages", "server", headers=(("server", r"github\.com"),)),
    S("Amazon CloudFront", "server", headers=(("x-amz-cf-id", r""),)),
)  # fmt: skip


def _matches(signature: Signature, html: str, headers: Mapping[str, str]) -> bool:
    if any(re.search(pattern, html, re.IGNORECASE) for pattern in signature.html):
        return True
    for name, pattern in signature.headers:
        value = headers.get(name)
        if value is not None and re.search(pattern, value, re.IGNORECASE):
            return True
    return False


def detect_technologies(
    html: str, headers: Mapping[str, str] | None = None
) -> tuple[Technology, ...]:
    """Tecnologías detectadas, ordenadas por categoría y luego por ``SIGNATURES``."""
    lowered = {key.lower(): value for key, value in (headers or {}).items()}
    found = {sig.name for sig in SIGNATURES if _matches(sig, html, lowered)}
    by_name = {sig.name: sig for sig in SIGNATURES}
    pending = list(found)
    while pending:
        for implied in by_name[pending.pop()].implies:
            if implied not in found:
                found.add(implied)
                pending.append(implied)
    ordered = sorted(
        (sig for sig in SIGNATURES if sig.name in found),
        key=lambda sig: CATEGORY_ORDER.index(sig.category),
    )
    return tuple(Technology(sig.name, sig.category) for sig in ordered)

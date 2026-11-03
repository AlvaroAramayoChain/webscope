"""Detección de tecnologías por firmas declarativas sobre el HTML y los headers.

Agregar una tecnología es sumar una línea a ``SIGNATURES``. El backend solo se
detecta si deja pistas visibles (headers, cookies, tokens en formularios...).

``versions`` son pares ``(fuente, regex)`` donde la fuente es ``"html"`` o el
nombre de un header y el primer grupo de la regex captura la versión.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from webscope.models import Technology

# Orden en el que se muestran los grupos en el reporte.
CATEGORY_ORDER: Final = (
    "language",
    "cms",
    "ecommerce",
    "framework",
    "library",
    "backend",
    "analytics",
    "service",
    "server",
    "cdn",
)

_V = r"(\d+(?:\.\d+){0,3})"


@dataclass(frozen=True)
class Signature:
    """Firma de una tecnología: regex sobre el HTML y/o ``(header, regex)``."""

    name: str
    category: str
    html: tuple[str, ...] = ()
    headers: tuple[tuple[str, str], ...] = ()
    implies: tuple[str, ...] = ()
    versions: tuple[tuple[str, str], ...] = ()


S = Signature
GEN = r"generator\" content=\""
SIGNATURES: Final[tuple[Signature, ...]] = (
    # Lenguajes base del front y del back.
    S("HTML", "language", html=(r"<html", r"<body", r"<!doctype html")),
    S("CSS", "language", html=(r"<link[^>]+stylesheet", r"<style", r"\sstyle=[\"']")),
    S("JavaScript", "language", html=(r"<script",)),
    S("TypeScript", "language", html=(r"\.tsx?[\"'?#]", r"sourceMappingURL=\S+\.tsx?\b")),
    S("PHP", "language", html=(r"\.php\b",), headers=(("x-powered-by", r"php"), ("set-cookie", r"PHPSESSID")), versions=(("x-powered-by", rf"PHP/{_V}"),)),
    S("Python", "language"),
    S("Ruby", "language"),
    S("Node.js", "language"),
    S("Java", "language", headers=(("set-cookie", r"JSESSIONID"),)),
    # CMS, constructores y generadores de sitios.
    S("WordPress", "cms", html=(r"/wp-content/", r"/wp-includes/", GEN + "WordPress"), headers=(("link", r"api\.w\.org"),), implies=("PHP",), versions=(("html", GEN + rf"WordPress {_V}"),)),
    S("Shopify", "cms", html=(r"cdn\.shopify\.com", r"Shopify\.theme"), headers=(("x-shopid", r""), ("x-shopify-stage", r""))),
    S("Wix", "cms", html=(r"static\.wixstatic\.com", GEN + "Wix"), headers=(("x-wix-request-id", r""),)),
    S("Squarespace", "cms", html=(r"static1\.squarespace\.com", r"Static\.SQUARESPACE_CONTEXT")),
    S("Webflow", "cms", html=(r"data-wf-page", GEN + "Webflow")),
    S("Drupal", "cms", html=(r"Drupal\.settings", r"/sites/default/files/", GEN + "Drupal"), headers=(("x-generator", r"drupal"), ("x-drupal-cache", r"")), implies=("PHP",), versions=(("html", GEN + rf"Drupal {_V}"), ("x-generator", rf"Drupal {_V}"))),
    S("Joomla", "cms", html=(GEN + "Joomla", r"/media/jui/", r"/media/system/js/core\.js"), implies=("PHP",), versions=(("html", GEN + rf"Joomla! {_V}"),)),
    S("Ghost", "cms", html=(GEN + "Ghost", r"ghost-(?:portal|search)"), versions=(("html", GEN + rf"Ghost {_V}"),)),
    S("Hugo", "cms", html=(GEN + "Hugo",), versions=(("html", GEN + rf"Hugo {_V}"),)),
    S("Jekyll", "cms", html=(GEN + "Jekyll",), implies=("Ruby",), versions=(("html", GEN + rf"Jekyll v{_V}"),)),
    S("Docusaurus", "cms", html=(GEN + "Docusaurus",), implies=("React",), versions=(("html", GEN + rf"Docusaurus v{_V}"),)),
    S("Elementor", "cms", html=(r"/plugins/elementor/", r"elementor-kit-\d", GEN + "Elementor"), implies=("WordPress",), versions=(("html", GEN + rf"Elementor {_V}"), ("html", rf"/plugins/elementor/[^\"']+\?ver={_V}"))),
    S("Divi", "cms", html=(r"/themes/Divi/", r"\bet_pb_[a-z]", r"et-divi-"), implies=("WordPress",)),
    # Tiendas online.
    S("WooCommerce", "ecommerce", html=(r"/plugins/woocommerce/", r"\bwoocommerce\b", GEN + "WooCommerce"), implies=("WordPress",), versions=(("html", GEN + rf"WooCommerce {_V}"), ("html", rf"/plugins/woocommerce/[^\"']+\?ver={_V}"))),
    S("Magento", "ecommerce", html=(r"text/x-magento-init", r"Mage\.Cookies", r"/static/version\d+/frontend/"), implies=("PHP",)),
    S("PrestaShop", "ecommerce", html=(r"\bprestashop\b", GEN + "PrestaShop"), headers=(("powered-by", r"prestashop"),), implies=("PHP",)),
    # Frameworks de frontend.
    S("Next.js", "framework", html=(r"__NEXT_DATA__", r"/_next/static/", r"id=\"__next\""), headers=(("x-powered-by", r"next\.js"),), implies=("React",), versions=(("x-powered-by", rf"Next\.js {_V}"),)),
    S("React", "framework", html=(r"data-reactroot", r"data-reactid", r"react(?:-dom)?(?:\.production|\.development)?(?:\.min)?\.js", r"__REACT_DEVTOOLS_GLOBAL_HOOK__"), versions=(("html", rf"react(?:-dom)?@{_V}"), ("html", rf"/react/{_V}/"))),
    S("Gatsby", "framework", html=(r"id=\"___gatsby\"", GEN + "Gatsby"), implies=("React",), versions=(("html", GEN + rf"Gatsby {_V}"),)),
    S("Remix", "framework", html=(r"__remixContext", r"__remixManifest"), implies=("React",)),
    S("Nuxt", "framework", html=(r"__NUXT__", r"/_nuxt/", r"id=\"__nuxt\""), implies=("Vue",)),
    S("Vue", "framework", html=(r"data-v-[0-9a-f]{6,8}", r"vue(?:\.runtime)?(?:\.global)?(?:\.prod)?(?:\.min)?\.js", r"data-server-rendered=\"true\""), versions=(("html", rf"vue@{_V}"), ("html", rf"/vue/{_V}/"))),
    S("Angular", "framework", html=(r"ng-version=", r"_nghost-", r"_ngcontent-"), implies=("TypeScript",), versions=(("html", rf"ng-version=\"{_V}"),)),
    S("AngularJS", "framework", html=(r"\bng-app\b", r"angular(?:\.min)?\.js"), versions=(("html", rf"angular(?:js)?/{_V}/"), ("html", rf"angular(?:js)?@{_V}"))),
    S("SvelteKit", "framework", html=(r"__sveltekit", r"data-sveltekit-", r"/_app/immutable/"), implies=("Svelte",)),
    S("Svelte", "framework", html=(r"\bsvelte-[a-z0-9]{5,}",)),
    S("Astro", "framework", html=(r"<astro-island", GEN + "Astro"), versions=(("html", GEN + rf"Astro v{_V}"),)),
    # Librerías de UI y utilidades.
    S("jQuery", "library", html=(r"jquery(?:[.-]\d[\d.]*)?(?:\.min)?\.js", r"jQuery\("), versions=(("html", rf"jquery[.-]{_V}(?:\.min)?\.js"), ("html", rf"jquery(?:\.min)?\.js\?ver={_V}"), ("html", rf"jquery@{_V}"), ("html", rf"/jquery/{_V}/"))),
    S("Bootstrap", "library", html=(r"bootstrap(?:\.bundle)?(?:\.min)?\.(?:css|js)", r"class=\"[^\"]*\b(?:col-(?:xs|sm|md|lg)-\d+|navbar-expand)"), versions=(("html", rf"bootstrap@{_V}"), ("html", rf"/bootstrap/{_V}/"), ("html", rf"bootstrap(?:\.bundle)?(?:\.min)?\.(?:css|js)\?ver={_V}"))),
    S("Tailwind CSS", "library", html=(r"tailwind", r"class=\"[^\"]*\b(?:sm|md|lg|xl):(?:flex|hidden|block|grid|px-\d|py-\d|text-\w+)"), versions=(("html", rf"tailwindcss@{_V}"), ("html", rf"tailwindcss v{_V}"))),
    S("Alpine.js", "library", html=(r"\sx-data=", r"alpine(?:\.min)?\.js"), versions=(("html", rf"alpinejs@{_V}"),)),
    S("htmx", "library", html=(r"\shx-(?:get|post)=", r"htmx(?:\.min)?\.js"), versions=(("html", rf"htmx\.org@{_V}"),)),
    # Frameworks de backend (solo si dejan pistas).
    S("Django", "backend", html=(r"csrfmiddlewaretoken",), headers=(("set-cookie", r"csrftoken="),), implies=("Python",)),
    S("Flask", "backend", headers=(("server", r"werkzeug"),), implies=("Python",), versions=(("server", rf"Werkzeug/{_V}"),)),
    S("Laravel", "backend", headers=(("set-cookie", r"laravel_session"),), implies=("PHP",)),
    S("Ruby on Rails", "backend", html=(r"name=\"csrf-param\" content=\"authenticity_token\"",), headers=(("x-powered-by", r"phusion"),), implies=("Ruby",)),
    S("Express", "backend", headers=(("x-powered-by", r"express"),), implies=("Node.js",)),
    S("Spring", "backend", html=(r"Whitelabel Error Page",), headers=(("x-application-context", r""),), implies=("Java",)),
    S("ASP.NET", "backend", html=(r"__VIEWSTATE",), headers=(("x-powered-by", r"asp\.net"), ("x-aspnet-version", r"")), versions=(("x-aspnet-version", _V),)),
    # Analítica y marketing.
    S("Google Analytics", "analytics", html=(r"google-analytics\.com/(?:analytics|ga)\.js", r"googletagmanager\.com/gtag/js", r"gtag\(\s*['\"]config['\"]")),
    S("Google Tag Manager", "analytics", html=(r"googletagmanager\.com/gtm\.js", r"\bGTM-[A-Z0-9]{4,}")),
    S("Meta Pixel", "analytics", html=(r"connect\.facebook\.net/[^\"']*/fbevents\.js", r"fbq\(\s*['\"]init")),
    S("Hotjar", "analytics", html=(r"static\.hotjar\.com", r"\bhjid\s*:")),
    # Servicios de terceros (captcha, pagos).
    S("reCAPTCHA", "service", html=(r"google\.com/recaptcha/", r"recaptcha/api\.js", r"\bg-recaptcha\b")),
    S("Cloudflare Turnstile", "service", html=(r"challenges\.cloudflare\.com/turnstile", r"\bcf-turnstile\b")),
    S("Stripe", "service", html=(r"js\.stripe\.com",)),
    # Servidores y hosting.
    S("nginx", "server", headers=(("server", r"nginx"),), versions=(("server", rf"nginx/{_V}"),)),
    S("Apache", "server", headers=(("server", r"apache"),), versions=(("server", rf"Apache/{_V}"),)),
    S("LiteSpeed", "server", headers=(("server", r"litespeed"),)),
    S("Microsoft IIS", "server", headers=(("server", r"microsoft-iis"),), versions=(("server", rf"Microsoft-IIS/{_V}"),)),
    S("Vercel", "server", headers=(("server", r"vercel"), ("x-vercel-id", r""))),
    S("Netlify", "server", headers=(("server", r"netlify"), ("x-nf-request-id", r""))),
    S("GitHub Pages", "server", headers=(("server", r"^(?-i:GitHub\.com)$"),)),  # github.com responde en minúsculas
    # CDN.
    S("Cloudflare", "cdn", headers=(("server", r"cloudflare"), ("cf-ray", r""))),
    S("Amazon CloudFront", "cdn", headers=(("x-amz-cf-id", r""),)),
    S("Fastly", "cdn", headers=(("x-fastly-request-id", r""), ("x-served-by", r"cache-"))),
    S("Akamai", "cdn", headers=(("server", r"akamai"), ("x-akamai-transformed", r""))),
)  # fmt: skip


def _matches(signature: Signature, html: str, headers: Mapping[str, str]) -> bool:
    if any(re.search(pattern, html, re.IGNORECASE) for pattern in signature.html):
        return True
    for name, pattern in signature.headers:
        value = headers.get(name)
        if value is not None and re.search(pattern, value, re.IGNORECASE):
            return True
    return False


def find_version(signature: Signature, html: str, headers: Mapping[str, str]) -> str | None:
    """Primera versión visible según ``signature.versions``; ``None`` si no hay."""
    for source, pattern in signature.versions:
        text = html if source == "html" else headers.get(source, "")
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


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
    return tuple(
        Technology(sig.name, sig.category, find_version(sig, html, lowered)) for sig in ordered
    )

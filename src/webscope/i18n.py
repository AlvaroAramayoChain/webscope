"""Textos de la interfaz en cada idioma y la función de traducción ``t()``.

Para agregar un idioma basta con sumar un diccionario a ``MESSAGES`` con las
mismas claves (las que falten caen en inglés). El menú de idioma, ``--lang`` y la
validación se generan a partir de este diccionario.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

DEFAULT_LANG: Final = "en"
MENU_FALLBACK_LANG: Final = "es"

_ES: Final[dict[str, str]] = {
    "lang.name": "Español",
    # Menú de idioma (bilingüe a propósito: todavía no sabemos el idioma).
    "menu.title": "Select language / Elegí idioma",
    "menu.invalid": "Opción inválida / Invalid option",
    "menu.fallback": "Demasiados intentos: se usa Español.",
    "menu.saved": "Idioma guardado: {name}",
    "menu.not_saved": "No se pudo guardar la preferencia; se usará solo en esta ejecución.",
    # Etiquetas del reporte.
    "label.topic": "De qué trata",
    "label.type": "Tipo",
    "label.pages": "Páginas",
    "label.tech": "Tecnologías",
    "label.keywords": "Palabras clave",
    # Valores.
    "type.site": "Sitio web",
    "type.app": "App web",
    "type.value": "{kind} (confianza: {confidence})",
    "confidence.low": "baja",
    "confidence.medium": "media",
    "confidence.high": "alta",
    "pages.exact": "{count} (vía {source})",
    "pages.approx": "~{count} (vía {source})",
    "pages.at_least": "al menos {count} (vía {source})",
    "source.sitemap": "sitemap.xml",
    "source.crawl": "rastreo de links",
    "topic.none": "sin descripción disponible",
    "tech.none": "no se detectaron",
    "keywords.none": "texto insuficiente",
    # Errores.
    "error.prefix": "Error",
    "error.invalid_url": "URL inválida: {url}",
    "error.dns": "No se pudo resolver el dominio {host}. ¿Está bien escrito?",
    "error.timeout": "{host} tardó más de {timeout}s en responder.",
    "error.ssl": "Error de certificado SSL en {host}. Si confiás en el sitio, probá con http://",
    "error.connection": "No se pudo conectar con {host}.",
    "error.too_many_redirects": "Demasiadas redirecciones al abrir {url}.",
    "error.http": "El servidor respondió {status} {reason}.",
    "error.not_html": "La URL no devuelve una página HTML (Content-Type: {content_type}).",
    "error.missing_url": "Falta la URL. Uso: webscope <url>  (ver webscope --help)",
    "error.invalid_lang": "Idioma no soportado: '{lang}'. Opciones: {options}",
    "error.invalid_max_pages": "--max-pages tiene que ser un número mayor o igual a 1.",
    "error.interrupted": "Análisis cancelado.",
    "error.unexpected": "Error inesperado: {detail}",
    # Ayuda del CLI.
    "help.description": (
        "Analiza una web y resume de qué trata, cuántas páginas tiene, qué tecnologías "
        "usa, sus palabras clave y si es un sitio o una app web."
    ),
    "help.url": "URL a analizar (si no trae esquema se asume https://).",
    "help.max_pages": "Máximo de páginas a rastrear cuando no hay sitemap.",
    "help.json": "Imprime solo JSON (claves siempre en inglés).",
    "help.lang": "Idioma de la interfaz para esta ejecución (es/en). No cambia el guardado.",
    "help.verbose": "Muestra señales, detalles y el progreso del rastreo.",
    "help.no_color": "Desactiva los colores (también con la variable NO_COLOR).",
    "help.change_lang": "Vuelve a mostrar el menú de idioma y guarda la elección.",
    "help.version": "Muestra la versión y sale.",
    "help.help": "Muestra esta ayuda y sale.",
    "help.panel_args": "Argumentos",
    "help.panel_options": "Opciones",
    # Progreso y --verbose.
    "status.analyzing": "Analizando {url}…",
    "verbose.title": "Detalles",
    "verbose.final_url": "URL final",
    "verbose.status": "Estado HTTP",
    "verbose.server": "Servidor",
    "verbose.elapsed": "Respuesta",
    "verbose.site_lang": "Idioma de la web",
    "verbose.ui_lang": "Idioma interfaz",
    "verbose.scores": "Puntaje",
    "verbose.scores_value": "app {app} · sitio {site}",
    "verbose.signals": "Señales",
    "verbose.no_signals": "ninguna",
    "verbose.unknown": "desconocido",
    "target.site": "sitio",
    "target.app": "app",
    # Eventos del crawler (se muestran con --verbose).
    "event.fetch_home": "Descargando {url}",
    "event.robots_found": "robots.txt encontrado ({url})",
    "event.robots_missing": "Sin robots.txt: se asume que todo está permitido",
    "event.sitemap_try": "Probando sitemap {url}",
    "event.sitemap_found": "Sitemap con {count} URLs: {url}",
    "event.sitemap_index": "Sitemap index con {count} sitemaps: {url}",
    "event.sitemap_limit": "Límite de sitemaps leídos alcanzado: el total puede ser mayor",
    "event.sitemap_missing": "Sin sitemap útil: se rastrean links internos",
    "event.crawl_page": "[{n}/{max}] {url}",
    "event.crawl_blocked": "Bloqueado por robots.txt: {url}",
    "event.crawl_error": "No se pudo leer {url}",
    "event.crawl_limit": "Se alcanzó --max-pages ({max})",
    # Señales de la clasificación sitio/app.
    "signal.spa_root": "Contenedor de SPA (#root, #app, #__next...) casi sin texto",
    "signal.little_text": "Muy poco texto visible en el HTML",
    "signal.many_scripts": "Muchos bundles de JavaScript",
    "signal.module_scripts": "Scripts tipo módulo o chunks de un bundler",
    "signal.manifest": "Tiene manifest.json (PWA)",
    "signal.service_worker": "Registra un service worker",
    "signal.app_routes": "Rutas de app (/login, /dashboard, /app, /api/)",
    "signal.noscript_js": "Pide activar JavaScript para funcionar",
    "signal.password_form": "Formulario con contraseña en la home",
    "signal.rich_text": "Mucho texto estático",
    "signal.some_text": "Bastante texto estático",
    "signal.paragraphs": "Varios párrafos de contenido",
    "signal.nav_links": "Navegación clásica con muchos links",
    "signal.blog": "Blog, noticias o artículos",
    "signal.info_pages": "Páginas informativas (nosotros, contacto, servicios...)",
    "signal.cms_generator": "Generado por un CMS o generador estático",
}

_EN: Final[dict[str, str]] = {
    "lang.name": "English",
    "menu.title": "Select language / Elegí idioma",
    "menu.invalid": "Opción inválida / Invalid option",
    "menu.fallback": "Too many attempts: using Spanish.",
    "menu.saved": "Language saved: {name}",
    "menu.not_saved": "Could not save the preference; it will only apply to this run.",
    "label.topic": "About",
    "label.type": "Type",
    "label.pages": "Pages",
    "label.tech": "Technologies",
    "label.keywords": "Keywords",
    "type.site": "Website",
    "type.app": "Web app",
    "type.value": "{kind} (confidence: {confidence})",
    "confidence.low": "low",
    "confidence.medium": "medium",
    "confidence.high": "high",
    "pages.exact": "{count} (via {source})",
    "pages.approx": "~{count} (via {source})",
    "pages.at_least": "at least {count} (via {source})",
    "source.sitemap": "sitemap.xml",
    "source.crawl": "link crawl",
    "topic.none": "no description available",
    "tech.none": "none detected",
    "keywords.none": "not enough text",
    "error.prefix": "Error",
    "error.invalid_url": "Invalid URL: {url}",
    "error.dns": "Could not resolve the domain {host}. Is it spelled correctly?",
    "error.timeout": "{host} took longer than {timeout}s to respond.",
    "error.ssl": "SSL certificate error on {host}. If you trust the site, try http://",
    "error.connection": "Could not connect to {host}.",
    "error.too_many_redirects": "Too many redirects while opening {url}.",
    "error.http": "The server answered {status} {reason}.",
    "error.not_html": "The URL does not return an HTML page (Content-Type: {content_type}).",
    "error.missing_url": "Missing URL. Usage: webscope <url>  (see webscope --help)",
    "error.invalid_lang": "Unsupported language: '{lang}'. Options: {options}",
    "error.invalid_max_pages": "--max-pages must be a number greater than or equal to 1.",
    "error.interrupted": "Analysis cancelled.",
    "error.unexpected": "Unexpected error: {detail}",
    "help.description": (
        "Analyzes a website and summarizes what it is about, how many pages it has, "
        "which technologies it uses, its keywords and whether it is a website or a web app."
    ),
    "help.url": "URL to analyze (https:// is assumed when no scheme is given).",
    "help.max_pages": "Maximum pages to crawl when there is no sitemap.",
    "help.json": "Print JSON only (keys are always in English).",
    "help.lang": "Interface language for this run (es/en). Does not change the saved one.",
    "help.verbose": "Show signals, details and crawl progress.",
    "help.no_color": "Disable colors (the NO_COLOR variable works too).",
    "help.change_lang": "Show the language menu again and save the choice.",
    "help.version": "Show the version and exit.",
    "help.help": "Show this help and exit.",
    "help.panel_args": "Arguments",
    "help.panel_options": "Options",
    "status.analyzing": "Analyzing {url}…",
    "verbose.title": "Details",
    "verbose.final_url": "Final URL",
    "verbose.status": "HTTP status",
    "verbose.server": "Server",
    "verbose.elapsed": "Response",
    "verbose.site_lang": "Site language",
    "verbose.ui_lang": "UI language",
    "verbose.scores": "Score",
    "verbose.scores_value": "app {app} · site {site}",
    "verbose.signals": "Signals",
    "verbose.no_signals": "none",
    "verbose.unknown": "unknown",
    "target.site": "site",
    "target.app": "app",
    "event.fetch_home": "Downloading {url}",
    "event.robots_found": "robots.txt found ({url})",
    "event.robots_missing": "No robots.txt: assuming everything is allowed",
    "event.sitemap_try": "Trying sitemap {url}",
    "event.sitemap_found": "Sitemap with {count} URLs: {url}",
    "event.sitemap_index": "Sitemap index with {count} sitemaps: {url}",
    "event.sitemap_limit": "Sitemap read limit reached: the total may be higher",
    "event.sitemap_missing": "No usable sitemap: crawling internal links",
    "event.crawl_page": "[{n}/{max}] {url}",
    "event.crawl_blocked": "Blocked by robots.txt: {url}",
    "event.crawl_error": "Could not read {url}",
    "event.crawl_limit": "Reached --max-pages ({max})",
    "signal.spa_root": "SPA container (#root, #app, #__next...) with almost no text",
    "signal.little_text": "Very little visible text in the HTML",
    "signal.many_scripts": "Many JavaScript bundles",
    "signal.module_scripts": "Module scripts or bundler chunks",
    "signal.manifest": "Has a manifest.json (PWA)",
    "signal.service_worker": "Registers a service worker",
    "signal.app_routes": "App routes (/login, /dashboard, /app, /api/)",
    "signal.noscript_js": "Asks to enable JavaScript to work",
    "signal.password_form": "Password form on the home page",
    "signal.rich_text": "Lots of static text",
    "signal.some_text": "A fair amount of static text",
    "signal.paragraphs": "Several content paragraphs",
    "signal.nav_links": "Classic navigation with many links",
    "signal.blog": "Blog, news or articles",
    "signal.info_pages": "Informational pages (about, contact, services...)",
    "signal.cms_generator": "Generated by a CMS or static site generator",
}

MESSAGES: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {"es": MappingProxyType(_ES), "en": MappingProxyType(_EN)}
)

SUPPORTED_LANGS: Final[tuple[str, ...]] = tuple(MESSAGES)


def t(key: str, lang: str, **fmt: object) -> str:
    """Traduce ``key`` a ``lang``; cae en inglés y, si tampoco existe, en la clave."""
    text = MESSAGES.get(lang, {}).get(key) or MESSAGES[DEFAULT_LANG].get(key, key)
    if not fmt:
        return text
    try:
        return text.format(**fmt)
    except (KeyError, IndexError, ValueError):
        return text


def normalize_lang(value: str | None) -> str | None:
    """Devuelve el código soportado para ``value`` (``"ES"`` -> ``"es"``) o ``None``."""
    if not value:
        return None
    code = value.strip().lower().replace("-", "_").split("_")[0]
    return code if code in MESSAGES else None


def language_name(lang: str) -> str:
    """Nombre del idioma en su propio idioma (``"es"`` -> ``"Español"``)."""
    return t("lang.name", lang)

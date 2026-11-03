"""De qué trata la web: descripción concreta, categoría, nombre del sitio y país.

Combina fuentes en orden de confianza (JSON-LD/schema.org, Open Graph, ``<title>``,
``meta description``, ``h1``/``h2``, ``meta keywords``) de la home y de algunas
páginas internas. Sin metadatos útiles, arma un resumen extractivo del texto.
``summarize()`` se mantiene como el resumen simple de la v0.1.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from webscope.analyzers._text import stopwords_for, tokenize
from webscope.analyzers.category import CategoryInput, classify_category
from webscope.models import CategorySignal, TopicResult
from webscope.parsing import content_soup, make_soup, visible_text

MAX_CHARS = 200
DESCRIPTION_CHARS = 170
MAX_INTERNAL_PAGES = 5
_MIN_GOOD_DESCRIPTION = 60
_MIN_JSONLD_DESCRIPTION = 40
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_META_DESCRIPTIONS = (
    {"name": "description"},
    {"property": "og:description"},
    {"name": "twitter:description"},
)
_TITLE_SEPARATORS = re.compile(r"\s+[|·•»–—:-]\s+|\s+::\s+")
_WELCOME = re.compile(
    r"^\s*(?:¡\s*)?(?:bienvenid[oa]s?|welcome)\s+(?:a|al|to)\s+[^.!|:—–-]{1,60}[.!:|—–-]+\s*",
    re.I,
)
_GENERIC_TITLES = frozenset(
    "home inicio index start página principal home page homepage portada welcome bienvenido "
    "bienvenidos".split()
)
_BOILERPLATE = re.compile(
    r"cookie|privacidad|privacy|derechos reservados|all rights reserved|copyright|"
    r"newsletter|suscrib|subscribe|javascript|navegador|browser",
    re.I,
)
# Tipos de schema.org cuya descripción describe al sitio entero.
_SITE_ENTITY_TYPES = frozenset(
    "organization corporation localbusiness website webapplication softwareapplication "
    "store onlinestore professionalservice educationalorganization collegeoruniversity "
    "governmentorganization medicalorganization restaurant hotel newsmediaorganization "
    "person profilepage".split()
)
# Grupos de páginas internas útiles para entender el sitio (una por grupo).
INTERNAL_PAGE_GROUPS: Final[tuple[tuple[str, str], ...]] = (
    ("about", r"/(?:about|about-us|nosotros|quienes-somos|sobre-nosotros|sobre-mi|acerca|empresa|company)(?:/|$|\.html?)"),
    ("offer", r"/(?:productos|products|servicios|services|soluciones|solutions|features|tienda|shop|pricing|precios)(?:/|$|\.html?)"),
    ("contact", r"/(?:contact|contacto|contact-us|contactanos|contactenos)(?:/|$|\.html?)"),
    ("blog", r"/(?:blog|news|noticias|novedades|articulos|articles)(?:/|$|\.html?)"),
    ("docs", r"/(?:docs|documentation|documentacion|faq|preguntas-frecuentes)(?:/|$|\.html?)"),
)  # fmt: skip
_PERSON_NAME = re.compile(r"^(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñü'-]+\s){1,3}[A-ZÁÉÍÓÚÑ][a-záéíóúñü'-]+$")
_ORG_WORDS = re.compile(
    r"(?:inc|llc|ltd|corp|s\.?a|srl|sas|group|grupo|studio|estudio|agency|agencia|labs?|"
    r"solutions|soluciones|software|tech|digital|media|shop|store|tienda|club|news)",
    re.I,
)
# ccTLD que en la práctica se usan como genéricos (no indican país).
_GENERIC_CCTLDS = frozenset("io co ai me tv ly fm gg sh so to ws cc app dev xyz".split())
_CCTLD_ALIASES = {"uk": "GB"}


# --- Utilidades de la v0.1 (se mantienen) -------------------------------------------


def clip(text: str, max_chars: int = MAX_CHARS) -> str:
    """Colapsa espacios y corta en un límite de palabra agregando ``…``."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:.-—|") + "…"


def meta_description(soup: BeautifulSoup) -> str:
    """Primer ``meta description``/``og:description`` no vacío."""
    for attrs in _META_DESCRIPTIONS:
        content = _meta(soup, attrs)
        if content:
            return content
    return ""


def headline(soup: BeautifulSoup) -> str:
    """``title``, ``h1`` y ``h2`` sin repetir, unidos con `` — ``."""
    parts: list[str] = []
    for name in ("title", "h1", "h2"):
        tag = soup.find(name)
        text = " ".join(tag.get_text(" ", strip=True).split()) if tag else ""
        if text and not any(text.lower() in part.lower() for part in parts):
            parts.append(text)
    return " — ".join(parts)


def _candidate_sentences(soup: BeautifulSoup) -> list[str]:
    root = soup.find("main") or soup.find("article") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in root.find_all("p")]
    blocks = paragraphs if len(paragraphs) >= 2 else [root.get_text(" ", strip=True)]
    sentences: list[str] = []
    for block in blocks:
        for sentence in _SENTENCE_SPLIT.split(" ".join(block.split())):
            if 40 <= len(sentence) <= 300 and len(sentence.split()) >= 6:
                sentences.append(sentence)
    return sentences


def _rank_sentences(sentences: Sequence[str], max_chars: int) -> str:
    if not sentences:
        return ""
    stop = stopwords_for("unknown")
    freq = Counter(w for s in sentences for w in tokenize(s) if w not in stop)

    def score(sentence: str) -> float:
        words = [w for w in tokenize(sentence) if w not in stop]
        return sum(freq[w] for w in words) / (len(words) or 1)

    ranked = sorted(range(len(sentences)), key=lambda i: score(sentences[i]), reverse=True)
    chosen: list[int] = []
    length = 0
    for index in ranked:
        if chosen and length + len(sentences[index]) > max_chars:
            continue
        chosen.append(index)
        length += len(sentences[index]) + 1
        if length >= max_chars * 0.6:
            break
    return clip(" ".join(sentences[i] for i in sorted(chosen)), max_chars)


def extractive_summary(html: str, max_chars: int = MAX_CHARS) -> str:
    """Las frases más representativas del texto principal, en su orden original."""
    return _rank_sentences(_candidate_sentences(content_soup(html)), max_chars)


def summarize(html: str, max_chars: int = MAX_CHARS) -> str:
    """Resumen de ~200 caracteres: description, si no extractivo, si no los títulos."""
    soup = make_soup(html)
    description = meta_description(soup)
    if len(description) >= _MIN_GOOD_DESCRIPTION:
        return clip(description, max_chars)
    if description:
        title_tag = soup.find("title")
        title = " ".join(title_tag.get_text(" ", strip=True).split()) if title_tag else ""
        if not title or title.lower() in description.lower():
            return clip(description, max_chars)
        if description.lower() in title.lower():
            return clip(title, max_chars)
        return clip(f"{title}: {description}", max_chars)
    return extractive_summary(html, max_chars) or clip(headline(soup), max_chars)


# --- Metadatos ----------------------------------------------------------------------


@dataclass(frozen=True)
class PageMeta:
    """Metadatos de una página ya parseados (sin red)."""

    title: str = ""
    description: str = ""
    og_description: str = ""
    twitter_description: str = ""
    og_type: str = ""
    og_site_name: str = ""
    keywords: str = ""
    h1: str = ""
    h2: tuple[str, ...] = ()
    lang: str = ""
    schema_types: tuple[str, ...] = ()
    schema_names: tuple[tuple[str, str], ...] = ()
    schema_descriptions: tuple[tuple[str, str], ...] = ()
    schema_country: str = ""
    links: tuple[str, ...] = ()


def _meta(soup: BeautifulSoup, attrs: dict[str, str]) -> str:
    tag = soup.find("meta", attrs=attrs)
    content = tag.get("content") if tag else None
    return " ".join(content.split()) if isinstance(content, str) else ""


def _text_of(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find(name)
    return " ".join(tag.get_text(" ", strip=True).split()) if tag else ""


def _walk_jsonld(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from _walk_jsonld(item)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement", "publisher", "author"):
            if key in node:
                yield from _walk_jsonld(node[key])


def jsonld_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Objetos JSON-LD de la página (aplana ``@graph`` y entidades anidadas)."""
    items: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        try:
            data = json.loads(raw.strip().rstrip(";")) if raw else None
        except ValueError:
            continue
        items.extend(_walk_jsonld(data))
    return items


def _types_of(item: dict[str, Any]) -> list[str]:
    raw = item.get("@type", [])
    values = raw if isinstance(raw, list) else [raw]
    return [str(v).rsplit("/", 1)[-1].lower() for v in values if v]


def _country_of(item: dict[str, Any]) -> str:
    address = item.get("address")
    addresses = address if isinstance(address, list) else [address]
    for entry in addresses:
        if isinstance(entry, dict):
            country = entry.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name")
            if isinstance(country, str) and len(country.strip()) == 2:
                return country.strip().upper()
    return ""


def extract_meta(html: str) -> PageMeta:
    """Lee título, descripciones, Open Graph, encabezados, JSON-LD y links."""
    soup = make_soup(html)
    items = jsonld_items(soup)
    types: list[str] = [t for item in items for t in _types_of(item)]
    types += [
        str(tag["itemtype"]).rstrip("/").rsplit("/", 1)[-1].lower()
        for tag in soup.find_all(attrs={"itemtype": True})
    ]
    names: list[tuple[str, str]] = []
    descriptions: list[tuple[str, str]] = []
    country = ""
    for item in items:
        kind = next(iter(_types_of(item)), "")
        if isinstance(item.get("name"), str) and item["name"].strip():
            names.append((kind, " ".join(item["name"].split())))
        if isinstance(item.get("description"), str) and item["description"].strip():
            descriptions.append((kind, " ".join(item["description"].split())))
        country = country or _country_of(item)
    html_tag = soup.find("html")
    lang = html_tag.get("lang") if html_tag else None
    return PageMeta(
        title=_text_of(soup, "title"),
        description=_meta(soup, {"name": "description"}),
        og_description=_meta(soup, {"property": "og:description"}),
        twitter_description=_meta(soup, {"name": "twitter:description"}),
        og_type=_meta(soup, {"property": "og:type"}),
        og_site_name=_meta(soup, {"property": "og:site_name"}),
        keywords=_meta(soup, {"name": "keywords"}),
        h1=_text_of(soup, "h1"),
        h2=tuple(" ".join(h.get_text(" ", strip=True).split()) for h in soup.find_all("h2")[:8]),
        lang=lang.strip() if isinstance(lang, str) else "",
        schema_types=tuple(dict.fromkeys(t for t in types if t)),
        schema_names=tuple(names),
        schema_descriptions=tuple(descriptions),
        schema_country=country,
        links=tuple(str(a["href"]) for a in soup.find_all("a", href=True)),
    )


# --- Limpieza -----------------------------------------------------------------------


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def title_parts(title: str) -> list[str]:
    """Partes de un ``<title>`` separadas por `` | ``, `` - ``, `` — ``, `` · ``..."""
    return [part.strip() for part in _TITLE_SEPARATORS.split(title) if part.strip()]


def clean_title(title: str, site_name: str = "") -> str:
    """Título sin el nombre del sitio ni partes genéricas como ``Home`` o ``Inicio``."""
    parts = title_parts(title)
    site = _norm(site_name)
    useful = [
        part
        for part in parts
        if part.lower() not in _GENERIC_TITLES and (not site or _norm(part) != site)
    ]
    return " — ".join(useful) if useful else (parts[0] if parts else "")


def strip_boilerplate(text: str, site_name: str = "") -> str:
    """Quita "Bienvenido a…", "Home |" y el nombre del sitio repetido al inicio."""
    text = " ".join(text.split())
    text = _WELCOME.sub("", text)
    parts = title_parts(text)
    while len(parts) > 1 and (
        parts[0].lower() in _GENERIC_TITLES or (site_name and _norm(parts[0]) == _norm(site_name))
    ):
        text = text[text.find(parts[1]) :]
        parts = parts[1:]
    return text[:1].upper() + text[1:] if text else ""


def guess_site_name(meta: PageMeta, host: str) -> str:
    """``og:site_name`` > nombre en JSON-LD > parte del título que coincide con el dominio."""
    if meta.og_site_name:
        return meta.og_site_name
    for kind, name in meta.schema_names:
        if kind in ("website", "organization", "corporation", "localbusiness", "store"):
            return name
    label = _norm(host.removeprefix("www.").split(".")[0])
    for part in title_parts(meta.title):
        if label and (_norm(part) == label or (label in _norm(part) and len(part) <= 40)):
            return part
    return host.removeprefix("www.")


def guess_country(host: str, meta: PageMeta) -> tuple[str | None, str | None]:
    """País (ISO alfa-2) como pista: ccTLD > dirección en schema.org > ``lang`` regional."""
    tld = host.rsplit(".", 1)[-1].lower() if "." in host else ""
    if len(tld) == 2 and tld.isalpha() and tld not in _GENERIC_CCTLDS:
        return _CCTLD_ALIASES.get(tld, tld.upper()), "tld"
    if meta.schema_country:
        return meta.schema_country, "schema"
    region = re.match(r"^[a-z]{2}[-_]([a-z]{2})$", meta.lang, re.I)
    if region:
        return region.group(1).upper(), "lang"
    return None, None


# --- Descripción --------------------------------------------------------------------


def _description_candidates(meta: PageMeta) -> Iterator[tuple[str, str]]:
    for kind, text in meta.schema_descriptions:
        if kind in _SITE_ENTITY_TYPES and len(text) >= _MIN_JSONLD_DESCRIPTION:
            yield "schema", text
    for source, text in (
        ("meta", meta.description),
        ("og", meta.og_description),
        ("twitter", meta.twitter_description),
    ):
        if text:
            yield source, text


def _extractive(pages: Iterable[str], max_chars: int) -> str:
    sentences = [
        sentence
        for html in pages
        for sentence in _candidate_sentences(content_soup(html))
        if not _BOILERPLATE.search(sentence)
    ]
    return _rank_sentences(list(dict.fromkeys(sentences)), max_chars)


def choose_description(
    meta: PageMeta, site_name: str, pages: Sequence[str], max_chars: int = DESCRIPTION_CHARS
) -> tuple[str, str]:
    """Mejor descripción disponible y de dónde salió (``schema``, ``meta``, ``extractive``...)."""
    short: tuple[str, str] | None = None
    for source, raw in _description_candidates(meta):
        text = strip_boilerplate(raw, site_name)
        if len(text) >= _MIN_GOOD_DESCRIPTION:
            return clip(text, max_chars), source
        short = short or (source, text)
    title = clean_title(meta.title, site_name)
    if short and short[1]:
        source, text = short
        if title and _norm(text) not in _norm(title) and _norm(title) not in _norm(text):
            return clip(f"{title}: {text}", max_chars), f"title+{source}"
        longest = max(text, title, key=len)
        return clip(longest, max_chars), source if longest == text else "title"
    extractive = _extractive(pages, max_chars)
    if extractive:
        return extractive, "extractive"
    parts = [p for p in dict.fromkeys((title, meta.h1)) if p]
    return clip(" — ".join(parts), max_chars), "headline" if parts else ""


def pick_internal_pages(
    urls: Iterable[str], home_url: str, limit: int = MAX_INTERNAL_PAGES
) -> list[str]:
    """Hasta ``limit`` páginas internas útiles (nosotros, productos, contacto, blog, docs)."""
    candidates = [u for u in dict.fromkeys(urls) if u.rstrip("/") != home_url.rstrip("/")]
    chosen: list[str] = []
    for _, pattern in INTERNAL_PAGE_GROUPS:
        matches = [u for u in candidates if re.search(pattern, urlparse(u).path, re.I)]
        if matches:
            chosen.append(min(matches, key=lambda u: (len(urlparse(u).path), u)))
        if len(chosen) >= limit:
            break
    return chosen


def looks_like_person(name: str) -> bool:
    """Nombre del sitio con forma de nombre de persona (2-4 palabras capitalizadas)."""
    return bool(_PERSON_NAME.match(name.strip())) and not _ORG_WORDS.search(name)


def describe(
    home_html: str,
    host: str,
    *,
    extra_pages: Sequence[str] = (),
    technologies: Sequence[str] = (),
) -> TopicResult:
    """Descripción concreta, categoría, nombre y país a partir de la home y páginas internas."""
    meta = extract_meta(home_html)
    extras = [extract_meta(html) for html in extra_pages]
    site_name = guess_site_name(meta, host)
    pages = [home_html, *extra_pages]
    description, source = choose_description(meta, site_name, pages)
    strong = " ".join(
        [meta.title, meta.description, meta.og_description, meta.h1, *meta.h2, meta.keywords]
        + [text for _, text in meta.schema_descriptions]
    )
    body = " ".join(visible_text(html) for html in pages)[:30000]
    category = classify_category(
        CategoryInput(
            schema_types=[t for m in (meta, *extras) for t in m.schema_types],
            og_type=meta.og_type,
            host=host,
            technologies=technologies,
            links=meta.links,
            strong_text=strong,
            body_text=body,
            extra=(
                (CategorySignal("portfolio", "name:person", 4),)
                if looks_like_person(site_name)
                else ()
            ),
        )
    )
    country, country_source = guess_country(host, meta)
    return TopicResult(
        description=description,
        category=category,
        site_name=site_name,
        description_source=source,
        country=country,
        country_source=country_source,
        pages_analyzed=len(pages),
    )

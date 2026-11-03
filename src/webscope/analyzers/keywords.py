"""Palabras clave por frecuencia ponderada y detección simple del idioma de la web."""

from __future__ import annotations

from collections import Counter

from bs4 import BeautifulSoup

from webscope.analyzers._text import count_stopwords, stopwords_for, tokenize
from webscope.parsing import content_soup, make_soup

DEFAULT_LIMIT = 8
_MIN_STOPWORD_HITS = 5
# Peso extra de cada zona del HTML respecto del texto común (peso 1).
_ZONE_WEIGHTS: tuple[tuple[str, int], ...] = (("title", 4), ("h1", 3), ("h2", 2), ("h3", 2))
_META_WEIGHTS: tuple[tuple[dict[str, str], int], ...] = (
    ({"name": "keywords"}, 3),
    ({"name": "description"}, 2),
    ({"property": "og:title"}, 2),
)


def detect_language(html: str) -> str:
    """Código de idioma de la web según ``<html lang>`` o stopwords dominantes."""
    soup = make_soup(html)
    tag = soup.find("html")
    lang = tag.get("lang") if tag else None
    if isinstance(lang, str) and lang.strip():
        return lang.strip().lower().replace("_", "-").split("-")[0]
    words = tokenize(content_soup(html).get_text(" "))
    es, en = count_stopwords(words)
    if max(es, en) < _MIN_STOPWORD_HITS:
        return "unknown"
    return "es" if es > en else "en"


def _weighted_counts(soup: BeautifulSoup, body: BeautifulSoup) -> Counter[str]:
    counts: Counter[str] = Counter(tokenize(body.get_text(" ")))
    for name, weight in _ZONE_WEIGHTS:
        for tag in soup.find_all(name):
            for word in tokenize(tag.get_text(" ")):
                counts[word] += weight
    for attrs, weight in _META_WEIGHTS:
        tag = soup.find("meta", attrs=attrs)
        content = tag.get("content") if tag else None
        if isinstance(content, str):
            for word in tokenize(content):
                counts[word] += weight
    return counts


def _merge_plurals(counts: Counter[str]) -> Counter[str]:
    """Une ``zapatilla``/``zapatillas`` quedándose con la forma más frecuente."""
    merged = Counter(counts)
    for word in sorted(counts, key=len, reverse=True):
        for suffix in ("es", "s"):
            singular = word[: -len(suffix)]
            if word.endswith(suffix) and singular in merged and word in merged:
                keep, drop = sorted((word, singular), key=merged.__getitem__, reverse=True)
                merged[keep] += merged.pop(drop)
                break
    return merged


def extract_keywords(
    html: str, site_lang: str | None = None, limit: int = DEFAULT_LIMIT
) -> tuple[str, ...]:
    """Top ``limit`` palabras clave, sin stopwords, números ni palabras cortas."""
    lang = site_lang or detect_language(html)
    stop = stopwords_for(lang)
    counts = _weighted_counts(make_soup(html), content_soup(html))
    filtered = Counter({word: n for word, n in counts.items() if word not in stop})
    ranked = _merge_plurals(filtered).most_common()
    return tuple(word for word, score in ranked[:limit] if score >= 2)

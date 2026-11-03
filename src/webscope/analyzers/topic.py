"""Resumen corto de qué trata la web a partir de metadatos o del texto principal."""

from __future__ import annotations

import re
from collections import Counter

from bs4 import BeautifulSoup

from webscope.analyzers._text import stopwords_for, tokenize
from webscope.parsing import content_soup, make_soup

MAX_CHARS = 200
_MIN_GOOD_DESCRIPTION = 60
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_META_DESCRIPTIONS = (
    {"name": "description"},
    {"property": "og:description"},
    {"name": "twitter:description"},
)


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
        tag = soup.find("meta", attrs=attrs)
        content = tag.get("content") if tag else None
        if isinstance(content, str) and content.strip():
            return " ".join(content.split())
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


def extractive_summary(html: str, max_chars: int = MAX_CHARS) -> str:
    """Las frases más representativas del texto principal, en su orden original."""
    sentences = _candidate_sentences(content_soup(html))
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

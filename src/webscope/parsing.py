"""Helpers de parseo HTML compartidos por analizadores y crawler (sin red)."""

from __future__ import annotations

import importlib.util

from bs4 import BeautifulSoup

PARSER = "lxml" if importlib.util.find_spec("lxml") else "html.parser"
NON_CONTENT_TAGS = ("script", "style", "noscript", "template", "svg", "iframe")
LAYOUT_TAGS = ("nav", "footer", "header", "aside", "form")


def make_soup(html: str) -> BeautifulSoup:
    """Parsea ``html`` con ``lxml`` si está instalado; si no, con ``html.parser``."""
    return BeautifulSoup(html, PARSER)


def content_soup(html: str) -> BeautifulSoup:
    """Soup sin scripts, estilos ni bloques de navegación/pie: solo el contenido."""
    soup = make_soup(html)
    for tag in soup.find_all([*NON_CONTENT_TAGS, *LAYOUT_TAGS]):
        tag.decompose()
    return soup


def visible_text(html: str) -> str:
    """Texto visible del contenido principal, con espacios colapsados."""
    soup = content_soup(html)
    root = soup.find("main") or soup.find("article") or soup.body or soup
    return " ".join(root.get_text(" ", strip=True).split())

"""Analizadores puros: reciben HTML, headers o registros ya obtenidos y devuelven datos o códigos.

No hacen red ni conocen el idioma de la interfaz.
"""

from webscope.analyzers.keywords import detect_language, extract_keywords
from webscope.analyzers.site_type import classify
from webscope.analyzers.tech import detect_technologies
from webscope.analyzers.topic import summarize

__all__ = ["classify", "detect_language", "detect_technologies", "extract_keywords", "summarize"]

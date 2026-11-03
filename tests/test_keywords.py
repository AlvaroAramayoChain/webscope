from collections.abc import Callable

from webscope.analyzers._text import STOPWORDS_EN, STOPWORDS_ES, stopwords_for, tokenize
from webscope.analyzers.keywords import detect_language, extract_keywords


def test_spanish_keywords(load_fixture: Callable[[str], str]) -> None:
    keywords = extract_keywords(load_fixture("wordpress.html"))
    assert 5 <= len(keywords) <= 8
    assert keywords[0] == "zapatillas"
    assert {"running", "trail"} <= set(keywords)


def test_keywords_have_no_stopwords_numbers_or_short_words(
    load_fixture: Callable[[str], str],
) -> None:
    for fixture in ("wordpress.html", "static.html"):
        for word in extract_keywords(load_fixture(fixture)):
            assert word not in STOPWORDS_ES | STOPWORDS_EN
            assert len(word) >= 3
            assert word.isalpha()


def test_english_keywords(load_fixture: Callable[[str], str]) -> None:
    keywords = extract_keywords(load_fixture("static.html"))
    assert "bread" in keywords
    assert "sourdough" in keywords


def test_title_and_headings_weigh_more() -> None:
    body = " ".join(["manzana"] * 4)
    html = f"<title>Naranjas</title><h1>Naranjas</h1><p>{body}</p>"
    assert extract_keywords(html)[0] == "naranjas"


def test_plurals_are_merged() -> None:
    html = "<p>zapatilla zapatillas zapatillas zapatillas calzado calzado</p>"
    keywords = extract_keywords(html)
    assert "zapatillas" in keywords
    assert "zapatilla" not in keywords


def test_detect_language_from_html_lang(load_fixture: Callable[[str], str]) -> None:
    assert detect_language(load_fixture("wordpress.html")) == "es"
    assert detect_language('<html lang="pt-BR"><body></body></html>') == "pt"


def test_detect_language_from_stopwords(load_fixture: Callable[[str], str]) -> None:
    assert detect_language(load_fixture("static.html")) == "en"
    spanish = (
        "<p>" + "el pan de la casa es para los vecinos y las familias del barrio " * 3 + "</p>"
    )
    assert detect_language(spanish) == "es"
    assert detect_language("<p>hola</p>") == "unknown"


def test_english_sites_keep_words_that_are_spanish_stopwords() -> None:
    # "son" es stopword en español pero una palabra válida en inglés.
    assert "son" not in stopwords_for("en")
    assert "son" in stopwords_for("es")


def test_tokenize_ignores_numbers_and_short_words() -> None:
    assert tokenize("El año 2026 trae 3 ofertas: envío ya") == ["año", "trae", "ofertas", "envío"]

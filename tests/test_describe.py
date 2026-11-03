"""Tests de la descripción concreta v2 (``describe`` y sus helpers)."""

from collections.abc import Callable

import pytest

from webscope.analyzers.topic import (
    clean_title,
    describe,
    extract_meta,
    guess_country,
    pick_internal_pages,
    strip_boilerplate,
)


def test_describe_woocommerce(load_fixture: Callable[[str], str]) -> None:
    topic = describe(load_fixture("woocommerce.html"), "calzadospampa.example")
    # Se quita el "Bienvenidos a Calzados Pampa." del principio.
    assert topic.description.startswith("Tienda online de calzado deportivo")
    assert topic.site_name == "Calzados Pampa"
    assert topic.country == "AR"
    assert topic.country_source == "schema"
    assert len(topic.description) <= 200


def test_extract_meta_flattens_jsonld_graph(load_fixture: Callable[[str], str]) -> None:
    meta = extract_meta(load_fixture("woocommerce.html"))
    assert {"organization", "website"} <= set(meta.schema_types)
    assert meta.og_site_name == "Calzados Pampa"
    assert meta.schema_country == "AR"


def test_broken_jsonld_is_ignored() -> None:
    html = '<script type="application/ld+json">{not json</script><title>Hola</title>'
    assert extract_meta(html).schema_types == ()


def test_short_description_combines_with_clean_title() -> None:
    html = (
        "<title>Orbit — Project management for small teams</title>"
        '<meta name="description" content="Plan, track, ship.">'
        '<meta property="og:site_name" content="Orbit">'
    )
    topic = describe(html, "orbit.example")
    assert topic.description == "Project management for small teams: Plan, track, ship."


def test_extractive_uses_internal_pages_and_skips_cookie_banners() -> None:
    home = "<html><body><p>Hi.</p></body></html>"
    about = (
        "<main><p>We use cookies to improve your experience on this website, accept them.</p>"
        "<p>Our studio restores antique wooden furniture with traditional techniques.</p>"
        "<p>Every restoration of antique wooden furniture is documented for the owner.</p></main>"
    )
    topic = describe(home, "studio.example", extra_pages=[about])
    assert "antique wooden furniture" in topic.description
    assert "cookies" not in topic.description
    assert topic.description_source == "extractive"
    assert topic.pages_analyzed == 2


@pytest.mark.parametrize(
    ("title", "site", "expected"),
    [
        ("Inicio | Calzados Pampa", "Calzados Pampa", "Inicio"),
        ("Home - Flowly - Automate work", "Flowly", "Automate work"),
        (
            "Zapas Run | Zapatillas deportivas y running",
            "Zapas Run",
            "Zapatillas deportivas y running",
        ),
    ],
)
def test_clean_title(title: str, site: str, expected: str) -> None:
    assert clean_title(title, site) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Bienvenidos a Calzados Pampa. Tienda online de calzado.", "Tienda online de calzado."),
        ("Welcome to Flowly! Automate your work.", "Automate your work."),
        ("Home | Flowly | Automate your work", "Automate your work"),
    ],
)
def test_strip_boilerplate(text: str, expected: str) -> None:
    assert strip_boilerplate(text, "Flowly") == expected


def test_pick_internal_pages_one_per_group() -> None:
    urls = [
        "https://x.example/",
        "https://x.example/nosotros",
        "https://x.example/productos/zapatilla-1",
        "https://x.example/productos",
        "https://x.example/contacto",
        "https://x.example/blog",
        "https://x.example/blog/post-1",
        "https://x.example/carrito",
    ]
    chosen = pick_internal_pages(urls, "https://x.example/")
    assert chosen == [
        "https://x.example/nosotros",
        "https://x.example/productos",
        "https://x.example/contacto",
        "https://x.example/blog",
    ]
    assert len(pick_internal_pages(urls * 3, "https://x.example/", limit=2)) == 2


@pytest.mark.parametrize(
    ("host", "lang", "expected"),
    [
        ("tienda.com.ar", "", ("AR", "tld")),
        ("shop.co.uk", "", ("GB", "tld")),
        ("app.io", "es-MX", ("MX", "lang")),
        ("example.com", "en", (None, None)),
    ],
)
def test_guess_country(host: str, lang: str, expected: tuple[str | None, str | None]) -> None:
    meta = extract_meta(f'<html lang="{lang}"></html>')
    assert guess_country(host, meta) == expected

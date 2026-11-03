from collections.abc import Callable

import pytest

from webscope.analyzers.category import (
    CATEGORIES,
    KEYWORDS,
    SCHEMA_TYPES,
    CategoryInput,
    classify_category,
)
from webscope.analyzers.topic import describe
from webscope.i18n import MESSAGES


def test_ecommerce_from_woocommerce_fixture(load_fixture: Callable[[str], str]) -> None:
    topic = describe(
        load_fixture("woocommerce.html"), "calzadospampa.example", technologies=["WooCommerce"]
    )
    assert topic.category.code == "ecommerce"
    assert topic.category.confidence in ("medium", "high")
    reasons = {s.reason for s in topic.category.signals}
    assert "tech:WooCommerce" in reasons


def test_blog_from_jsonld(load_fixture: Callable[[str], str]) -> None:
    topic = describe(load_fixture("blog.html"), "bitacoraandina.example", technologies=["Ghost"])
    assert topic.category.code == "blog_media"
    assert any(s.reason == "schema:blogposting" for s in topic.category.signals)


def test_saas_from_software_application(load_fixture: Callable[[str], str]) -> None:
    topic = describe(load_fixture("saas.html"), "flowly.example", technologies=["Stripe"])
    assert topic.category.code == "saas"
    assert topic.description.startswith("Flowly is a workflow automation platform")
    assert topic.description_source == "schema"


def test_undetermined_when_there_is_no_evidence() -> None:
    html = "<html><body><p>Hola.</p></body></html>"
    result = describe(html, "algo.example")
    assert result.category.code == "unknown"
    assert result.category.confidence == "low"


def test_close_tie_is_undetermined() -> None:
    data = CategoryInput(schema_types=["Product", "BlogPosting"])
    assert classify_category(data).code == "unknown"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("www.argentina.gob.ar", "government"),
        ("uba.edu.ar", "education"),
        ("cam.ac.uk", "education"),
    ],
)
def test_tld_hints(host: str, expected: str) -> None:
    assert classify_category(CategoryInput(host=host)).code == expected


def test_person_name_counts_as_portfolio() -> None:
    html = (
        "<html><head><title>Ana Pérez</title>"
        "<meta name='description' content='Full stack developer based in Córdoba. "
        "Selected work, skills and contact.'></head><body></body></html>"
    )
    assert describe(html, "anaperez.example").category.code == "portfolio"


def test_dictionaries_are_consistent() -> None:
    assert set(KEYWORDS) <= set(CATEGORIES)
    assert {category for category, _ in SCHEMA_TYPES.values()} <= set(CATEGORIES)
    for phrases in KEYWORDS.values():
        assert all(phrase == phrase.lower() and weight > 0 for phrase, weight in phrases.items())


@pytest.mark.parametrize("lang", ["es", "en"])
def test_every_category_is_translated(lang: str) -> None:
    for code in (*CATEGORIES, "unknown"):
        assert f"category.{code}" in MESSAGES[lang]

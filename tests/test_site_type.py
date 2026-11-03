from collections.abc import Callable

import pytest

from webscope.analyzers.site_type import classify, confidence_for


def codes(html: str) -> set[str]:
    return {signal.code for signal in classify(html).signals}


def test_react_spa_is_an_app(load_fixture: Callable[[str], str]) -> None:
    result = classify(load_fixture("react_spa.html"))
    assert result.kind == "app"
    assert result.confidence == "high"
    assert {"spa_root", "noscript_js", "manifest", "service_worker", "many_scripts"} <= {
        s.code for s in result.signals
    }


def test_wordpress_is_a_site(load_fixture: Callable[[str], str]) -> None:
    result = classify(load_fixture("wordpress.html"))
    assert result.kind == "site"
    assert result.confidence == "high"
    assert {"paragraphs", "nav_links", "blog", "info_pages", "cms_generator"} <= {
        s.code for s in result.signals
    }


def test_static_site_is_a_site(load_fixture: Callable[[str], str]) -> None:
    result = classify(load_fixture("static.html"))
    assert result.kind == "site"
    assert result.site_score > result.app_score


def test_scores_match_signals(load_fixture: Callable[[str], str]) -> None:
    result = classify(load_fixture("nextjs_tailwind.html"))
    assert result.app_score == sum(s.weight for s in result.signals if s.target == "app")
    assert result.site_score == sum(s.weight for s in result.signals if s.target == "site")
    assert "app_routes" in {s.code for s in result.signals}


def test_password_form_counts_for_app() -> None:
    assert "password_form" in codes('<form><input type="password" name="p"></form>')


def test_empty_html_defaults_to_low_confidence() -> None:
    result = classify("")
    assert result.kind in ("site", "app")
    assert result.confidence in ("low", "medium")


@pytest.mark.parametrize(
    ("margin", "expected"), [(0, "low"), (1, "low"), (2, "medium"), (5, "high")]
)
def test_confidence_thresholds(margin: int, expected: str) -> None:
    assert confidence_for(margin) == expected

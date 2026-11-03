from collections.abc import Callable

import pytest

from webscope.analyzers.site_type import STRONG_APP_SIGNALS, classify, confidence_for


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


# --- Poco texto sin señales fuertes de app ---------------------------------------------


def test_minimal_page_is_a_low_confidence_site(load_fixture: Callable[[str], str]) -> None:
    result = classify(load_fixture("minimal.html"))
    assert result.kind == "site"
    assert result.confidence == "low"
    # La señal de poco texto se sigue informando (sirve en --verbose).
    assert "little_text" in {s.code for s in result.signals}
    assert not {s.code for s in result.signals} & STRONG_APP_SIGNALS


@pytest.mark.parametrize(
    "extra",
    [
        '<div id="root"></div>',
        '<link rel="manifest" href="/manifest.json">',
        "<script>navigator.serviceWorker.register('/sw.js')</script>",
        '<a href="/dashboard">Dashboard</a>',
        '<script type="module" src="/assets/index-a1b2c3d4.js"></script>',
    ],
)
def test_minimal_page_with_a_strong_signal_is_an_app(
    load_fixture: Callable[[str], str], extra: str
) -> None:
    html = load_fixture("minimal.html").replace("</body>", f"{extra}</body>")
    assert classify(html).kind == "app"


def test_empty_html_is_never_an_app() -> None:
    result = classify("")
    assert (result.kind, result.confidence) == ("site", "low")

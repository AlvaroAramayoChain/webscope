from collections.abc import Callable

from webscope.analyzers.topic import MAX_CHARS, clip, extractive_summary, summarize


def test_uses_meta_description_when_long_enough(load_fixture: Callable[[str], str]) -> None:
    summary = summarize(load_fixture("wordpress.html"))
    assert summary.startswith("Tienda online de zapatillas deportivas")


def test_short_description_is_combined_with_title(load_fixture: Callable[[str], str]) -> None:
    # <meta description="Orbit"> es muy corta: se le antepone el <title>.
    summary = summarize(load_fixture("nextjs_tailwind.html"))
    assert summary == "Orbit — Project management for small teams"


def test_falls_back_to_extractive_summary(load_fixture: Callable[[str], str]) -> None:
    summary = summarize(load_fixture("static.html"))
    assert "sourdough" in summary.lower()
    assert len(summary) <= MAX_CHARS
    # No incluye texto de <nav> ni de <footer>.
    assert "Download menu" not in summary
    assert "Old Town Street" not in summary


def test_uses_headline_when_there_is_no_text(load_fixture: Callable[[str], str]) -> None:
    assert summarize(load_fixture("react_spa.html")) == "Acme Dashboard"


def test_ignores_scripts_and_styles() -> None:
    html = (
        "<script>var secret = 'do not show this sentence anywhere please';</script>"
        "<style>.x{}</style>"
        "<p>This bakery bakes bread every single morning for the neighborhood.</p>"
        "<p>Our croissants are made with butter and patience by a small family team.</p>"
    )
    summary = extractive_summary(html)
    assert "secret" not in summary
    assert "bakery" in summary


def test_clip_cuts_on_word_boundary() -> None:
    text = "palabra " * 60
    clipped = clip(text, 50)
    assert len(clipped) <= 50
    assert clipped.endswith("…")
    assert "palab…" not in clipped


def test_empty_html_returns_empty_summary() -> None:
    assert summarize("") == ""

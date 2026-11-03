from collections.abc import Callable

import pytest

from webscope.analyzers.tech import CATEGORY_ORDER, SIGNATURES, detect_technologies


def names(html: str, headers: dict[str, str] | None = None) -> list[str]:
    return [tech.name for tech in detect_technologies(html, headers)]


def test_wordpress_site(load_fixture: Callable[[str], str]) -> None:
    found = names(load_fixture("wordpress.html"), {"Server": "nginx"})
    for expected in ("HTML", "CSS", "JavaScript", "PHP", "WordPress", "jQuery", "nginx"):
        assert expected in found
    assert "React" not in found


def test_react_spa_with_typescript_hints(load_fixture: Callable[[str], str]) -> None:
    found = names(load_fixture("react_spa.html"))
    assert {"React", "TypeScript", "JavaScript"} <= set(found)
    assert "WordPress" not in found


def test_next_implies_react_and_detects_tailwind(load_fixture: Callable[[str], str]) -> None:
    found = names(load_fixture("nextjs_tailwind.html"), {"X-Powered-By": "Next.js"})
    assert {"Next.js", "React", "Tailwind CSS"} <= set(found)


def test_static_site_with_bootstrap_and_django(load_fixture: Callable[[str], str]) -> None:
    found = names(load_fixture("static.html"))
    assert {"Bootstrap", "Django", "Python"} <= set(found)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Server": "cloudflare", "CF-RAY": "8a1b"}, "Cloudflare"),
        ({"Server": "Apache/2.4.58 (Ubuntu)"}, "Apache"),
        ({"X-Powered-By": "PHP/8.3.1"}, "PHP"),
        ({"X-Powered-By": "ASP.NET"}, "ASP.NET"),
        ({"Set-Cookie": "XSRF-TOKEN=a; laravel_session=b; path=/"}, "Laravel"),
        ({"X-ShopId": "12345"}, "Shopify"),
        ({"x-vercel-id": "gru1::abc"}, "Vercel"),
    ],
)
def test_detects_from_headers(headers: dict[str, str], expected: str) -> None:
    assert expected in names("<html><body></body></html>", headers)


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ('<div id="__nuxt"></div><script>window.__NUXT__={}</script>', "Nuxt"),
        ('<app-root ng-version="17.3.0"></app-root>', "Angular"),
        ('<div class="svelte-1xyz9ab">hola</div>', "Svelte"),
        ('<div data-v-1a2b3c4d class="card"></div>', "Vue"),
        ('<img src="https://static.wixstatic.com/media/a.png">', "Wix"),
        ('<link href="//cdn.shopify.com/s/files/theme.css" rel="stylesheet">', "Shopify"),
        ('<input type="hidden" name="__VIEWSTATE" value="x">', "ASP.NET"),
    ],
)
def test_detects_from_html(snippet: str, expected: str) -> None:
    assert expected in names(f"<html><body>{snippet}</body></html>")


def test_results_are_grouped_by_category(load_fixture: Callable[[str], str]) -> None:
    techs = detect_technologies(load_fixture("wordpress.html"), {"Server": "nginx"})
    positions = [CATEGORY_ORDER.index(tech.category) for tech in techs]
    assert positions == sorted(positions)


def test_signatures_are_consistent() -> None:
    known = {sig.name for sig in SIGNATURES}
    assert len(known) == len(SIGNATURES), "nombres duplicados"
    for sig in SIGNATURES:
        assert sig.category in CATEGORY_ORDER
        assert set(sig.implies) <= known


def test_nothing_detected_for_empty_input() -> None:
    assert detect_technologies("") == ()

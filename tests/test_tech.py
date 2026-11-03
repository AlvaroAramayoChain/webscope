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


# --- v2: versiones y tecnologías nuevas ----------------------------------------------


def versions(html: str, headers: dict[str, str] | None = None) -> dict[str, str | None]:
    return {tech.name: tech.version for tech in detect_technologies(html, headers)}


def test_versions_from_wordpress_fixture(load_fixture: Callable[[str], str]) -> None:
    found = versions(load_fixture("wordpress.html"))
    assert found["WordPress"] == "6.6.2"
    assert found["jQuery"] == "3.7.1"


def test_woocommerce_fixture_detects_stack_and_versions(load_fixture: Callable[[str], str]) -> None:
    found = versions(load_fixture("woocommerce.html"))
    assert found["WooCommerce"] == "8.5.2"
    assert found["Bootstrap"] == "5.3.2"
    assert found["WordPress"] == "6.4.3"
    assert "Google Tag Manager" in found


@pytest.mark.parametrize(
    ("headers", "name", "version"),
    [
        ({"Server": "nginx/1.25.3"}, "nginx", "1.25.3"),
        ({"Server": "Apache/2.4.58 (Ubuntu)"}, "Apache", "2.4.58"),
        ({"X-Powered-By": "PHP/8.1.2"}, "PHP", "8.1.2"),
        ({"Server": "Werkzeug/3.0.1 Python/3.12.1"}, "Flask", "3.0.1"),
        ({"X-AspNet-Version": "4.0.30319"}, "ASP.NET", "4.0.30319"),
    ],
)
def test_versions_from_headers(headers: dict[str, str], name: str, version: str) -> None:
    assert versions("<html></html>", headers)[name] == version


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ('<div class="et_pb_section"></div>', "Divi"),
        (
            '<link href="/wp-content/plugins/elementor/assets/css/frontend.min.css?ver=3.18.0">',
            "Elementor",
        ),
        ('<script type="text/x-magento-init">{}</script>', "Magento"),
        ('<meta name="generator" content="PrestaShop">', "PrestaShop"),
        ("<script>window.__remixContext = {}</script>", "Remix"),
        ('<a data-sveltekit-preload-data href="/">x</a>', "SvelteKit"),
        (
            '<script src="https://www.google-analytics.com/analytics.js"></script>',
            "Google Analytics",
        ),
        ("<script>fbq('init', '123');</script>", "Meta Pixel"),
        ('<script src="https://static.hotjar.com/c/hotjar-1.js"></script>', "Hotjar"),
        ('<div class="g-recaptcha"></div>', "reCAPTCHA"),
        ('<script src="https://js.stripe.com/v3/"></script>', "Stripe"),
        ('<div class="cf-turnstile"></div>', "Cloudflare Turnstile"),
        ('<meta name="generator" content="Astro v4.2.1">', "Astro"),
    ],
)
def test_new_technologies(snippet: str, expected: str) -> None:
    assert expected in names(f"<html><body>{snippet}</body></html>")


def test_spring_and_java_from_cookie() -> None:
    found = names(
        "<html></html>", {"X-Application-Context": "app:8080", "Set-Cookie": "JSESSIONID=1"}
    )
    assert {"Spring", "Java"} <= set(found)


def test_github_pages_is_case_sensitive() -> None:
    assert "GitHub Pages" in names("<html></html>", {"Server": "GitHub.com"})
    assert "GitHub Pages" not in names("<html></html>", {"Server": "github.com"})


def test_every_signature_version_regex_has_a_group() -> None:
    import re

    for sig in SIGNATURES:
        for _, pattern in sig.versions:
            assert re.compile(pattern).groups >= 1, sig.name

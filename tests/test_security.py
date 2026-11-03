import json
from collections.abc import Callable
from datetime import datetime, timezone

import pytest

from webscope.analyzers.security import (
    analyze_content,
    analyze_email,
    analyze_headers,
    build_security,
    csp_issues,
    find_leaks,
    find_surface,
    grade_for,
    parse_cookie,
    parse_hsts,
    parse_security_txt,
    sensitive_robots_paths,
    spf_qualifier,
)
from webscope.models import DnsRecords

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)


@pytest.fixture
def headers(load_fixture: Callable[[str], str]) -> Callable[[str], dict[str, str]]:
    return lambda name: json.loads(load_fixture(f"headers_{name}.json"))


# --- Headers ------------------------------------------------------------------------


def test_good_headers_get_an_a(headers: Callable[[str], dict[str, str]]) -> None:
    report = analyze_headers(headers("good"), https=True)
    assert (report.score, report.max_score, report.grade) == (8, 8, "A")
    assert all(check.present for check in report.checks)
    assert report.extra == {"cross-origin-opener-policy": "same-origin"}


def test_bad_headers_get_low_grade_and_issues(headers: Callable[[str], dict[str, str]]) -> None:
    report = analyze_headers(headers("bad"), https=True)
    by_name = {check.name: check for check in report.checks}
    assert by_name["Strict-Transport-Security"].issues == ("short-max-age",)
    assert set(by_name["Content-Security-Policy"].issues) == {
        "unsafe-inline",
        "unsafe-eval",
        "wildcard",
    }
    assert not by_name["X-Frame-Options"].present
    assert report.score == 2
    assert report.grade == "D"


def test_hsts_does_not_count_on_http() -> None:
    report = analyze_headers({"Strict-Transport-Security": "max-age=63072000"}, https=False)
    assert report.checks[0].points == 0


@pytest.mark.parametrize(
    ("score", "grade"), [(8, "A"), (7, "A"), (6, "B"), (4, "C"), (2, "D"), (1, "F")]
)
def test_grade_scale(score: int, grade: str) -> None:
    assert grade_for(score) == grade


def test_parse_hsts_and_csp_nonce() -> None:
    assert parse_hsts("max-age=31536000; includeSubDomains; preload") == (31536000, True, True)
    assert parse_hsts("includeSubDomains") == (None, True, False)
    assert csp_issues("script-src 'self' 'unsafe-inline' 'nonce-abc'") == ()
    assert csp_issues("default-src https:") == ("wildcard",)


# --- Fugas y cookies ----------------------------------------------------------------


def test_leaks_from_headers_meta_and_comments(
    headers: Callable[[str], dict[str, str]], load_fixture: Callable[[str], str]
) -> None:
    leaks = find_leaks(headers("bad"), load_fixture("woocommerce.html"))
    sources = {leak.source for leak in leaks}
    assert {
        "server",
        "x-powered-by",
        "x-aspnet-version",
        "meta-generator",
        "html-comment",
    } <= sources
    comment = next(leak for leak in leaks if leak.source == "html-comment")
    assert "Yoast SEO plugin v21.9" in comment.value


def test_server_without_version_is_not_a_leak() -> None:
    assert find_leaks({"Server": "nginx"}, "") == ()


def test_parse_cookie_attributes() -> None:
    good = parse_cookie("__Host-session=abc; Path=/; Secure; HttpOnly; SameSite=Lax")
    bad = parse_cookie("PHPSESSID=xyz; path=/")
    assert good is not None and bad is not None
    assert (good.secure, good.httponly, good.samesite, good.prefix) == (
        True,
        True,
        "Lax",
        "__Host-",
    )
    assert (bad.secure, bad.httponly, bad.samesite, bad.prefix) == (False, False, None, None)
    assert parse_cookie("garbage") is None


# --- Email --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ("v=spf1 include:_spf.google.com -all", "-all"),
        ("v=spf1 mx ~all", "~all"),
        ("v=spf1 ?all", "?all"),
        ("v=spf1 all", "+all"),
        ("v=spf1 redirect=_spf.example.com", "redirect"),
        ("v=spf1 include:x.example", None),
    ],
)
def test_spf_qualifier(record: str, expected: str | None) -> None:
    assert spf_qualifier(record) == expected


def test_email_posture_valid_records() -> None:
    dns = DnsRecords(
        mx=("10 aspmx.l.google.com",),
        txt=("google-site-verification=abc", "v=spf1 include:_spf.google.com ~all"),
        dmarc=("v=DMARC1; p=reject; rua=mailto:d@example.com",),
        dkim=("google",),
        mta_sts=("v=STSv1; id=1",),
    )
    email = analyze_email(dns)
    assert email.has_mx and email.spf_all == "~all" and email.spf_records == 1
    assert email.dmarc_policy == "reject"
    assert email.dkim_selectors == ("google",)
    assert email.mta_sts and not email.bimi


def test_email_posture_invalid_records() -> None:
    dns = DnsRecords(
        mx=("0 .",),
        txt=("v=spf1 +all", "v=spf1 -all"),
        dmarc=("v=DMARC1; p=none",),
        unanswered=("dkim",),
    )
    email = analyze_email(dns)
    assert not email.has_mx  # MX nulo
    assert email.spf_records == 2
    assert email.dmarc_policy == "none"
    assert email.unanswered == ("dkim",)


# --- Archivos -----------------------------------------------------------------------


def test_security_txt_parsing() -> None:
    text = "Contact: mailto:security@example.com\nExpires: 2026-01-01T00:00:00Z\n"
    parsed = parse_security_txt(text, NOW)
    assert parsed is not None
    assert parsed.contacts == ("mailto:security@example.com",)
    assert parsed.expired
    assert parse_security_txt("<html>404</html>", NOW) is None
    assert parse_security_txt("Policy: x", NOW) is None


def test_sensitive_robots_paths() -> None:
    robots = "User-agent: *\nDisallow: /admin/\nDisallow: /tienda/\nDisallow: /backup.sql # old\n"
    assert sensitive_robots_paths(robots) == ("/admin/", "/backup.sql")


# --- Contenido y superficie ---------------------------------------------------------


def test_content_from_woocommerce(load_fixture: Callable[[str], str]) -> None:
    content = analyze_content(load_fixture("woocommerce.html"), "https://calzadospampa.example/")
    assert "cdn.jsdelivr.net" in content.third_party
    assert any("swiper" in url for url in content.scripts_without_sri)
    assert any("bootstrap" in url for url in content.styles_without_sri)
    assert content.mixed == ("http://ads.example.net/tracker.js",)
    assert content.forms.count == 2 and content.forms.login == 1
    assert content.forms.external_actions == ("https://newsletter.example.org/subscribe",)
    assert content.blank_without_noopener == 1


def test_login_form_page(load_fixture: Callable[[str], str]) -> None:
    content = analyze_content(load_fixture("login_form.html"), "https://acme.example/login")
    forms = content.forms
    assert forms.login == 2
    assert forms.insecure_actions == ("http://login.acme.example/session",)
    assert forms.external_actions == ("https://auth.partner.example/sso",)
    assert forms.password_autocomplete == 1
    assert content.mixed == ("http://acme.example/logo.png",)


def test_surface_endpoints_and_subdomains(load_fixture: Callable[[str], str]) -> None:
    surface = find_surface(
        load_fixture("login_form.html"),
        "https://acme.example/login",
        sans=("acme.example", "*.acme.example", "mail.acme.example"),
    )
    assert "/api/v1/status" in surface.endpoints
    assert "/graphql" in surface.endpoints
    assert {"mail.acme.example", "docs.acme.example", "login.acme.example"} <= set(
        surface.subdomains
    )
    assert "*.acme.example" not in surface.subdomains


def test_build_security_without_dns_or_files() -> None:
    result = build_security(page_url="https://x.example/", headers={}, html="<html></html>")
    assert result.https
    assert result.email is None
    assert result.files.robots is None and result.files.sitemap is None
    assert result.headers.grade == "F"

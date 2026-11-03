import re

import pytest

from webscope.analyzers.findings import RULES, FindingContext, Rule, evaluate
from webscope.analyzers.security import build_security
from webscope.i18n import MESSAGES, SUPPORTED_LANGS
from webscope.models import (
    SEVERITY_ORDER,
    DnsRecords,
    HttpRedirect,
    InfraResult,
    Technology,
    TlsResult,
)

# Severidad esperada de cada id: cambiar una severidad es un cambio de contrato.
EXPECTED = {
    "TLS-EXPIRED": "high",
    "TLS-CERT-INVALID": "high",
    "HTTPS-MISSING": "high",
    "FORM-PASSWORD-HTTP": "high",
    "FORM-INSECURE-ACTION": "high",
    "SPF-PERMISSIVE": "high",
    "TLS-EXPIRING": "medium",
    "TLS-OLD-PROTOCOL": "medium",
    "HTTP-NO-REDIRECT": "medium",
    "HDR-HSTS-MISSING": "medium",
    "HDR-CSP-MISSING": "medium",
    "CONTENT-MIXED": "medium",
    "COOKIE-NO-SECURE": "medium",
    "DMARC-MISSING": "medium",
    "HDR-HSTS-WEAK": "low",
    "HDR-CSP-UNSAFE": "low",
    "HDR-XFO-MISSING": "low",
    "HDR-XCTO-MISSING": "low",
    "LEAK-SERVER-VERSION": "low",
    "LEAK-POWERED-BY": "low",
    "LEAK-ASPNET-VERSION": "low",
    "COOKIE-NO-HTTPONLY": "low",
    "COOKIE-NO-SAMESITE": "low",
    "SPF-MISSING": "low",
    "SPF-NEUTRAL": "low",
    "SPF-MULTIPLE": "low",
    "DMARC-NONE": "low",
    "SECTXT-EXPIRED": "low",
    "HDR-REFERRER-MISSING": "info",
    "HDR-PERMISSIONS-MISSING": "info",
    "LEAK-GENERATOR": "info",
    "LEAK-HTML-COMMENT": "info",
    "DKIM-NOT-FOUND": "info",
    "SECTXT-MISSING": "info",
    "ROBOTS-SENSITIVE": "info",
    "CONTENT-NO-SRI": "info",
    "FORM-EXTERNAL-ACTION": "info",
    "FORM-PASSWORD-AUTOCOMPLETE": "info",
    "LINK-NO-NOOPENER": "info",
    "SURFACE-ENDPOINTS": "info",
    "TECH-VERSIONS": "info",
    "DNS-NO-CAA": "info",
}


def ids(findings: tuple) -> list[str]:
    return [f.id for f in findings]


def test_catalog_ids_and_severities_are_stable() -> None:
    assert {rule.id: rule.severity for rule in RULES} == EXPECTED
    assert len({rule.id for rule in RULES}) == len(RULES)
    for rule in RULES:
        assert re.fullmatch(r"[A-Z]+(?:-[A-Z]+)+", rule.id), rule.id


@pytest.mark.parametrize("lang", SUPPORTED_LANGS)
def test_every_rule_has_title_and_recommendation(lang: str) -> None:
    for rule in RULES:
        assert f"finding.{rule.id}.title" in MESSAGES[lang]
        assert f"finding.{rule.id}.rec" in MESSAGES[lang]


def test_wording_is_prudent() -> None:
    for lang in SUPPORTED_LANGS:
        for key, text in MESSAGES[lang].items():
            if key.startswith("finding."):
                assert not re.search(r"\bvulnerable\b|\bes vulnerable\b", text, re.I), key


def bad_context() -> FindingContext:
    security = build_security(
        page_url="https://shop.example/",
        headers={
            "Server": "Apache/2.4.41",
            "X-Powered-By": "PHP/8.1.2",
            "Strict-Transport-Security": "max-age=60",
        },
        html=(
            '<script src="https://cdn.example.net/x.js"></script>'
            '<img src="http://shop.example/a.png">'
            '<form action="http://shop.example/login"><input type="password"></form>'
        ),
        set_cookies=("sid=1; path=/",),
        dns=DnsRecords(
            a=("203.0.113.10",),
            mx=("10 mx.example",),
            txt=("v=spf1 +all",),
            dmarc=("v=DMARC1; p=none",),
        ),
        security_txt=None,
        security_txt_checked=True,
        http_redirect=HttpRedirect(False, 200, "http://shop.example/"),
    )
    tls = TlsResult(issuer="R11", days_left=10, protocol="TLSv1.1", verified=True)
    infra = InfraResult(dns=DnsRecords(a=("203.0.113.10",)))
    techs = (Technology("jQuery", "library", "1.12.4"),)
    return FindingContext("https://shop.example/", security, tls, infra, techs)


def test_bad_site_triggers_expected_rules() -> None:
    found = ids(evaluate(bad_context()))
    for expected in (
        "FORM-INSECURE-ACTION",
        "SPF-PERMISSIVE",
        "TLS-EXPIRING",
        "TLS-OLD-PROTOCOL",
        "HTTP-NO-REDIRECT",
        "HDR-HSTS-WEAK",
        "HDR-CSP-MISSING",
        "CONTENT-MIXED",
        "COOKIE-NO-SECURE",
        "COOKIE-NO-HTTPONLY",
        "COOKIE-NO-SAMESITE",
        "LEAK-SERVER-VERSION",
        "LEAK-POWERED-BY",
        "DMARC-NONE",
        "DKIM-NOT-FOUND",
        "SECTXT-MISSING",
        "CONTENT-NO-SRI",
        "TECH-VERSIONS",
        "DNS-NO-CAA",
    ):
        assert expected in found, expected
    assert "HDR-HSTS-MISSING" not in found
    assert "DMARC-MISSING" not in found


def test_findings_are_sorted_by_severity() -> None:
    findings = evaluate(bad_context())
    positions = [SEVERITY_ORDER.index(f.severity) for f in findings]
    assert positions == sorted(positions)


def test_tls_rules() -> None:
    expired = TlsResult(
        not_after="2026-01-01", days_left=-5, verified=False, verify_error="expired"
    )
    invalid = TlsResult(days_left=90, verified=False, verify_error="self-signed certificate")
    assert ids(evaluate(FindingContext("https://x.example/", tls=expired))) == ["TLS-EXPIRED"]
    assert ids(evaluate(FindingContext("https://x.example/", tls=invalid))) == ["TLS-CERT-INVALID"]


def test_http_site_and_password_form() -> None:
    security = build_security(
        page_url="http://x.example/", headers={}, html='<form><input type="password"></form>'
    )
    found = ids(evaluate(FindingContext("http://x.example/", security)))
    assert found[:2] == ["HTTPS-MISSING", "FORM-PASSWORD-HTTP"]
    assert "HDR-HSTS-MISSING" not in found


def test_unanswered_dns_does_not_create_false_findings() -> None:
    security = build_security(
        page_url="https://x.example/",
        headers={},
        html="",
        dns=DnsRecords(mx=("10 mx.example",), unanswered=("txt", "dmarc", "dkim")),
    )
    found = ids(evaluate(FindingContext("https://x.example/", security)))
    assert not {"SPF-MISSING", "DMARC-MISSING", "DKIM-NOT-FOUND"} & set(found)


def test_broken_rule_does_not_break_the_report() -> None:
    def boom(ctx: FindingContext) -> None:
        raise ValueError("bug")

    rules = (Rule("X-BROKEN", "high", boom), *RULES[:1])
    assert evaluate(FindingContext("https://x.example/"), rules) == ()

"""Integración del orquestador sin red real: requests, DNS y TLS simulados."""

from collections.abc import Callable

import pytest
import responses

from webscope import core
from webscope.core import AnalyzeOptions, analyze

BASE = "https://zapasrun.example"


def run(url: str = "zapasrun.example", **options: object):
    return analyze(url, options=AnalyzeOptions(**options))  # type: ignore[arg-type]


@pytest.mark.usefixtures("full_site")
def test_full_analysis_has_every_block() -> None:
    result = run()
    assert result.unavailable == {}
    assert result.infra is not None and result.infra.ipv4 == ("104.16.1.1",)
    assert [m.name for m in result.infra.cdn] == ["Cloudflare"]
    assert result.tls is not None and result.tls.issuer == "Let's Encrypt (R11)"
    assert result.security is not None
    assert result.security.files.security_txt is not None
    assert result.security.http_redirect is not None
    assert result.security.http_redirect.redirects_to_https
    assert result.security.email is not None and result.security.email.dmarc_policy == "none"
    assert "shop.zapasrun.example" in result.security.surface.subdomains
    ids = [f.id for f in result.findings]
    assert "DMARC-NONE" in ids and "HDR-CSP-MISSING" in ids
    assert "SECTXT-MISSING" not in ids and "HTTP-NO-REDIRECT" not in ids
    assert result.scanned_at.endswith("Z")
    assert result.topic is not None and result.topic.pages_analyzed == 2


@pytest.mark.usefixtures("full_site")
def test_dns_down_still_produces_report(fake_dns) -> None:
    fake_dns.down = True
    result = run()
    assert result.unavailable == {"dns": "dns_timeout"}
    assert result.security is not None and result.security.email is None
    assert result.tls is not None
    ids = [f.id for f in result.findings]
    assert "HDR-CSP-MISSING" in ids
    assert not {"SPF-MISSING", "DMARC-MISSING", "DNS-NO-CAA"} & set(ids)


@pytest.mark.usefixtures("wordpress_site")
def test_tls_failure_is_isolated() -> None:
    result = run()
    assert result.unavailable["tls"] == "tls_connection"
    assert result.tls is None
    assert result.security is not None and result.pages is not None


@pytest.mark.usefixtures("wordpress_site")
def test_crawl_failure_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("crawler roto")

    monkeypatch.setattr(core, "discover", boom)
    result = run()
    assert result.unavailable["pages"] == "error"
    assert result.pages is None
    assert result.summary


@pytest.mark.usefixtures("full_site")
def test_brief_skips_dns_tls_and_probes(fake_dns) -> None:
    result = run(brief=True)
    assert result.brief
    assert result.infra is None and result.tls is None and result.security is None
    assert result.findings == ()
    assert fake_dns.queries == []


def test_no_crawl_does_not_read_sitemaps(full_site: responses.RequestsMock) -> None:
    result = run(crawl=False)
    assert result.pages is None
    assert result.unavailable["pages"] == "no_crawl"
    requested = [call.request.url for call in full_site.calls]
    assert not any("sitemap" in url for url in requested)
    assert f"{BASE}/robots.txt" in requested


def test_rdap_is_opt_in(full_site: responses.RequestsMock) -> None:
    full_site.get(
        "https://rdap.org/domain/zapasrun.example",
        json={
            "events": [{"eventAction": "registration", "eventDate": "2015-01-01T00:00:00Z"}],
            "entities": [{"roles": ["registrar"], "handle": "REG-1"}],
        },
    )
    without = run()
    assert without.infra is not None and without.infra.rdap is None
    assert not any("rdap.org" in call.request.url for call in full_site.calls)
    with_rdap = run(rdap=True)
    assert with_rdap.infra is not None and with_rdap.infra.rdap is not None
    assert with_rdap.infra.rdap.registrar == "REG-1"


@pytest.mark.usefixtures("full_site")
def test_rdap_failure_is_reported() -> None:
    result = run(rdap=True)
    assert result.unavailable["rdap"] == "rdap_failed"


def test_localhost_skips_dns_and_tls(
    mocked: responses.RequestsMock, load_fixture: Callable[[str], str]
) -> None:
    mocked.get(
        "http://localhost:8000/",
        body=load_fixture("static.html"),
        headers={"Content-Type": "text/html"},
    )
    result = analyze("http://localhost:8000/", options=AnalyzeOptions(crawl=False))
    assert result.unavailable["dns"] == "local_host"
    assert result.unavailable["tls"] == "http_only"
    assert "HTTPS-MISSING" in [f.id for f in result.findings]


def test_redirect_chain_is_recorded(
    mocked: responses.RequestsMock, load_fixture: Callable[[str], str]
) -> None:
    mocked.get("https://www.zapasrun.example/", status=301, headers={"Location": f"{BASE}/"})
    mocked.get(
        f"{BASE}/", body=load_fixture("wordpress.html"), headers={"Content-Type": "text/html"}
    )
    result = analyze("www.zapasrun.example", options=AnalyzeOptions(brief=True, crawl=False))
    assert [(r.url, r.status) for r in result.redirects] == [("https://www.zapasrun.example/", 301)]
    assert result.final_url == f"{BASE}/"

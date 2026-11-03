from types import SimpleNamespace

import dns.exception
import dns.resolver
import pytest

from webscope import dnsinfo
from webscope.dnsinfo import (
    cymru_origin_name,
    has_dkim_key,
    is_local_host,
    is_null_mx,
    parse_cymru_asname,
    parse_cymru_origin,
    record_to_text,
    registrable_domain,
)

# La función real: el fixture ``fake_dns`` reemplaza ``make_query`` en cada test.
REAL_MAKE_QUERY = dnsinfo.make_query


def test_parse_cymru() -> None:
    origin = parse_cymru_origin("13335 | 104.16.0.0/13 | US | arin | 2014-03-28")
    assert origin is not None
    assert (origin.asn, origin.prefix, origin.country, origin.registry) == (
        13335,
        "104.16.0.0/13",
        "US",
        "arin",
    )
    assert parse_cymru_origin("garbage") is None
    asname = "13335 | US | arin | 2010-07-14 | CLOUDFLARENET - Cloudflare, Inc., US"
    assert parse_cymru_asname(asname) == "Cloudflare, Inc."


def test_cymru_names() -> None:
    assert cymru_origin_name("203.0.113.10") == "10.113.0.203.origin.asn.cymru.com"
    assert cymru_origin_name("2001:db8::1").endswith(".origin6.asn.cymru.com")


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("www.shop.ejemplo.com.ar", "ejemplo.com.ar"),
        ("blog.example.co.uk", "example.co.uk"),
        ("www.example.com", "example.com"),
        ("example.com", "example.com"),
        ("alvaro.github.io", "github.io"),
    ],
)
def test_registrable_domain(host: str, expected: str) -> None:
    assert registrable_domain(host) == expected


@pytest.mark.parametrize(
    ("host", "local"),
    [
        ("localhost", True),
        ("127.0.0.1", True),
        ("192.168.0.10", True),
        ("app.localhost", True),
        ("8.8.8.8", False),
        ("example.com", False),
    ],
)
def test_is_local_host(host: str, local: bool) -> None:
    assert is_local_host(host) is local


def test_dkim_and_null_mx_helpers() -> None:
    assert has_dkim_key("v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA")
    assert not has_dkim_key("v=DKIM1; p=")
    assert is_null_mx("0 .") and not is_null_mx("10 mx.example.com")


def test_record_to_text() -> None:
    txt = SimpleNamespace(strings=(b"v=spf1 ", b"-all"))
    mx = SimpleNamespace(preference=10, exchange="mx.example.com.")
    null_mx = SimpleNamespace(preference=0, exchange=".")
    assert record_to_text(txt, "TXT") == "v=spf1 -all"
    assert record_to_text(mx, "MX") == "10 mx.example.com"
    assert record_to_text(null_mx, "MX") == "0 ."
    assert record_to_text("ns1.example.com.", "NS") == "ns1.example.com"


def test_collect_with_fake_resolver(fake_dns) -> None:
    fake_dns.add("www.ejemplo.com", "A", "104.16.1.1")
    fake_dns.add("www.ejemplo.com", "AAAA", "2001:db8::1")
    fake_dns.add("www.ejemplo.com", "CNAME", "ejemplo.cdn.cloudflare.net")
    fake_dns.add("ejemplo.com", "NS", "ns1.cloudflare.com", "ns2.cloudflare.com")
    fake_dns.add("ejemplo.com", "MX", "10 alt1.aspmx.l.google.com", "1 aspmx.l.google.com")
    fake_dns.add("ejemplo.com", "TXT", "v=spf1 include:_spf.google.com ~all")
    fake_dns.add("_dmarc.ejemplo.com", "TXT", "v=DMARC1; p=none")
    fake_dns.add("google._domainkey.ejemplo.com", "TXT", "v=DKIM1; p=MIIBIjANBgkqhkiG9w0BAQEF")
    fake_dns.add("1.1.16.104.in-addr.arpa", "PTR", "server10.hosting.example")
    fake_dns.add("1.1.16.104.origin.asn.cymru.com", "TXT", "13335 | 104.16.0.0/13 | US | arin | x")
    fake_dns.add(
        "AS13335.asn.cymru.com",
        "TXT",
        "13335 | US | arin | x | CLOUDFLARENET - Cloudflare, Inc., US",
    )
    records = dnsinfo.collect("www.ejemplo.com", fake_dns.query)
    assert records.a == ("104.16.1.1",) and records.aaaa == ("2001:db8::1",)
    assert records.cname == {"www.ejemplo.com": "ejemplo.cdn.cloudflare.net"}
    assert records.mx[0] == "1 aspmx.l.google.com"
    assert records.dmarc == ("v=DMARC1; p=none",)
    assert records.dkim == ("google",)
    assert records.ptr == {"104.16.1.1": "server10.hosting.example"}
    assert records.asn["104.16.1.1"].org == "Cloudflare, Inc."
    assert records.error is None and records.unanswered == ()


def test_collect_marks_failed_queries(fake_dns, monkeypatch: pytest.MonkeyPatch) -> None:
    original = fake_dns.query

    def flaky(name: str, rtype: str) -> list[str]:
        if rtype == "TXT":
            raise dnsinfo.DnsError("timeout")
        return original(name, rtype)

    fake_dns.add("ejemplo.com", "A", "203.0.113.10")
    records = dnsinfo.collect("ejemplo.com", flaky)
    assert {"txt", "dmarc", "dkim"} <= set(records.unanswered)
    assert records.error is None
    assert records.a == ("203.0.113.10",)


def test_collect_when_dns_is_down(fake_dns) -> None:
    fake_dns.down = True
    records = dnsinfo.collect("ejemplo.com", fake_dns.query)
    assert records.error == "timeout"
    assert records.a == ()


def test_collect_for_ip_target_skips_forward_lookups(fake_dns) -> None:
    dnsinfo.collect("8.8.8.8", fake_dns.query, is_target_ip=True)
    rtypes = {rtype for _, rtype in fake_dns.queries}
    assert rtypes <= {"PTR", "TXT"}
    assert ("8.8.8.8.in-addr.arpa", "PTR") in fake_dns.queries


# --- make_query con dnspython simulado ----------------------------------------------


class FakeResolver:
    def __init__(self, behavior: dict[str, object]) -> None:
        self.behavior = behavior
        self.lifetime = self.timeout = 0.0

    def resolve(self, name: str, rtype: str, raise_on_no_answer: bool = True) -> object:
        result = self.behavior[name]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (dns.exception.Timeout(), "timeout"),
        (dns.resolver.NoNameservers(), "no_nameservers"),
        (dns.exception.DNSException(), "error"),
    ],
)
def test_make_query_translates_errors(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    behavior = {"bad.example": error, "missing.example": dns.resolver.NXDOMAIN()}
    monkeypatch.setattr(dns.resolver, "Resolver", lambda: FakeResolver(behavior))
    query = REAL_MAKE_QUERY(2.0)
    assert query("missing.example", "A") == []
    with pytest.raises(dnsinfo.DnsError) as info:
        query("bad.example", "A")
    assert info.value.code == code


def test_make_query_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = [SimpleNamespace(strings=(b"v=spf1 -all",))]
    monkeypatch.setattr(dns.resolver, "Resolver", lambda: FakeResolver({"x.example": answer}))
    assert REAL_MAKE_QUERY(1.0)("x.example", "TXT") == ["v=spf1 -all"]

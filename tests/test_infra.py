from datetime import datetime, timezone

import pytest

from webscope.analyzers.infra import CDN_RULES, build_infra, detect_cdn, parse_rdap
from webscope.models import AsnInfo, DnsRecords


def names(**kwargs: object) -> list[str]:
    return [match.name for match in detect_cdn(**kwargs)]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"cf-ray": "8a1b-EZE", "server": "cloudflare"}, "Cloudflare"),
        ({"x-sucuri-id": "123"}, "Sucuri"),
        ({"x-akamai-transformed": "9 - 0 pmb=mRUM,1"}, "Akamai"),
        ({"x-amz-cf-id": "abc", "via": "1.1 x.cloudfront.net (CloudFront)"}, "Amazon CloudFront"),
        ({"x-served-by": "cache-eze2230028-EZE"}, "Fastly"),
        ({"x-vercel-id": "gru1::abc"}, "Vercel"),
        ({"x-nf-request-id": "01H"}, "Netlify"),
        ({"x-iinfo": "1-2-3"}, "Imperva"),
    ],
)
def test_cdn_from_headers(headers: dict[str, str], expected: str) -> None:
    assert expected in names(headers=headers)


@pytest.mark.parametrize(
    ("cname", "expected"),
    [
        ("d111111abcdef8.cloudfront.net", "Amazon CloudFront"),
        ("ejemplo.azureedge.net", "Azure Front Door / CDN"),
        ("ejemplo.global.fastly.net", "Fastly"),
        ("cname.vercel-dns.com", "Vercel"),
        ("ejemplo.netlify.app", "Netlify"),
        ("usuario.github.io", "GitHub Pages"),
    ],
)
def test_cdn_from_cnames(cname: str, expected: str) -> None:
    assert names(headers={}, cnames=[cname]) == [expected]


def test_cdn_from_asn_and_generic_cloud_is_suppressed() -> None:
    assert names(headers={}, asn_orgs=["Cloudflare, Inc."]) == ["Cloudflare"]
    assert names(headers={}, asn_orgs=["Amazon.com, Inc."]) == ["Amazon Web Services"]
    # Si ya hay un CDN, el ASN genérico de la nube no se repite.
    assert names(headers={"x-amz-cf-id": "x"}, asn_orgs=["Amazon.com, Inc."]) == [
        "Amazon CloudFront"
    ]


def test_nothing_detected() -> None:
    assert detect_cdn({"server": "nginx"}) == ()


def test_rules_have_unique_names() -> None:
    assert len({rule.name for rule in CDN_RULES}) == len(CDN_RULES)


def test_build_infra_combines_dns_and_headers() -> None:
    dns = DnsRecords(
        a=("104.16.1.1",),
        cname={"www.ejemplo.com": "ejemplo.cdn.cloudflare.net"},
        ptr={"104.16.1.1": "x.example"},
        asn={"104.16.1.1": AsnInfo(13335, "Cloudflare, Inc.", "US")},
    )
    infra = build_infra(dns, {"cf-ray": "abc"}, connected_ip="104.16.1.1")
    assert infra.ipv4 == ("104.16.1.1",)
    assert [m.name for m in infra.cdn] == ["Cloudflare"]
    assert infra.connected_ip == "104.16.1.1"


def test_build_infra_without_dns() -> None:
    infra = build_infra(None, {"x-vercel-id": "x"})
    assert infra.ipv4 == () and [m.name for m in infra.cdn] == ["Vercel"]


def test_parse_rdap() -> None:
    data = {
        "events": [
            {"eventAction": "registration", "eventDate": "2010-05-04T12:00:00Z"},
            {"eventAction": "expiration", "eventDate": "2027-05-04T12:00:00Z"},
        ],
        "entities": [
            {"roles": ["registrant"], "handle": "X"},
            {
                "roles": ["registrar"],
                "vcardArray": [
                    "vcard",
                    [["version", {}, "text", "4.0"], ["fn", {}, "text", "NIC Ejemplo"]],
                ],
            },
        ],
    }
    info = parse_rdap("ejemplo.com", data, now=datetime(2026, 5, 4, 12, tzinfo=timezone.utc))
    assert info.registrar == "NIC Ejemplo"
    assert (info.created, info.expires) == ("2010-05-04", "2027-05-04")
    assert info.age_days is not None and info.age_days // 365 == 16


def test_parse_rdap_with_missing_data() -> None:
    info = parse_rdap("x.example", {"events": "nope"})
    assert info.registrar == "" and info.created is None and info.age_days is None

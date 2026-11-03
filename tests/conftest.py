"""Fixtures compartidas: config aislada en ``tmp_path`` y HTML de ejemplo."""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import responses

from webscope import core, dnsinfo, tlsprobe

FIXTURES = Path(__file__).parent / "fixtures"
HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Nunca tocar el home real: config en ``tmp_path`` y entorno predecible."""
    config_dir = tmp_path / "config"
    monkeypatch.setenv("WEBSCOPE_CONFIG_DIR", str(config_dir))
    for name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "NO_COLOR", "FORCE_COLOR", "PY_COLORS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    return config_dir


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falla si algún test intenta abrir una conexión real (TCP o UDP)."""

    def guard(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Los tests no deben hacer requests reales")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "sendto", guard)
    monkeypatch.setattr(socket, "create_connection", guard)


class FakeDns:
    """Resolver falso: ``records[(nombre, tipo)] = [valores]``; ``down`` simula DNS caído."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str], list[str]] = {}
        self.down = False
        self.queries: list[tuple[str, str]] = []

    def add(self, name: str, rtype: str, *values: str) -> None:
        self.records[(name, rtype)] = list(values)

    def query(self, name: str, rtype: str) -> list[str]:
        self.queries.append((name, rtype))
        if self.down:
            raise dnsinfo.DnsError("timeout")
        return list(self.records.get((name, rtype), []))


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> FakeDns:
    """Reemplaza ``dnspython``: por defecto todas las consultas devuelven vacío."""
    fake = FakeDns()
    monkeypatch.setattr(dnsinfo, "make_query", lambda timeout=0: fake.query)
    return fake


@pytest.fixture(autouse=True)
def fake_tls(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Reemplaza ``tlsprobe.probe``: sin configurar, falla como si no hubiera conexión."""
    state: dict[str, object] = {"probe": None}

    def probe(host: str, port: int = 443, timeout: float = 10.0) -> tlsprobe.TlsProbe:
        result = state["probe"]
        if result is None:
            raise tlsprobe.TlsError("connection", "mocked")
        return result  # type: ignore[return-value]

    monkeypatch.setattr(tlsprobe, "probe", probe)
    return state


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pausas de cortesía entre requests no hacen falta en los tests."""
    monkeypatch.setattr(core.time, "sleep", lambda seconds: None)


@pytest.fixture
def load_fixture() -> Callable[[str], str]:
    """Devuelve una función que lee ``tests/fixtures/<name>``."""

    def _load(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _load


@pytest.fixture
def mocked() -> Iterator[responses.RequestsMock]:
    """Intercepta ``requests``: cualquier request no registrado falla."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def wordpress_site(
    mocked: responses.RequestsMock, load_fixture: Callable[[str], str]
) -> responses.RequestsMock:
    """Sitio WordPress simulado con robots.txt y un sitemap de 3 URLs."""
    base = "https://zapasrun.example"
    mocked.get(
        f"{base}/",
        body=load_fixture("wordpress.html"),
        headers={**HTML_HEADERS, "Server": "nginx"},
    )
    mocked.get(f"{base}/robots.txt", body=f"User-agent: *\nSitemap: {base}/sitemap.xml\n")
    urls = "".join(f"<url><loc>{base}/{path}</loc></url>" for path in ("", "tienda/", "blog/"))
    mocked.get(
        f"{base}/sitemap.xml",
        body=f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
    )
    return mocked


ZAPAS = "https://zapasrun.example"
CERT = {
    "subject": ((("commonName", "zapasrun.example"),),),
    "issuer": ((("organizationName", "Let's Encrypt"),), (("commonName", "R11"),)),
    "notBefore": "Jan  1 00:00:00 2026 GMT",
    "notAfter": "Dec 31 23:59:59 2099 GMT",
    "subjectAltName": (("DNS", "zapasrun.example"), ("DNS", "shop.zapasrun.example")),
}


@pytest.fixture
def full_site(
    wordpress_site: responses.RequestsMock, fake_dns: FakeDns, fake_tls: dict[str, object]
) -> responses.RequestsMock:
    """Sitio WordPress con DNS, TLS, security.txt, redirección HTTP y una página interna."""
    wordpress_site.get(
        f"{ZAPAS}/.well-known/security.txt",
        body="Contact: mailto:sec@zapasrun.example\nExpires: 2099-01-01T00:00:00Z\n",
    )
    wordpress_site.get("http://zapasrun.example/", status=301, headers={"Location": f"{ZAPAS}/"})
    wordpress_site.get(
        f"{ZAPAS}/nosotros",
        body=(
            "<main><p>Somos una tienda familiar de zapatillas de running "
            "fundada en Rosario en 2015.</p></main>"
        ),
        headers={"Content-Type": "text/html"},
    )
    fake_dns.add("zapasrun.example", "A", "104.16.1.1")
    fake_dns.add("zapasrun.example", "NS", "ns1.cloudflare.com", "ns2.cloudflare.com")
    fake_dns.add("zapasrun.example", "MX", "1 aspmx.l.google.com")
    fake_dns.add("zapasrun.example", "TXT", "v=spf1 include:_spf.google.com ~all")
    fake_dns.add("_dmarc.zapasrun.example", "TXT", "v=DMARC1; p=none")
    fake_dns.add("1.1.16.104.origin.asn.cymru.com", "TXT", "13335 | 104.16.0.0/13 | US | arin | x")
    fake_dns.add(
        "AS13335.asn.cymru.com",
        "TXT",
        "13335 | US | arin | x | CLOUDFLARENET - Cloudflare, Inc., US",
    )
    fake_tls["probe"] = tlsprobe.TlsProbe(
        cert=CERT, protocol="TLSv1.3", cipher="TLS_AES_256_GCM_SHA384"
    )
    return wordpress_site

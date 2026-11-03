"""Fixtures compartidas: config aislada en ``tmp_path`` y HTML de ejemplo."""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import responses

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
    """Falla si algún test intenta abrir una conexión real."""

    def guard(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Los tests no deben hacer requests reales")

    monkeypatch.setattr(socket.socket, "connect", guard)


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

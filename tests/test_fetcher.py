import socket

import pytest
import requests
import responses

from webscope.fetcher import USER_AGENT, FetchError, decode_html, fetch_page, normalize_url

URL = "https://site.example/"


def error_code(mocked: responses.RequestsMock, **kwargs: object) -> str:
    mocked.get(URL, **kwargs)
    with pytest.raises(FetchError) as info:
        fetch_page(URL)
    return info.value.code


def test_fetch_ok_sends_user_agent(mocked: responses.RequestsMock) -> None:
    mocked.get(
        URL, body="<html>hola</html>", headers={"Content-Type": "text/html", "Server": "nginx"}
    )
    page = fetch_page(URL)
    assert page.html == "<html>hola</html>"
    assert page.status_code == 200
    assert page.headers["server"] == "nginx"
    assert mocked.calls[0].request.headers["User-Agent"] == USER_AGENT


def test_follows_redirects(mocked: responses.RequestsMock) -> None:
    mocked.get(URL, status=301, headers={"Location": "https://www.site.example/"})
    mocked.get("https://www.site.example/", body="<html></html>", content_type="text/html")
    assert fetch_page(URL).final_url == "https://www.site.example/"


def test_http_error_status(mocked: responses.RequestsMock) -> None:
    mocked.get(URL, status=404)
    with pytest.raises(FetchError) as info:
        fetch_page(URL)
    assert info.value.code == "http"
    assert info.value.params["status"] == 404


def test_not_html(mocked: responses.RequestsMock) -> None:
    assert error_code(mocked, json={"a": 1}) == "not_html"


def test_timeout(mocked: responses.RequestsMock) -> None:
    assert error_code(mocked, body=requests.exceptions.ReadTimeout("slow")) == "timeout"


def test_ssl_error(mocked: responses.RequestsMock) -> None:
    assert error_code(mocked, body=requests.exceptions.SSLError("bad cert")) == "ssl"


def test_dns_error(mocked: responses.RequestsMock) -> None:
    dns = requests.exceptions.ConnectionError(socket.gaierror(11001, "getaddrinfo failed"))
    assert error_code(mocked, body=dns) == "dns"


def test_generic_connection_error(mocked: responses.RequestsMock) -> None:
    refused = requests.exceptions.ConnectionError(ConnectionRefusedError("refused"))
    assert error_code(mocked, body=refused) == "connection"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com"),
        ("  example.com/path ", "https://example.com/path"),
        ("http://example.com", "http://example.com"),
        ("https://example.com/a?b=1", "https://example.com/a?b=1"),
    ],
)
def test_normalize_url(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "ftp://example.com", "http://", "exa mple.com"])
def test_normalize_url_rejects_invalid(raw: str) -> None:
    with pytest.raises(FetchError) as info:
        normalize_url(raw)
    assert info.value.code == "invalid_url"


def test_decode_html_uses_header_meta_or_utf8() -> None:
    latin = "<p>envío</p>".encode("latin-1")
    assert decode_html(latin, "text/html; charset=ISO-8859-1") == "<p>envío</p>"
    meta = b'<meta charset="iso-8859-1"><p>' + "año".encode("latin-1") + b"</p>"
    assert "año" in decode_html(meta, "text/html")
    assert decode_html("ñ".encode(), "text/html") == "ñ"
    assert decode_html(b"abc", "text/html; charset=nope") == "abc"

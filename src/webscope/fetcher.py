"""Descarga de páginas con ``requests``: timeouts, user-agent propio y errores claros.

Es (junto a ``crawler``) el único módulo que hace red. Los errores se convierten en
``FetchError`` con un ``code`` estable que ``report``/``cli`` traducen al idioma de
la interfaz; nunca se muestra un stack trace al usuario.
"""

from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from webscope import __version__

DEFAULT_TIMEOUT = 10.0
MAX_BYTES = 5 * 1024 * 1024
USER_AGENT = f"webscope/{__version__} (+https://github.com/AlvaroAramayoChain/webscope)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es,en;q=0.8",
}
_HTML_TYPES = ("text/html", "application/xhtml+xml")
_META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([\w-]+)""", re.IGNORECASE)


class FetchError(Exception):
    """Error de red o de contenido con un código traducible y sus parámetros."""

    def __init__(self, code: str, **params: object) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


@dataclass(frozen=True)
class FetchedPage:
    """Una página descargada: HTML decodificado y headers en minúsculas."""

    url: str
    final_url: str
    status_code: int
    html: str
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_ms: int = 0


def create_session() -> requests.Session:
    """Sesión HTTP con los headers por defecto de webscope."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def normalize_url(raw: str) -> str:
    """Agrega ``https://`` si falta y valida que la URL tenga esquema y host."""
    value = raw.strip()
    if not value:
        raise FetchError("invalid_url", url=raw)
    if "://" not in value:
        value = "https://" + value.lstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or " " in value:
        raise FetchError("invalid_url", url=raw)
    return value


def _is_dns_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen = 0
    while current is not None and seen < 10:
        if isinstance(current, socket.gaierror):
            return True
        text = repr(current)
        if "NameResolutionError" in text or "getaddrinfo failed" in text:
            return True
        if "Name or service not known" in text or "nodename nor servname" in text:
            return True
        current = current.__cause__ or current.__context__ or _first_arg_exception(current)
        seen += 1
    return False


def _first_arg_exception(exc: BaseException) -> BaseException | None:
    for arg in getattr(exc, "args", ()):
        if isinstance(arg, BaseException):
            return arg
        reason = getattr(arg, "reason", None)
        if isinstance(reason, BaseException):
            return reason
    return None


def _translate_request_error(
    exc: requests.RequestException, url: str, timeout: float = DEFAULT_TIMEOUT
) -> FetchError:
    host = urlparse(url).hostname or url
    if isinstance(exc, requests.exceptions.SSLError):
        return FetchError("ssl", host=host)
    if isinstance(exc, requests.exceptions.Timeout):
        return FetchError("timeout", host=host, timeout=int(timeout))
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        return FetchError("too_many_redirects", url=url)
    if isinstance(exc, requests.exceptions.InvalidURL | requests.exceptions.MissingSchema):
        return FetchError("invalid_url", url=url)
    if isinstance(exc, requests.exceptions.ConnectionError) and _is_dns_error(exc):
        return FetchError("dns", host=host)
    return FetchError("connection", host=host)


def _read_limited(response: requests.Response, limit: int = MAX_BYTES) -> bytes:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_content(chunk_size=65536):
        chunks.append(chunk)
        size += len(chunk)
        if size >= limit:
            break
    return b"".join(chunks)[:limit]


def decode_html(body: bytes, content_type: str) -> str:
    """Decodifica usando el charset del header, del ``<meta>`` o UTF-8 por defecto."""
    match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    encoding = match.group(1) if match else None
    if not encoding:
        meta = _META_CHARSET.search(body[:4096])
        encoding = meta.group(1).decode("ascii", "ignore") if meta else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _get(session: requests.Session, url: str, timeout: float) -> requests.Response:
    try:
        return session.get(url, timeout=timeout, allow_redirects=True, stream=True)
    except requests.RequestException as exc:
        raise _translate_request_error(exc, url, timeout) from exc


def fetch_page(
    url: str, session: requests.Session | None = None, timeout: float = DEFAULT_TIMEOUT
) -> FetchedPage:
    """Descarga ``url`` y devuelve el HTML; lanza ``FetchError`` si algo falla."""
    session = session or create_session()
    started = time.perf_counter()
    response = _get(session, url, timeout)
    with response:
        if response.status_code >= 400:
            raise FetchError(
                "http", status=response.status_code, reason=response.reason or "", url=url
            )
        content_type = response.headers.get("Content-Type", "")
        if content_type and not content_type.lower().startswith(_HTML_TYPES):
            raise FetchError("not_html", content_type=content_type.split(";")[0], url=url)
        try:
            body = _read_limited(response)
        except requests.RequestException as exc:
            raise _translate_request_error(exc, url, timeout) from exc
    return FetchedPage(
        url=url,
        final_url=response.url or url,
        status_code=response.status_code,
        html=decode_html(body, content_type),
        headers={k.lower(): v for k, v in response.headers.items()},
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


def fetch_bytes(
    url: str, session: requests.Session, timeout: float = DEFAULT_TIMEOUT
) -> bytes | None:
    """Descarga un recurso auxiliar (robots.txt, sitemap); ``None`` si falla o no es 2xx."""
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
    except requests.RequestException:
        return None
    with response:
        if not 200 <= response.status_code < 300:
            return None
        try:
            return _read_limited(response, limit=MAX_BYTES * 4)
        except requests.RequestException:
            return None

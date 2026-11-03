"""Conexión TLS estándar con ``ssl``/``socket`` de la stdlib.

Es el único módulo que abre sockets TLS. Hace un único handshake normal (no prueba
ciphers ni protocolos débiles) y devuelve el certificado y lo negociado. Valida
contra el almacén del sistema más el bundle de ``certifi`` (el mismo que usa
``requests``), porque en Windows Python no completa cadenas intermedias. Si la
verificación falla, repite el handshake sin verificar solo para leer el certificado
y reportar el problema como hallazgo (no se envían datos por esa conexión).
"""

from __future__ import annotations

import contextlib
import os
import socket
import ssl
import tempfile
from dataclasses import dataclass, field
from typing import Any

import certifi

DEFAULT_PORT = 443


class TlsError(Exception):
    """Fallo de conexión TLS con un código estable."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class TlsProbe:
    """Datos crudos del handshake."""

    cert: dict[str, Any] = field(default_factory=dict)
    protocol: str | None = None
    cipher: str | None = None
    verified: bool = True
    verify_error: str | None = None
    peer_ip: str | None = None


def _handshake(host: str, port: int, timeout: float, context: ssl.SSLContext) -> TlsProbe:
    with (
        socket.create_connection((host, port), timeout=timeout) as raw,
        context.wrap_socket(raw, server_hostname=host) as tls,
    ):
        cert = tls.getpeercert() or {}
        if not cert:
            cert = decode_der(tls.getpeercert(binary_form=True))
        cipher = tls.cipher()
        peer = tls.getpeername()
        return TlsProbe(
            cert=cert,
            protocol=tls.version(),
            cipher=cipher[0] if cipher else None,
            peer_ip=str(peer[0]) if peer else None,
        )


def decode_der(der: bytes | None) -> dict[str, Any]:
    """Decodifica un certificado DER con el parser interno de ``ssl`` (vacío si no se puede)."""
    decoder = getattr(getattr(ssl, "_ssl", None), "_test_decode_cert", None)
    if not der or decoder is None:
        return {}
    handle, path = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(handle, "w", encoding="ascii") as pem:
            pem.write(ssl.DER_cert_to_PEM_cert(der))
        return dict(decoder(path))
    except (OSError, ValueError, ssl.SSLError):
        return {}
    finally:
        with contextlib.suppress(OSError):
            os.remove(path)


def verifying_context() -> ssl.SSLContext:
    """Contexto que valida con el almacén del sistema y con ``certifi``."""
    context = ssl.create_default_context()
    with contextlib.suppress(OSError, ssl.SSLError):
        context.load_verify_locations(certifi.where())
    return context


def probe(host: str, port: int = DEFAULT_PORT, timeout: float = 10.0) -> TlsProbe:
    """Handshake TLS contra ``host:port``; lanza ``TlsError`` si no se puede conectar."""
    try:
        return _handshake(host, port, timeout, verifying_context())
    except ssl.SSLCertVerificationError as exc:
        reason = exc.verify_message or str(exc)
    except TimeoutError as exc:
        raise TlsError("timeout", str(exc)) from exc
    except ssl.SSLError as exc:
        raise TlsError("handshake", getattr(exc, "reason", None) or str(exc)) from exc
    except OSError as exc:
        raise TlsError("connection", str(exc)) from exc

    insecure = ssl.create_default_context()
    insecure.check_hostname = False
    insecure.verify_mode = ssl.CERT_NONE
    try:
        result = _handshake(host, port, timeout, insecure)
    except (OSError, ssl.SSLError) as exc:
        raise TlsError("handshake", str(exc)) from exc
    return TlsProbe(
        cert=result.cert,
        protocol=result.protocol,
        cipher=result.cipher,
        verified=False,
        verify_error=reason,
        peer_ip=result.peer_ip,
    )

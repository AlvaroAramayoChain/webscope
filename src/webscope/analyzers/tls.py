"""Interpretación del certificado TLS: emisor, SANs, vigencia y lo negociado.

Función pura: recibe el diccionario de ``ssl.getpeercert()`` (vía ``tlsprobe``) y la
fecha actual; no abre conexiones.
"""

from __future__ import annotations

import ssl
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from webscope.models import TlsResult

EXPIRY_WARNING_DAYS = 30


def _name_field(name: Iterable[Any], key: str) -> str:
    for rdn in name or ():
        for attr, value in rdn:
            if attr == key:
                return str(value)
    return ""


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(ssl.cert_time_to_seconds(value), tz=timezone.utc)
    except (ValueError, OverflowError):
        return None


def describe_issuer(cert: dict[str, Any]) -> str:
    """``Let's Encrypt (R11)``: organización emisora y su CN."""
    issuer = cert.get("issuer", ())
    org = _name_field(issuer, "organizationName")
    common = _name_field(issuer, "commonName")
    if org and common and common != org:
        return f"{org} ({common})"
    return org or common


def analyze_certificate(
    cert: dict[str, Any],
    *,
    protocol: str | None = None,
    cipher: str | None = None,
    verified: bool = True,
    verify_error: str | None = None,
    peer_ip: str | None = None,
    now: datetime | None = None,
) -> TlsResult:
    """Arma un ``TlsResult`` con días para vencer calculados contra ``now``."""
    now = now or datetime.now(timezone.utc)
    not_before = _parse_time(cert.get("notBefore"))
    not_after = _parse_time(cert.get("notAfter"))
    sans = tuple(value for kind, value in cert.get("subjectAltName", ()) if kind == "DNS")
    days_left = (not_after - now).days if not_after else None
    if not_after and not_after < now:
        days_left = -((now - not_after).days or 1)
    return TlsResult(
        subject=_name_field(cert.get("subject", ()), "commonName"),
        issuer=describe_issuer(cert),
        sans=sans,
        not_before=not_before.date().isoformat() if not_before else None,
        not_after=not_after.date().isoformat() if not_after else None,
        days_left=days_left,
        protocol=protocol,
        cipher=cipher,
        verified=verified,
        verify_error=verify_error,
        peer_ip=peer_ip,
    )


def is_expired(tls: TlsResult) -> bool:
    """El certificado ya venció."""
    return tls.days_left is not None and tls.days_left < 0


def is_expiring(tls: TlsResult, days: int = EXPIRY_WARNING_DAYS) -> bool:
    """El certificado vence en menos de ``days`` días (y todavía no venció)."""
    return tls.days_left is not None and 0 <= tls.days_left < days

import socket
import ssl
from datetime import datetime, timezone

import pytest

from webscope import tlsprobe
from webscope.analyzers.tls import analyze_certificate, describe_issuer, is_expired, is_expiring

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)
# Certificado con el formato de ``ssl.getpeercert()``, a 12 días de vencer.
EXPIRING_CERT = {
    "subject": ((("commonName", "ejemplo.com"),),),
    "issuer": (
        (("countryName", "US"),),
        (("organizationName", "Let's Encrypt"),),
        (("commonName", "R11"),),
    ),
    "notBefore": "Aug 17 00:00:00 2026 GMT",
    "notAfter": "Nov 15 23:59:59 2026 GMT",
    "subjectAltName": (("DNS", "ejemplo.com"), ("DNS", "www.ejemplo.com")),
}
# La función real: se toma al importar, antes de que el fixture ``fake_tls`` la reemplace.
REAL_PROBE = tlsprobe.probe


def test_expiring_certificate() -> None:
    result = analyze_certificate(EXPIRING_CERT, protocol="TLSv1.3", cipher="TLS_AES", now=NOW)
    assert result.issuer == "Let's Encrypt (R11)"
    assert result.subject == "ejemplo.com"
    assert result.sans == ("ejemplo.com", "www.ejemplo.com")
    assert result.not_after == "2026-11-15"
    assert result.days_left == 12
    assert is_expiring(result) and not is_expired(result)


def test_expired_certificate() -> None:
    later = datetime(2026, 12, 1, tzinfo=timezone.utc)
    result = analyze_certificate(EXPIRING_CERT, now=later)
    assert result.days_left is not None and result.days_left < 0
    assert is_expired(result) and not is_expiring(result)


def test_empty_certificate_does_not_crash() -> None:
    result = analyze_certificate({}, now=NOW)
    assert result.days_left is None and result.issuer == "" and result.sans == ()


def test_issuer_without_org() -> None:
    assert describe_issuer({"issuer": ((("commonName", "My CA"),),)}) == "My CA"


# --- tlsprobe con ssl/socket simulados ----------------------------------------------


def test_probe_reports_verification_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def handshake(
        host: str, port: int, timeout: float, context: ssl.SSLContext
    ) -> tlsprobe.TlsProbe:
        calls.append(context.verify_mode)
        if context.verify_mode == ssl.CERT_REQUIRED:
            error = ssl.SSLCertVerificationError("bad")
            error.verify_message = "self-signed certificate"
            raise error
        return tlsprobe.TlsProbe(cert=EXPIRING_CERT, protocol="TLSv1.2", peer_ip="203.0.113.5")

    monkeypatch.setattr(tlsprobe, "_handshake", handshake)
    result = REAL_PROBE("self-signed.example", 443, 3)
    assert not result.verified
    assert result.verify_error == "self-signed certificate"
    assert result.peer_ip == "203.0.113.5"
    assert calls == [ssl.CERT_REQUIRED, ssl.CERT_NONE]


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TimeoutError("slow"), "timeout"),
        (ConnectionRefusedError("refused"), "connection"),
        (socket.gaierror("dns"), "connection"),
        (ssl.SSLError("handshake failure"), "handshake"),
    ],
)
def test_probe_translates_errors(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    def handshake(*args: object) -> tlsprobe.TlsProbe:
        raise error

    monkeypatch.setattr(tlsprobe, "_handshake", handshake)
    with pytest.raises(tlsprobe.TlsError) as info:
        REAL_PROBE("x.example", 443, 3)
    assert info.value.code == code


def test_decode_der_handles_garbage() -> None:
    assert tlsprobe.decode_der(None) == {}
    assert tlsprobe.decode_der(b"not a certificate") == {}

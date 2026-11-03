"""Consultas DNS con ``dnspython``: registros, PTR y ASN vía Team Cymru.

Es el único módulo que hace consultas DNS. ``make_query()`` crea la función de
consulta real; los tests la reemplazan por una falsa. Cada consulta tiene timeout
corto y los errores no cortan el análisis: se cuentan y, si fallan todas, el bloque
de infraestructura se informa como no disponible.

Servicio de terceros: el ASN se resuelve con consultas TXT a ``origin.asn.cymru.com``
/ ``origin6.asn.cymru.com`` y ``asn.cymru.com`` (Team Cymru, sin API key).
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Final

from webscope.models import AsnInfo, DnsRecords

QueryFn = Callable[[str, str], list[str]]

DEFAULT_TIMEOUT: Final = 4.0
MAX_WORKERS: Final = 12
MAX_IPS_FOR_LOOKUPS: Final = 4
DKIM_SELECTORS: Final = (
    "default",
    "google",
    "selector1",
    "selector2",
    "k1",
    "k2",
    "s1",
    "s2",
    "dkim",
    "mail",
    "smtp",
    "zoho",
)
# Segundo nivel de dominios con sufijo compuesto (com.ar, co.uk...). Heurística simple:
# sin Public Suffix List para no sumar dependencias.
_COMPOUND_SLD: Final = frozenset(
    "com net org gob gov edu ac co mil int nom web blogspot ltd plc".split()
)


class DnsError(Exception):
    """Fallo de resolución (timeout, sin servidores...) con un código estable."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def make_query(timeout: float = DEFAULT_TIMEOUT) -> QueryFn:
    """Función ``query(nombre, tipo) -> [valores]`` con ``dnspython`` y timeouts cortos."""
    import dns.exception
    import dns.resolver

    try:
        resolver = dns.resolver.Resolver()
    except dns.exception.DNSException as exc:
        raise DnsError("no_resolver") from exc
    resolver.lifetime = timeout
    resolver.timeout = min(timeout, 2.0)

    def query(name: str, rtype: str) -> list[str]:
        try:
            answer = resolver.resolve(name, rtype, raise_on_no_answer=False)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return []
        except dns.exception.Timeout as exc:
            raise DnsError("timeout") from exc
        except dns.resolver.NoNameservers as exc:
            raise DnsError("no_nameservers") from exc
        except dns.exception.DNSException as exc:
            raise DnsError("error") from exc
        return [record_to_text(rdata, rtype) for rdata in answer]

    return query


def record_to_text(rdata: object, rtype: str) -> str:
    """Texto legible de un registro: TXT unido, MX ``pref host``, nombres sin punto final."""
    if rtype == "TXT":
        strings = getattr(rdata, "strings", ())
        return "".join(s.decode("utf-8", "replace") for s in strings)
    if rtype == "MX":
        exchange = str(getattr(rdata, "exchange", "")).rstrip(".") or "."
        return f"{getattr(rdata, 'preference', 0)} {exchange}"
    return str(rdata).rstrip(".")


# --- Nombres ------------------------------------------------------------------------


def is_ip(host: str) -> bool:
    """``True`` si ``host`` es una dirección IP (v4 o v6)."""
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def is_public_ip(value: str) -> bool:
    """``True`` si la IP es enrutable en Internet (no privada, loopback, etc.)."""
    try:
        return ipaddress.ip_address(value.strip("[]")).is_global
    except ValueError:
        return False


def is_local_host(host: str) -> bool:
    """``localhost``, ``*.local``, ``*.localhost`` o una IP no pública."""
    host = host.lower().strip("[]")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return True
    return is_ip(host) and not is_public_ip(host)


def registrable_domain(host: str) -> str:
    """Dominio registrable aproximado: ``www.shop.ejemplo.com.ar`` -> ``ejemplo.com.ar``."""
    labels = host.lower().strip(".").split(".")
    if len(labels) <= 2:
        return ".".join(labels)
    take = 3 if labels[-2] in _COMPOUND_SLD and len(labels[-1]) == 2 else 2
    return ".".join(labels[-take:])


def reverse_name(ip: str) -> str:
    """Nombre PTR de una IP (``4.3.2.1.in-addr.arpa``)."""
    address = ipaddress.ip_address(ip)
    return address.reverse_pointer


def cymru_origin_name(ip: str) -> str:
    """Nombre a consultar en Team Cymru para saber el ASN de ``ip``."""
    address = ipaddress.ip_address(ip)
    pointer = address.reverse_pointer
    if address.version == 4:
        return pointer.removesuffix(".in-addr.arpa") + ".origin.asn.cymru.com"
    return pointer.removesuffix(".ip6.arpa") + ".origin6.asn.cymru.com"


def parse_cymru_origin(text: str) -> AsnInfo | None:
    """``"13335 | 104.16.0.0/13 | US | arin | 2014-03-28"`` -> ``AsnInfo``."""
    fields = [part.strip() for part in text.split("|")]
    first = fields[0].split()[0] if fields and fields[0] else ""
    if not first.isdigit():
        return None
    fields += [""] * (4 - len(fields))
    return AsnInfo(asn=int(first), prefix=fields[1], country=fields[2], registry=fields[3])


def parse_cymru_asname(text: str) -> str:
    """``"13335 | US | arin | 2010-07-14 | CLOUDFLARENET - Cloudflare, Inc., US"`` -> org."""
    fields = [part.strip() for part in text.split("|")]
    name = fields[4] if len(fields) > 4 else ""
    name = re.sub(r",\s*[A-Z]{2}$", "", name)
    if " - " in name:
        name = name.split(" - ", 1)[1]
    return name


# --- Recolección --------------------------------------------------------------------


class _Collector:
    """Ejecuta consultas tolerando fallos y cuenta cuántas fallaron."""

    def __init__(self, query: QueryFn) -> None:
        self._query = query
        self.failed = 0
        self.total = 0
        self.last_error: str | None = None

    def attempt(self, name: str, rtype: str) -> tuple[list[str], bool]:
        """``(valores, respondió)``: distingue "no existe" de "la consulta falló"."""
        self.total += 1
        try:
            return self._query(name, rtype), True
        except DnsError as exc:
            self.last_error = exc.code
        except Exception:  # un resolver roto no debe cortar el reporte
            self.last_error = "error"
        self.failed += 1
        return [], False

    def __call__(self, name: str, rtype: str) -> list[str]:
        return self.attempt(name, rtype)[0]


def _lookup(run: _Collector, names: Iterable[str], rtype: str) -> tuple[list[str], bool]:
    """Primer nombre con respuesta; ``False`` si quedó vacío porque alguna consulta falló."""
    answered = True
    for name in dict.fromkeys(names):
        values, ok = run.attempt(name, rtype)
        if values:
            return values, True
        answered = answered and ok
    return [], answered


def lookup_asn(run: _Collector, ip: str) -> AsnInfo | None:
    """ASN, prefijo, país y organización de una IP pública vía Team Cymru."""
    if not is_public_ip(ip):
        return None
    answers = run(cymru_origin_name(ip), "TXT")
    origin = next((o for text in answers if (o := parse_cymru_origin(text))), None)
    if origin is None:
        return None
    names = run(f"AS{origin.asn}.asn.cymru.com", "TXT")
    org = parse_cymru_asname(names[0]) if names else ""
    return AsnInfo(origin.asn, org, origin.country, origin.prefix, origin.registry)


def collect(host: str, query: QueryFn, *, is_target_ip: bool = False) -> DnsRecords:
    """Junta registros, PTR y ASN del host. Nunca lanza: los fallos quedan contados."""
    run = _Collector(query)
    domain = host.lower().removeprefix("www.")
    org = registrable_domain(domain)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        if is_target_ip:
            futures = {}
            dkim = {}
            ips_v4 = [host] if ":" not in host else []
            ips_v6 = [host] if ":" in host else []
        else:
            plan: dict[str, tuple[tuple[str, ...], str]] = {
                "a": ((host,), "A"),
                "aaaa": ((host,), "AAAA"),
                "cname_root": ((domain,), "CNAME"),
                "cname_www": ((f"www.{domain}",), "CNAME"),
                "ns": ((domain, org), "NS"),
                "mx": ((domain,), "MX"),
                "txt": ((domain,), "TXT"),
                "caa": ((domain, org), "CAA"),
                "dmarc": ((f"_dmarc.{domain}", f"_dmarc.{org}"), "TXT"),
                "mta_sts": ((f"_mta-sts.{domain}",), "TXT"),
                "bimi": ((f"default._bimi.{domain}",), "TXT"),
            }
            futures = {
                key: pool.submit(_lookup, run, names, rtype) for key, (names, rtype) in plan.items()
            }
            dkim = {
                s: pool.submit(run.attempt, f"{s}._domainkey.{domain}", "TXT")
                for s in DKIM_SELECTORS
            }
            ips_v4 = futures["a"].result()[0]
            ips_v6 = futures["aaaa"].result()[0]
        lookup_ips = (ips_v4[:2] + ips_v6[:2])[:MAX_IPS_FOR_LOOKUPS]
        ptr_jobs = {ip: pool.submit(run, reverse_name(ip), "PTR") for ip in lookup_ips}
        asn_jobs = {ip: pool.submit(lookup_asn, run, ip) for ip in lookup_ips}
        results = {key: future.result() for key, future in futures.items()}
        values = {key: found for key, (found, _) in results.items()}
        unanswered = [key for key, (_, answered) in results.items() if not answered]
        ptr = {ip: job.result()[0] for ip, job in ptr_jobs.items() if job.result()}
        asn = {ip: info for ip, job in asn_jobs.items() if (info := job.result())}
        dkim_results = {s: job.result() for s, job in dkim.items()}
        dkim_found = tuple(
            s for s, (found, _) in dkim_results.items() if any(has_dkim_key(v) for v in found)
        )
        if dkim_results and not dkim_found and not all(ok for _, ok in dkim_results.values()):
            unanswered.append("dkim")
    cname = {
        name: values[key][0]
        for name, key in ((domain, "cname_root"), (f"www.{domain}", "cname_www"))
        if values.get(key)
    }
    error = run.last_error if run.total and run.failed == run.total else None
    return DnsRecords(
        a=tuple(ips_v4),
        aaaa=tuple(ips_v6),
        cname=cname,
        ns=tuple(sorted(values.get("ns", []))),
        mx=tuple(sorted(values.get("mx", []), key=_mx_order)),
        txt=tuple(values.get("txt", [])),
        caa=tuple(values.get("caa", [])),
        dmarc=tuple(v for v in values.get("dmarc", []) if v.lower().startswith("v=dmarc1")),
        dkim=dkim_found,
        mta_sts=tuple(v for v in values.get("mta_sts", []) if "sts" in v.lower()),
        bimi=tuple(v for v in values.get("bimi", []) if "bimi" in v.lower()),
        ptr=ptr,
        asn=asn,
        failed=run.failed,
        error=error,
        unanswered=tuple(unanswered),
    )


def has_dkim_key(record: str) -> bool:
    """Registro DKIM con clave pública (``p=`` vacío significa clave revocada)."""
    return re.search(r"(?:^|;)\s*p=[A-Za-z0-9+/]{16,}", record) is not None


def is_null_mx(value: str) -> bool:
    """MX nulo (RFC 7505): ``0 .`` indica que el dominio no recibe correo."""
    return value.split()[-1:] == ["."]


def _mx_order(value: str) -> tuple[int, str]:
    pref, _, host = value.partition(" ")
    return (int(pref) if pref.isdigit() else 0, host)

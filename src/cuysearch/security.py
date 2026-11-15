import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """La URL no es válida o apunta a un destino no público."""


_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google.com",
}


def validate_public_url(url: str) -> str:
    """Valida sintaxis y bloquea destinos obviamente internos."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Solo se permiten URLs http y https")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("No se permiten credenciales embebidas en la URL")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname or hostname in _BLOCKED_HOSTNAMES:
        raise UnsafeUrlError("El destino no es público")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not _is_public(address):
        raise UnsafeUrlError("No se permiten IPs privadas o reservadas")
    return url


def _is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Global y no reservada: Python da por global la IPv6 «compatible» ::a.b.c.d (::/96, reservada)."""

    return address.is_global and not address.is_reserved


async def validate_resolved_public_url(url: str) -> str:
    """Evita SSRF también cuando un dominio resuelve a una IP privada."""

    await resolve_public_addresses(url)
    return url


async def resolve_public_addresses(url: str) -> list[str]:
    """Resuelve el nombre una sola vez y devuelve sus IP, todas públicas, en el orden del sistema.

    Quien conecte debe hacerlo a una de estas IP y no volver a resolver el nombre: si no, un DNS que
    cambia entre la comprobación y la conexión («DNS rebinding») lleva a una red interna.
    """

    validate_public_url(url)
    hostname = urlparse(url).hostname
    if hostname is None:
        raise UnsafeUrlError("URL sin hostname")
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError("No se pudo resolver el dominio") from exc

    addresses = list(dict.fromkeys(info[4][0] for info in infos if info[4]))
    if not addresses:
        raise UnsafeUrlError("El dominio no tiene direcciones válidas")
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise UnsafeUrlError("El dominio resolvió a una dirección inválida") from exc
        if not _is_public(address):
            raise UnsafeUrlError("El dominio resuelve a una red no pública")
    return addresses


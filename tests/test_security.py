import pytest

from cuysearch.security import UnsafeUrlError, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://user:password@example.com/private",
        # IPv6 «compatible con IPv4» (::/96, reservado): Python la da por global.
        "http://[::127.0.0.1]:8080/",
        "http://[::a9fe:a9fe]/latest/meta-data",
    ],
)
def test_blocks_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_url(url)


def test_allows_public_http_url() -> None:
    assert validate_public_url("https://example.com/path") == "https://example.com/path"
    assert validate_public_url("http://[2606:4700::6810:84e5]/") == "http://[2606:4700::6810:84e5]/"


async def test_un_dominio_que_resuelve_a_ipv6_compatible_no_pasa(monkeypatch) -> None:
    import socket

    from cuysearch.security import resolve_public_addresses

    def falso(host, port, *args, **kwargs):
        return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::127.0.0.1", 0, 0, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", falso)
    with pytest.raises(UnsafeUrlError):
        await resolve_public_addresses("http://ejemplo.org/")


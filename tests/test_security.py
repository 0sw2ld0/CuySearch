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
    ],
)
def test_blocks_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_url(url)


def test_allows_public_http_url() -> None:
    assert validate_public_url("https://example.com/path") == "https://example.com/path"


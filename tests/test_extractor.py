import httpx
import pytest

from cuysearch import ErrorDeLectura
from cuysearch import extractor as modulo
from cuysearch.extractor import PageExtractor, _LimitedHTMLTextParser


def test_html_parser_extracts_text_without_scripts_or_navigation() -> None:
    parser = _LimitedHTMLTextParser(max_chars=100)
    parser.feed(
        "<html><head><title> Demo </title><script>bad()</script></head>"
        "<body><nav>menu</nav><main><h1>Hello</h1><p>world</p></main></body></html>"
    )

    title, content, truncated = parser.result()

    assert title == "Demo"
    assert content == "Hello world"
    assert truncated is False


def test_html_parser_caps_retained_content() -> None:
    parser = _LimitedHTMLTextParser(max_chars=10)
    parser.feed("<p>01234567890123456789</p>")

    _, content, truncated = parser.result()

    assert content == "0123456789"
    assert truncated is True


@pytest.fixture
def red_falsa(monkeypatch):
    """Sustituye la red por un transporte falso; la validación DNS se simula."""
    rutas = {}
    validadas = []

    async def validar(url):
        validadas.append(url)
        if "privado" in url:
            raise modulo.UnsafeUrlError("El dominio resuelve a una red no pública")
        return url

    def responder(request):
        return rutas[str(request.url)]

    monkeypatch.setattr(modulo, "validate_resolved_public_url", validar)
    original = PageExtractor._new_client

    def cliente(self):
        nuevo = original(self)
        nuevo._transport = httpx.MockTransport(responder)
        return nuevo

    monkeypatch.setattr(PageExtractor, "_new_client", cliente)
    return rutas, validadas


async def test_lee_una_pagina_y_valida_cada_redireccion(red_falsa):
    rutas, validadas = red_falsa
    rutas["https://ejemplo.org/"] = httpx.Response(301, headers={"location": "/final"})
    rutas["https://ejemplo.org/final"] = httpx.Response(
        200, headers={"content-type": "text/html"}, text="<title>T</title><main>Hola</main>"
    )

    pagina = await PageExtractor().extract("https://ejemplo.org/")

    assert (pagina.url, pagina.titulo, pagina.texto) == ("https://ejemplo.org/final", "T", "Hola")
    assert validadas == ["https://ejemplo.org/", "https://ejemplo.org/final"]


async def test_no_sigue_una_redireccion_a_una_red_privada(red_falsa):
    rutas, _ = red_falsa
    rutas["https://ejemplo.org/"] = httpx.Response(302, headers={"location": "https://privado.local/"})

    with pytest.raises(ErrorDeLectura, match="no pública"):
        await PageExtractor().extract("https://ejemplo.org/")


async def test_rechaza_tipos_no_soportados_y_paginas_grandes(red_falsa):
    rutas, _ = red_falsa
    rutas["https://ejemplo.org/a.pdf"] = httpx.Response(200, headers={"content-type": "application/pdf"})
    rutas["https://ejemplo.org/grande"] = httpx.Response(200, headers={"content-type": "text/plain"}, text="x" * 5000)

    with pytest.raises(ErrorDeLectura, match="no soportado"):
        await PageExtractor().extract("https://ejemplo.org/a.pdf")
    with pytest.raises(ErrorDeLectura, match="tamaño"):
        await PageExtractor(max_fetch_bytes=1024).extract("https://ejemplo.org/grande")


async def test_rechaza_localhost_sin_salir_a_la_red():
    with pytest.raises(ErrorDeLectura):
        await PageExtractor().extract("http://localhost:8080/")

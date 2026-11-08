"""Lectura de páginas públicas con límites de tamaño y protección anti-SSRF."""

from __future__ import annotations

import asyncio
import codecs
import weakref
from contextlib import asynccontextmanager
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from cuysearch.motores.base import USER_AGENT
from cuysearch.security import UnsafeUrlError, validate_resolved_public_url
from cuysearch.tipos import ErrorDeLectura, Pagina

# Nombre anterior, por compatibilidad.
ExtractionError = ErrorDeLectura


class _LimitedHTMLTextParser(HTMLParser):
    """Extrae texto sin construir un árbol DOM completo en memoria."""

    _ignored_tags = {"script", "style", "noscript", "template", "svg", "canvas", "nav", "footer"}

    def __init__(self, max_chars: int) -> None:
        super().__init__(convert_charrefs=True)
        self.max_chars = max_chars
        self.parts: list[str] = []
        self.preferred_parts: list[str] = []
        self.title_parts: list[str] = []
        self._ignored_depth = 0
        self._head_depth = 0
        self._title_depth = 0
        self._preferred_depth = 0
        self._captured_chars = 0
        self._preferred_chars = 0
        self._fallback_truncated = False
        self._preferred_truncated = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        if tag in self._ignored_tags:
            self._ignored_depth += 1
        elif tag == "head":
            self._head_depth += 1
        if tag == "title":
            self._title_depth += 1
        if tag in {"main", "article"}:
            self._preferred_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag == "head" and self._head_depth:
            self._head_depth -= 1
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag in {"main", "article"} and self._preferred_depth:
            self._preferred_depth -= 1

    def _append_limited(self, target: list[str], data: str, preferred: bool) -> None:
        captured = self._preferred_chars if preferred else self._captured_chars
        remaining = self.max_chars + 1 - captured
        if remaining <= 0:
            if preferred:
                self._preferred_truncated = True
            else:
                self._fallback_truncated = True
            return
        target.append(data[:remaining])
        if preferred:
            self._preferred_chars += min(len(data), remaining)
            self._preferred_truncated |= len(data) > remaining
        else:
            self._captured_chars += min(len(data), remaining)
            self._fallback_truncated |= len(data) > remaining

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._title_depth and sum(map(len, self.title_parts)) < 500:
            self.title_parts.append(data)
        if self._head_depth or not data.strip():
            return
        self._append_limited(self.parts, data, preferred=False)
        if self._preferred_depth:
            self._append_limited(self.preferred_parts, data, preferred=True)

    def result(self) -> tuple[str | None, str, bool]:
        title = " ".join(" ".join(self.title_parts).split())[:500] or None
        selected = self.preferred_parts or self.parts
        content = " ".join(" ".join(selected).split())
        truncated = (
            self._preferred_truncated if self.preferred_parts else self._fallback_truncated
        ) or len(content) > self.max_chars
        return title, content[: self.max_chars], truncated


class PageExtractor:
    """Descarga páginas http(s) públicas y devuelve su texto.

    Con `persistente=False` (lo normal en una librería) abre un cliente HTTP
    por lectura, así sirve igual desde varios bucles de asyncio. Un servicio
    de larga vida puede usar `persistente=True` y llamar a `close()`.
    """

    def __init__(
        self,
        timeout_seconds: float = 20.0,
        max_fetch_bytes: int = 2_000_000,
        max_content_chars: int = 20_000,
        max_redirects: int = 3,
        max_concurrent: int = 2,
        user_agent: str = USER_AGENT,
        max_keepalive_connections: int = 2,
        persistente: bool = False,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_fetch_bytes = max_fetch_bytes
        self.max_content_chars = max_content_chars
        self.max_redirects = max_redirects
        # Un semáforo por bucle: un asyncio.Semaphore queda atado al primer bucle que lo espera.
        self._semaphores: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self.user_agent = user_agent
        self.max_concurrent = max(1, max_concurrent)
        self.max_keepalive_connections = max(0, max_keepalive_connections)
        self.persistente = persistente
        self._client: httpx.AsyncClient | None = None

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html, text/plain, application/json;q=0.9",
            },
            follow_redirects=False,
            limits=httpx.Limits(
                max_connections=self.max_concurrent,
                max_keepalive_connections=self.max_keepalive_connections,
            ),
        )

    @asynccontextmanager
    async def _client_for_call(self):
        if not self.persistente:
            async with self._new_client() as client:
                yield client
            return
        if self._client is None:
            self._client = self._new_client()
        yield self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        semaphore = self._semaphores.get(loop)
        if semaphore is None:
            semaphore = self._semaphores[loop] = asyncio.Semaphore(self.max_concurrent)
        return semaphore

    async def extract(self, url: str) -> Pagina:
        async with self._semaphore(), self._client_for_call() as client:
            return await self._extract_limited(client, url)

    async def _extract_limited(self, client: httpx.AsyncClient, url: str) -> Pagina:
        current_url = url
        content_type = ""
        parser: _LimitedHTMLTextParser | None = None
        plain_body = bytearray()

        for redirect_count in range(self.max_redirects + 1):
            try:
                await validate_resolved_public_url(current_url)
            except UnsafeUrlError as exc:
                raise ExtractionError(str(exc)) from exc

            try:
                async with client.stream("GET", current_url) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location or redirect_count >= self.max_redirects:
                            raise ExtractionError("Se alcanzó el límite de redirecciones")
                        current_url = urljoin(current_url, location)
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    if content_type not in {
                        "text/html",
                        "application/xhtml+xml",
                        "text/plain",
                        "application/json",
                    }:
                        raise ExtractionError(
                            f"Tipo de contenido no soportado: {content_type or 'desconocido'}"
                        )

                    declared_length = response.headers.get("content-length")
                    if declared_length and int(declared_length) > self.max_fetch_bytes:
                        raise ExtractionError("La página supera el límite de tamaño")

                    is_html = content_type in {"text/html", "application/xhtml+xml"}
                    parser = _LimitedHTMLTextParser(self.max_content_chars) if is_html else None
                    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace") if is_html else None
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self.max_fetch_bytes:
                            raise ExtractionError("La página supera el límite de tamaño")
                        if parser is not None and decoder is not None:
                            parser.feed(decoder.decode(chunk))
                        else:
                            plain_body.extend(chunk)
                    if parser is not None and decoder is not None:
                        parser.feed(decoder.decode(b"", final=True))
                        parser.close()
                    break
            except ExtractionError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                raise ExtractionError(f"No se pudo descargar la página: {exc}") from exc
        else:
            raise ExtractionError("No se pudo resolver la redirección")

        title: str | None = None
        if parser is not None:
            title, text, truncated = parser.result()
        else:
            text = " ".join(plain_body.decode("utf-8", errors="replace").split())
            truncated = len(text) > self.max_content_chars
            text = text[: self.max_content_chars]

        return Pagina(
            url=current_url,
            titulo=title,
            texto=text,
            tipo=content_type or None,
            truncada=truncated,
        )

    async def extract_many(self, urls: list[str]) -> tuple[list[Pagina], list[dict[str, str]]]:
        async def one(url: str) -> Pagina | dict[str, str]:
            try:
                return await self.extract(url)
            except ExtractionError as exc:
                return {"url": url, "error": str(exc)}

        values = await asyncio.gather(*(one(url) for url in urls))
        pages = [value for value in values if isinstance(value, Pagina)]
        failures = [value for value in values if isinstance(value, dict)]
        return pages, failures

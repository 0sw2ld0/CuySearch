"""API HTTP de CuySearch (extra `[servicio]`).

Mantiene el contrato de la versión anterior: `POST /v1/search`,
`POST /v1/extract`, `GET /healthz` y la cabecera `X-CuySearch-Key` (o
`Authorization: Bearer`). La búsqueda la hace la librería, con su caída de
un motor al siguiente.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from cuysearch import __version__
from cuysearch.buscador import Buscador
from cuysearch.extractor import PageExtractor
from cuysearch.motores import Configuracion
from cuysearch.servicio.config import Settings
from cuysearch.servicio.modelos import (
    ExtractedPage,
    ExtractRequest,
    ExtractResponse,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from cuysearch.tipos import ErrorDeBusqueda, ErrorDeLectura, Pagina

_PERIODOS = {"day": "dia", "week": "semana", "month": "mes", "year": "año"}


def crear_buscador(settings: Settings) -> Buscador:
    extractor = PageExtractor(
        timeout_seconds=settings.cuysearch_extract_timeout_seconds,
        max_fetch_bytes=settings.cuysearch_max_fetch_bytes,
        max_content_chars=settings.cuysearch_max_content_chars,
        max_redirects=settings.cuysearch_max_redirects,
        max_concurrent=settings.cuysearch_max_concurrent_extractions,
        user_agent=settings.cuysearch_user_agent,
        max_keepalive_connections=settings.cuysearch_http_keepalive_connections,
        persistente=True,
    )
    config = Configuracion(
        searxng_url=(settings.searxng_base_url or "").strip() or None,
        claves=Configuracion.desde_entorno().claves,
        tiempo=settings.cuysearch_request_timeout_seconds,
    )
    return Buscador(
        settings.motores,
        config=config,
        cache_segundos=settings.cuysearch_cache_ttl_seconds,
        cache_entradas=settings.cuysearch_cache_max_entries,
        extractor=extractor,
    )


def _pagina(pagina: Pagina) -> ExtractedPage:
    return ExtractedPage(url=pagina.url, title=pagina.titulo, content=pagina.texto,
                         content_type=pagina.tipo, truncated=pagina.truncada)


def create_app(settings: Settings, buscador: Buscador | None = None) -> FastAPI:
    buscador = buscador or crear_buscador(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await buscador.cerrar()

    app = FastAPI(
        title="CuySearch",
        description="Búsqueda y lectura web para agentes.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.buscador = buscador

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    async def require_api_key(
        x_cuysearch_key: Annotated[str | None, Header()] = None,
        authorization: Annotated[str | None, Header()] = None,
    ) -> None:
        expected = settings.cuysearch_api_key
        if not expected:
            return
        bearer = authorization.removeprefix("Bearer ").strip() if authorization else None
        key_matches = x_cuysearch_key is not None and compare_digest(x_cuysearch_key, expected)
        bearer_matches = bearer is not None and compare_digest(bearer, expected)
        if not key_matches and not bearer_matches:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key inválida o ausente",
            )

    @app.get("/", response_model=HealthResponse)
    async def root() -> HealthResponse:
        return HealthResponse(version=__version__)

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(version=__version__)

    @app.post("/v1/search", response_model=SearchResponse, dependencies=[Depends(require_api_key)])
    async def search(request: SearchRequest) -> SearchResponse:
        inicio = time.perf_counter()
        try:
            busqueda = await buscador.buscar(
                request.query,
                request.domains,
                max_resultados=request.max_results,
                excluir=request.exclude_domains,
                periodo=_PERIODOS.get(request.time_range or ""),
                noticias=request.topic == "news",
            )
        except ErrorDeBusqueda as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        total = len(busqueda.resultados)
        results = [
            SearchResult(title=r.titulo, url=r.url, content=r.fragmento,
                         score=round(1.0 - i / max(total, 1), 3), published_date=r.fecha)
            for i, r in enumerate(busqueda.resultados)
        ]
        warnings = list(busqueda.avisos)
        if request.include_raw_content and results:
            lecturas = await asyncio.gather(*(buscador.leer(str(r.url)) for r in results), return_exceptions=True)
            enriquecidos = []
            for resultado, lectura in zip(results, lecturas):
                if isinstance(lectura, Pagina):
                    resultado = resultado.model_copy(update={"raw_content": lectura.texto})
                elif isinstance(lectura, ErrorDeLectura):
                    warnings.append(f"{resultado.url}: {lectura}")
                elif isinstance(lectura, BaseException):
                    raise lectura
                enriquecidos.append(resultado)
            results = enriquecidos

        return SearchResponse(
            query=request.query,
            results=results,
            response_time=max(0.0, time.perf_counter() - inicio),
            provider=busqueda.motor or "ninguno",
            warnings=warnings,
        )

    @app.post("/v1/extract", response_model=ExtractResponse, dependencies=[Depends(require_api_key)])
    async def extract(request: ExtractRequest) -> ExtractResponse:
        paginas, fallos = await buscador.extractor.extract_many([str(url) for url in request.urls])
        return ExtractResponse(results=[_pagina(p) for p in paginas], failed_results=fallos)

    return app

"""El buscador: prueba los motores en orden y lee páginas con cuidado."""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Sequence
from contextlib import asynccontextmanager

import httpx

from cuysearch import motores as registro
from cuysearch.cache import TTLCache
from cuysearch.extractor import PageExtractor
from cuysearch.motores import Configuracion, ErrorDeMotor, Motor, MotorBloqueado
from cuysearch.tipos import Busqueda, Consulta, ErrorDeBusqueda, Pagina, Periodo, Resultado
from cuysearch.utiles import en_dominios, normalizar_dominio

log = logging.getLogger("cuysearch")

MAX_DOMINIOS = 10
_PERIODOS = ("dia", "semana", "mes", "año")


def _motores_del_entorno() -> list[str] | str:
    valor = (os.environ.get("CUYSEARCH_MOTORES") or "").strip()
    if not valor or valor == "auto":
        return "auto"
    return [m.strip() for m in valor.split(",") if m.strip()]


class Buscador:
    """Busca con el primer motor que responda y recuerda a los que bloquean.

    Un motor que limita (429, 403 o captcha) descansa `pausa_tras_bloqueo`
    segundos: así no se insiste desde la conexión del usuario.
    """

    def __init__(
        self,
        motores: Sequence[str | Motor] | str | None = None,
        *,
        config: Configuracion | None = None,
        idioma: str | None = None,
        cache_segundos: int = 300,
        cache_entradas: int = 64,
        pausa_tras_bloqueo: float = 600.0,
        extractor: PageExtractor | None = None,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or Configuracion.desde_entorno()
        self.idioma = idioma
        self._motores = self._resolver(motores if motores is not None else "auto")
        self._cache: TTLCache[Busqueda] = TTLCache(cache_segundos, max_entries=cache_entradas, max_bytes=2_000_000)
        self._pausa = pausa_tras_bloqueo
        self._pausados: dict[str, float] = {}
        self._extractor = extractor or PageExtractor()
        self._cliente = cliente

    @property
    def motores(self) -> list[str]:
        return [m.nombre for m in self._motores]

    def _resolver(self, motores: Sequence[str | Motor] | str) -> list[Motor]:
        if isinstance(motores, str):
            motores = registro.orden_automatico(self.config) if motores == "auto" else [motores]
        resueltos: list[Motor] = []
        for motor in motores:
            resueltos.append(motor if isinstance(motor, Motor) else registro.crear(motor, self.config))
        if not resueltos:
            raise ValueError("Hace falta al menos un motor")
        return resueltos

    @asynccontextmanager
    async def _http(self):
        if self._cliente is not None:
            yield self._cliente
            return
        async with httpx.AsyncClient(follow_redirects=False,
                                     limits=httpx.Limits(max_connections=4, max_keepalive_connections=2)) as cliente:
            yield cliente

    async def buscar(
        self,
        consulta: str,
        dominios: Sequence[str] | None = None,
        motores: Sequence[str | Motor] | str | None = None,
        *,
        max_resultados: int = 8,
        excluir: Sequence[str] | None = None,
        periodo: Periodo | None = None,
        noticias: bool = False,
    ) -> Busqueda:
        texto = " ".join(str(consulta or "").split())
        if not 2 <= len(texto) <= 500:
            raise ValueError("La consulta debe tener entre 2 y 500 caracteres")
        if periodo is not None and periodo not in _PERIODOS:
            raise ValueError(f"periodo debe ser uno de: {', '.join(_PERIODOS)}")
        pedido = Consulta(
            texto=texto,
            max_resultados=max(1, min(int(max_resultados), 20)),
            dominios=_dominios(dominios),
            excluir=_dominios(excluir),
            periodo=periodo,
            noticias=noticias,
            idioma=self.idioma,
        )
        lista = self._motores if motores is None else self._resolver(motores)

        clave = json.dumps([pedido.texto, pedido.max_resultados, pedido.dominios, pedido.excluir,
                            pedido.periodo, pedido.noticias, pedido.idioma, [m.nombre for m in lista]])
        if (guardada := await self._cache.get(clave)) is not None:
            return guardada

        avisos: list[str] = []
        alguno_respondio = False
        async with self._http() as cliente:
            for motor in lista:
                hasta = self._pausados.get(motor.nombre, 0.0)
                if hasta > time.monotonic():
                    avisos.append(f"{motor.nombre}: en pausa tras un bloqueo reciente")
                    continue
                try:
                    encontrados = await motor.buscar(cliente, pedido)
                except MotorBloqueado as exc:
                    self._pausados[motor.nombre] = time.monotonic() + self._pausa
                    avisos.append(f"{motor.nombre}: {exc}")
                    log.info("%s bloqueó la búsqueda; descansa %.0f s", motor.nombre, self._pausa)
                    continue
                except ErrorDeMotor as exc:
                    avisos.append(f"{motor.nombre}: {exc}")
                    continue
                except Exception as exc:  # un motor roto no debe tumbar la búsqueda
                    log.exception("Fallo inesperado en %s", motor.nombre)
                    avisos.append(f"{motor.nombre}: fallo inesperado ({type(exc).__name__})")
                    continue
                alguno_respondio = True
                resultados = _depurar(encontrados, pedido)
                if resultados:
                    busqueda = Busqueda(texto, resultados, motor.nombre, avisos)
                    await self._cache.set(clave, busqueda)
                    return busqueda
                avisos.append(f"{motor.nombre}: sin resultados")

        if not alguno_respondio:
            raise ErrorDeBusqueda("Ningún motor respondió. " + "; ".join(avisos))
        return Busqueda(texto, [], None, avisos)

    @property
    def extractor(self) -> PageExtractor:
        return self._extractor

    async def leer(self, url: str) -> Pagina:
        return await self._extractor.extract(str(url or "").strip())

    async def cerrar(self) -> None:
        await self._extractor.close()


def _dominios(valores: Sequence[str] | None) -> tuple[str, ...]:
    if isinstance(valores, str):
        valores = [valores]
    limpios: list[str] = []
    for valor in valores or ():
        dominio = normalizar_dominio(valor)
        if dominio and dominio not in limpios:
            limpios.append(dominio)
    return tuple(limpios[:MAX_DOMINIOS])


def _depurar(resultados: list[Resultado], pedido: Consulta) -> list[Resultado]:
    """Sin duplicados, dentro de los dominios pedidos y no más de los pedidos."""
    vistos: set[str] = set()
    limpios = []
    for resultado in resultados:
        url = resultado.url.rstrip("/")
        if url in vistos:
            continue
        if pedido.dominios and not en_dominios(resultado.url, pedido.dominios):
            continue
        if pedido.excluir and en_dominios(resultado.url, pedido.excluir):
            continue
        vistos.add(url)
        limpios.append(resultado)
        if len(limpios) >= pedido.max_resultados:
            break
    return limpios


_predeterminado: Buscador | None = None


def predeterminado() -> Buscador:
    """El buscador que usan `buscar()` y `leer()`, configurado por el entorno."""
    global _predeterminado
    if _predeterminado is None:
        _predeterminado = Buscador(_motores_del_entorno())
    return _predeterminado


async def buscar(
    consulta: str,
    dominios: Sequence[str] | None = None,
    motores: Sequence[str | Motor] | str | None = None,
    **opciones,
) -> Busqueda:
    """Busca en la web desde la conexión de quien llama.

    `motores` admite "auto" o una lista de nombres (ver `cuysearch.motores.TODOS`);
    si un motor falla o bloquea, se pasa al siguiente.
    """
    return await predeterminado().buscar(consulta, dominios, motores, **opciones)


async def leer(url: str) -> Pagina:
    """Texto limpio de una página pública; rechaza localhost y redes privadas."""
    return await predeterminado().leer(url)

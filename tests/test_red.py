"""Pruebas contra internet de verdad. No corren por defecto: `pytest -m red`."""

import pytest

import cuysearch
from cuysearch import Buscador, ErrorDeBusqueda
from cuysearch.motores import GRATUITOS

pytestmark = pytest.mark.red


@pytest.mark.parametrize("motor", GRATUITOS)
async def test_cada_motor_gratuito(motor):
    try:
        busqueda = await Buscador([motor]).buscar("python asyncio event loop", max_resultados=3)
    except ErrorDeBusqueda as exc:
        pytest.skip(f"{motor} no respondió desde esta conexión: {exc}")
    print(motor, [r.url for r in busqueda.resultados], busqueda.avisos)


async def test_buscar_y_leer():
    busqueda = await cuysearch.buscar("httpx timeouts", dominios=["python-httpx.org"])
    assert busqueda.resultados
    pagina = await cuysearch.leer(busqueda.resultados[0].url)
    assert "timeout" in pagina.texto.lower()

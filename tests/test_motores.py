import json

import httpx
import pytest

from cuysearch.motores import Configuracion, MotorBloqueado, crear, orden_automatico
from cuysearch.motores.apis import BraveAPI, Exa, Ollama, SearXNG, Tavily
from cuysearch.motores.bing import Bing, desenvolver_url
from cuysearch.motores.brave import Brave
from cuysearch.motores.duckduckgo import DuckDuckGo
from cuysearch.motores.mojeek import Mojeek
from cuysearch.motores.wikipedia import Wikipedia
from cuysearch.tipos import Consulta

DDG = """
<div class="result results_links web-result"><div class="links_main result__body">
  <h2 class="result__title"><a class="result__a" href="https://ejemplo.org/a">Uno &amp; <b>dos</b></a></h2>
  <a class="result__snippet" href="https://ejemplo.org/a">Texto <b>del</b> fragmento</a>
</div></div>
<div class="result"><div class="result__body">
  <h2><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fejemplo.net%2Fb&rut=x">Envuelto</a></h2>
</div></div>
<div class="result"><div class="result__body">
  <h2><a class="result__a" href="https://duckduckgo.com/y.js?ad=1">Anuncio</a></h2>
</div></div>
"""


def test_duckduckgo_lee_resultados_desenvuelve_y_quita_anuncios():
    resultados = DuckDuckGo().leer(200, DDG)

    assert [(r.titulo, r.url) for r in resultados] == [
        ("Uno & dos", "https://ejemplo.org/a"),
        ("Envuelto", "https://ejemplo.net/b"),
    ]
    assert resultados[0].fragmento == "Texto del fragmento"
    assert resultados[0].motor == "duckduckgo"


def test_duckduckgo_con_anomalia_es_un_bloqueo():
    with pytest.raises(MotorBloqueado):
        DuckDuckGo().leer(202, "<div class='anomaly-modal'></div>")


def test_bing_desenvuelve_ck_a():
    envuelto = "https://www.bing.com/ck/a?!&p=abc&u=a1aHR0cHM6Ly93d3cucHl0aG9uLm9yZy8&ntb=1"

    assert desenvolver_url(envuelto) == "https://www.python.org/"
    assert desenvolver_url("https://ejemplo.org/") == "https://ejemplo.org/"


def test_bing_lee_resultados_y_salta_anuncios():
    html = """
    <li class="b_algo"><h2><a href="https://www.bing.com/ck/a?u=a1aHR0cHM6Ly9lamVtcGxvLm9yZy8">Ejemplo</a></h2>
      <div class="b_caption"><p class="b_lineclamp2">Un <strong>fragmento</strong></p></div></li>
    <li class="b_algo"><h2><a href="https://www.bing.com/aclick?x=1">Anuncio</a></h2></li>
    """
    resultados = Bing().leer(html)

    assert [(r.titulo, r.url, r.fragmento) for r in resultados] == [("Ejemplo", "https://ejemplo.org/", "Un fragmento")]


def test_bing_con_captcha_es_un_bloqueo():
    with pytest.raises(MotorBloqueado):
        Bing().leer('<div id="b_captcha"></div>')


def test_brave_lee_resultados():
    html = """
    <div data-type="web"><a href="https://ejemplo.org/x"><div class="site-name-content">ejemplo</div>
      <div class="title search-snippet-title">Título X</div></a>
      <div class="snippet"><div class="content desktop">Fragmento X</div></div></div>
    """
    resultados = Brave().leer(html)

    assert [(r.titulo, r.url, r.fragmento) for r in resultados] == [("Título X", "https://ejemplo.org/x", "Fragmento X")]


def test_mojeek_lee_resultados_y_detecta_captcha():
    html = """<ul class="results-standard"><li><h2><a href="https://ejemplo.org/m">M</a></h2>
              <p class="s">Fragmento M</p></li></ul>"""

    assert [(r.titulo, r.fragmento) for r in Mojeek().leer(html)] == [("M", "Fragmento M")]
    with pytest.raises(MotorBloqueado):
        Mojeek().leer("<html><head><title>Captcha</title></head></html>")


def test_wikipedia_arma_la_url_del_articulo():
    datos = {"query": {"search": [{"title": "Event loop", "snippet": 'An <span class="searchmatch">event</span> loop',
                                   "timestamp": "2026-01-01T00:00:00Z"}]}}

    [resultado] = Wikipedia().leer(datos, "en.wikipedia.org")

    assert resultado.url == "https://en.wikipedia.org/wiki/Event_loop"
    assert resultado.fragmento == "An event loop"
    assert resultado.fecha == "2026-01-01T00:00:00Z"


async def test_wikipedia_no_consulta_si_los_dominios_no_la_incluyen():
    def no_debe_llamarse(request):
        raise AssertionError("no debía salir a la red")

    async with httpx.AsyncClient(transport=httpx.MockTransport(no_debe_llamarse)) as cliente:
        assert await Wikipedia().buscar(cliente, Consulta("asyncio", dominios=("python.org",))) == []


def test_filtros_de_sitio():
    assert Consulta("x", dominios=("a.org",)).con_filtros_de_sitio() == "x site:a.org"
    assert Consulta("x", dominios=("a.org", "b.org"), excluir=("c.org",)).con_filtros_de_sitio() == (
        "x (site:a.org OR site:b.org) -site:c.org"
    )


@pytest.mark.parametrize("estado", [403, 429])
async def test_403_y_429_son_bloqueos(estado):
    transporte = httpx.MockTransport(lambda request: httpx.Response(estado))
    async with httpx.AsyncClient(transport=transporte) as cliente:
        with pytest.raises(MotorBloqueado):
            await DuckDuckGo().buscar(cliente, Consulta("hola"))


async def _llamar(motor, respuesta, consulta=None):
    peticiones = []

    def responder(request):
        peticiones.append(request)
        return httpx.Response(200, json=respuesta)

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cliente:
        resultados = await motor.buscar(cliente, consulta or Consulta("hola mundo", dominios=("ejemplo.org",)))
    return resultados, peticiones[0]


async def test_searxng_pide_json_con_filtros():
    resultados, peticion = await _llamar(
        SearXNG("http://127.0.0.1:8888"),
        {"results": [{"title": "S", "url": "https://ejemplo.org/s", "content": "c", "publishedDate": "2026"}]},
    )

    assert peticion.url.params["format"] == "json"
    assert peticion.url.params["q"] == "hola mundo site:ejemplo.org"
    assert [(r.titulo, r.fecha) for r in resultados] == [("S", "2026")]


async def test_ollama_manda_la_clave_en_la_cabecera():
    resultados, peticion = await _llamar(
        Ollama("clave-de-prueba"), {"results": [{"title": "O", "url": "https://ejemplo.org/o", "content": "c"}]}
    )

    assert peticion.headers["Authorization"] == "Bearer clave-de-prueba"
    assert json.loads(peticion.content)["max_results"] <= 10
    assert resultados[0].titulo == "O"


async def test_brave_api_tavily_y_exa_leen_su_formato():
    r_brave, p_brave = await _llamar(
        BraveAPI("k1"), {"web": {"results": [{"title": "B", "url": "https://ejemplo.org/b", "description": "d"}]}}
    )
    r_tavily, p_tavily = await _llamar(
        Tavily("k2"), {"results": [{"title": "T", "url": "https://ejemplo.org/t", "content": "c"}]}
    )
    r_exa, p_exa = await _llamar(
        Exa("k3"), {"results": [{"title": "E", "url": "https://ejemplo.org/e", "highlights": ["h1", "h2"]}]}
    )

    assert p_brave.headers["X-Subscription-Token"] == "k1"
    assert json.loads(p_tavily.content)["include_domains"] == ["ejemplo.org"]
    assert p_exa.headers["x-api-key"] == "k3"
    assert json.loads(p_exa.content)["includeDomains"] == ["ejemplo.org"]
    assert [r.titulo for r in r_brave + r_tavily + r_exa] == ["B", "T", "E"]
    assert r_exa[0].fragmento == "h1 … h2"


def test_orden_automatico_y_motores_que_piden_configuracion():
    assert orden_automatico(Configuracion()) == ["duckduckgo", "bing", "brave", "mojeek", "wikipedia"]
    config = Configuracion(searxng_url="http://127.0.0.1:8888", claves={"ollama": "o", "tavily": "t"})
    # Ollama no entra solo: su clave suele estar puesta para otra cosa.
    assert orden_automatico(config)[:2] == ["searxng", "tavily"]
    assert "ollama" not in orden_automatico(config)
    assert crear("ollama", config).nombre == "ollama"
    with pytest.raises(ValueError):
        crear("exa", config)
    with pytest.raises(ValueError):
        crear("google", config)


def test_configuracion_desde_el_entorno():
    config = Configuracion.desde_entorno({"CUYSEARCH_SEARXNG_URL": "http://x:1", "EXA_API_KEY": " e ", "OTRA": "z"})

    assert config.searxng_url == "http://x:1"
    assert dict(config.claves) == {"exa": "e"}

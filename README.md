# CuySearch

Búsqueda y lectura web para agentes de IA, en Python. Cada búsqueda sale desde
la conexión de quien la hace: no hay un servidor central que concentre el
tráfico. Si un motor falla o bloquea, se prueba el siguiente.

- `buscar(consulta, dominios=None, motores=None)` y `leer(url)`, asíncronas.
- Sólo depende de `httpx`. El servicio HTTP es un extra opcional.
- `leer` rechaza localhost, IPs privadas, link-local y demás destinos no
  públicos, también tras cada redirección y después de resolver el DNS.
- Límites de tamaño, de redirecciones y de concurrencia, y caché en memoria.

```bash
pip install "cuysearch @ git+https://github.com/0sw2ld0/CuySearch@v0.1.0"
```

```python
import asyncio
import cuysearch

async def main():
    busqueda = await cuysearch.buscar("httpx timeouts", dominios=["python-httpx.org"])
    for r in busqueda.resultados:
        print(r.titulo, r.url, r.motor)
    pagina = await cuysearch.leer(busqueda.resultados[0].url)
    print(pagina.titulo, pagina.texto[:300])

asyncio.run(main())
```

`buscar` devuelve una `Busqueda` con `resultados` (cada uno con `titulo`, `url`,
`fragmento`, `motor` y `fecha`), el `motor` que respondió y los `avisos` de los
que fallaron. Si ningún motor responde, lanza `ErrorDeBusqueda`. Otras
opciones: `max_resultados` (hasta 20), `excluir` (dominios), `periodo`
(`"dia"`, `"semana"`, `"mes"` o `"año"`) y `noticias`.

`leer` devuelve una `Pagina` con `url` (la final, tras redirecciones),
`titulo`, `texto` y `truncada`. Si no puede, lanza `ErrorDeLectura`.

Para controlar la configuración, crea tu propio `Buscador`:

```python
from cuysearch import Buscador
from cuysearch.motores import Configuracion

buscador = Buscador(["searxng", "duckduckgo"],
                    config=Configuracion(searxng_url="http://127.0.0.1:8888"))
```

## Motores

| Motor | Necesita | Cómo |
| --- | --- | --- |
| `duckduckgo` | nada | versión HTML sin JavaScript |
| `bing` | nada | página de resultados |
| `brave` | nada | página de resultados |
| `mojeek` | nada | página de resultados (índice propio) |
| `wikipedia` | nada | API oficial de MediaWiki |
| `searxng` | URL de tu instancia | su API JSON |
| `ollama` | `OLLAMA_API_KEY` | Ollama Web Search |
| `brave_api` | `BRAVE_API_KEY` | Brave Search API |
| `tavily` | `TAVILY_API_KEY` | Tavily |
| `exa` | `EXA_API_KEY` | Exa |

Con `motores="auto"`, el valor por defecto, se prueban en este orden:

1. `searxng`, si diste su URL (`CUYSEARCH_SEARXNG_URL`);
2. `brave_api`, `tavily` y `exa`, si hay su clave;
3. los cinco gratuitos.

Ollama entra sólo si lo pides por nombre, porque mucha gente tiene
`OLLAMA_API_KEY` puesta para otra cosa. La variable `CUYSEARCH_MOTORES` cambia
el orden de `buscar()`, por ejemplo `CUYSEARCH_MOTORES=ollama,duckduckgo`.

No hay Google: sus condiciones de uso no permiten consultarlo así.

### Buen vecino

CuySearch se identifica con su propio User-Agent, no se hace pasar por un
navegador y nunca intenta resolver un captcha. Cuando un motor limita (HTTP 403
o 429) o pide una comprobación anti-bots, descansa diez minutos y se pasa al
siguiente. Por eso algunos motores gratuitos responden mejor que otros según la
conexión. Si necesitas fiabilidad, usa tu SearXNG o una API con clave.

## Servicio HTTP (opcional)

```bash
pip install "cuysearch[servicio] @ git+https://github.com/0sw2ld0/CuySearch@v0.1.0"
cuysearch            # o: python -m cuysearch.servicio
```

Escucha en `127.0.0.1:8090` y ofrece:

- `GET /healthz`;
- `POST /v1/search`, con `query`, `max_results`, `domains`, `exclude_domains`,
  `time_range` (`day`, `week`, `month` o `year`), `topic` (`general` o `news`)
  e `include_raw_content`;
- `POST /v1/extract`, con `urls` (hasta 20).

Si defines `CUYSEARCH_API_KEY`, las peticiones necesitan la cabecera
`X-CuySearch-Key` o `Authorization: Bearer <clave>`. Con `SEARXNG_BASE_URL`,
el servicio prueba ese SearXNG antes que los motores gratuitos. El resto de
variables está en `.env.example`.

```bash
curl -X POST http://127.0.0.1:8090/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "httpx timeouts", "max_results": 5}'
```

Para tenerlo en el Mac con un SearXNG propio y un icono en la barra de menú,
mira [CuySearch-Manager](https://github.com/0sw2ld0/CuySearch-Manager).

## Desarrollo

```bash
uv venv && uv pip install -e '.[dev,servicio]'
uv run pytest           # sin red: motores y transportes falsos
uv run pytest -m red    # contra internet de verdad
```

## Licencia

MIT; ver `LICENSE`. Los motores están adaptados de
[ddgs](https://github.com/deedy5/ddgs) (MIT). `PROCEDENCIA.md` cuenta qué se
tomó y qué se cambió.

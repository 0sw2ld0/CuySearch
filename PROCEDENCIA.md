# Procedencia

## ddgs

Los motores de `src/cuysearch/motores/` (DuckDuckGo, Bing, Brave, Mojeek y
Wikipedia) y `limpiar_texto` de `src/cuysearch/utiles.py` están adaptados de
[ddgs](https://github.com/deedy5/ddgs), el sucesor de `duckduckgo_search`.

- Licencia: MIT, © 2022 deedy5. El aviso completo está al final de `LICENSE`.
- Revisión consultada: `8e74959141106702645020dcb853c6453b5e5195`
  (24 de octubre de 2026, versión 9.16.1).
- Ficheros de origen: `ddgs/engines/duckduckgo.py`, `bing.py`, `brave.py`,
  `mojeek.py`, `wikipedia.py`, `ddgs/base.py` y `ddgs/utils.py`.

Qué se tomó:

- las URL y los parámetros de cada motor (`q`, `df`, `filters`, `tf`, `s`…);
- dónde está cada resultado en la página (las expresiones XPath, traducidas);
- cómo se desenvuelven los enlaces de Bing (`/ck/a?…&u=a1<base64>`);
- qué enlaces son anuncios y se descartan;
- la limpieza del texto: etiquetas, entidades, Unicode NFC y caracteres de control.

Qué se cambió:

- **Sin `primp` ni `lxml`.** La librería sólo depende de `httpx`. Los
  resultados se leen con un árbol HTML mínimo hecho con `html.parser` de la
  biblioteca estándar (`src/cuysearch/html.py`).
- **Sin hacerse pasar por un navegador.** ddgs usa `primp` para imitar la
  huella TLS y las cabeceras de navegadores reales. CuySearch se identifica
  con un User-Agent propio (`CuySearch/0.1 (+https://github.com/0sw2ld0/CuySearch)`)
  y nunca intenta resolver captchas. Si un motor limita o bloquea, descansa un
  rato y se pasa al siguiente. Por eso algunos motores bloquean más que en ddgs.
- **Asíncrono.** Cada motor es una corrutina sobre un `httpx.AsyncClient`.
- **Wikipedia con una sola petición.** Se usa `list=search` de la API de
  MediaWiki, que ya trae título y fragmento, en vez de `opensearch` más una
  segunda llamada por el resumen.
- **Bloqueos explícitos.** HTTP 403 o 429, la página de «anomalía» de
  DuckDuckGo y los captchas de Bing y Mojeek se convierten en `MotorBloqueado`.
- **Sin Google, Yahoo, Yandex ni los demás motores de ddgs.**

## Dependencias

CuySearch no copia código de sus dependencias; sólo las instala.

| Paquete | Licencia | Para qué |
| --- | --- | --- |
| httpx, httpcore, idna | BSD-3-Clause | cliente HTTP (librería) |
| anyio, h11 | MIT | dependencias de httpx |
| certifi | MPL-2.0 | certificados raíz para httpx |
| typing-extensions | PSF-2.0 | dependencia de anyio |
| fastapi, pydantic, pydantic-core, pydantic-settings, annotated-types, typing-inspection | MIT | servicio HTTP (extra `[servicio]`) |
| starlette, uvicorn, click, python-dotenv | BSD-3-Clause | servicio HTTP (extra `[servicio]`) |

MPL-2.0 (certifi) sólo obliga a publicar los cambios que se hagan a los propios
ficheros de certifi; usarlo sin modificar es compatible con MIT.

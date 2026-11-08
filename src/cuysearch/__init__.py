"""CuySearch: búsqueda y lectura web para agentes, sin servidor intermedio.

    import cuysearch

    busqueda = await cuysearch.buscar("httpx timeout", dominios=["python-httpx.org"])
    pagina = await cuysearch.leer(busqueda.resultados[0].url)

Cada búsqueda sale desde la conexión de quien llama. Si un motor falla o
bloquea, se prueba el siguiente.
"""

from cuysearch.buscador import Buscador, buscar, leer
from cuysearch.security import UnsafeUrlError
from cuysearch.tipos import Busqueda, ErrorDeBusqueda, ErrorDeLectura, Pagina, Resultado

__version__ = "0.1.0"

__all__ = [
    "Buscador",
    "Busqueda",
    "ErrorDeBusqueda",
    "ErrorDeLectura",
    "Pagina",
    "Resultado",
    "UnsafeUrlError",
    "__version__",
    "buscar",
    "leer",
]

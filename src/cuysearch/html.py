"""Árbol HTML mínimo para leer páginas de resultados sin lxml.

Los motores de `ddgs` eligen los resultados con XPath sobre lxml. Aquí basta
con buscar por etiqueta, clase y atributo, así que se construye un árbol
pequeño con `html.parser` de la biblioteca estándar. Tolera el HTML real:
etiquetas sin cerrar, cierres sobrantes y elementos vacíos.
"""

from __future__ import annotations

from collections.abc import Iterator
from html.parser import HTMLParser

_VACIOS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
}
_IGNORADOS = {"script", "style", "noscript", "template", "svg"}
# Una etiqueta de estas cierra la anterior del mismo tipo si sigue abierta.
_CIERRE_IMPLICITO = {"li", "p", "option", "tr", "td", "th", "dt", "dd"}


class Nodo:
    __slots__ = ("etiqueta", "atributos", "hijos", "padre")

    def __init__(self, etiqueta: str, atributos: dict[str, str], padre: Nodo | None = None) -> None:
        self.etiqueta = etiqueta
        self.atributos = atributos
        self.hijos: list[Nodo | str] = []
        self.padre = padre

    def atributo(self, nombre: str) -> str:
        return self.atributos.get(nombre, "")

    @property
    def clases(self) -> set[str]:
        return set(self.atributo("class").split())

    def descendientes(self) -> Iterator[Nodo]:
        pila = [h for h in reversed(self.hijos) if isinstance(h, Nodo)]
        while pila:
            nodo = pila.pop()
            yield nodo
            pila.extend(h for h in reversed(nodo.hijos) if isinstance(h, Nodo))

    def buscar(
        self,
        etiqueta: str | None = None,
        clase: str | None = None,
        *,
        clase_parcial: str | None = None,
        **atributos: str,
    ) -> list[Nodo]:
        """Descendientes que cumplen todo: etiqueta, clase y atributos exactos.

        `clase_parcial` equivale al `contains(@class, ...)` de XPath.
        """
        encontrados = []
        for nodo in self.descendientes():
            if etiqueta and nodo.etiqueta != etiqueta:
                continue
            if clase and clase not in nodo.clases:
                continue
            if clase_parcial and clase_parcial not in nodo.atributo("class"):
                continue
            if any(nodo.atributos.get(k.replace("_", "-")) != v for k, v in atributos.items()):
                continue
            encontrados.append(nodo)
        return encontrados

    def primero(self, etiqueta: str | None = None, clase: str | None = None, **filtros: str) -> Nodo | None:
        for nodo in self.buscar(etiqueta, clase, **filtros):
            return nodo
        return None

    def texto(self) -> str:
        partes: list[str] = []
        pila: list[Nodo | str] = [self]
        while pila:
            actual = pila.pop()
            if isinstance(actual, str):
                partes.append(actual)
            else:
                pila.extend(reversed(actual.hijos))
        return " ".join("".join(partes).split())


class _Constructor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.raiz = Nodo("#documento", {})
        self._pila = [self.raiz]
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORADOS:
            self._ignorando += 1
            return
        if self._ignorando:
            return
        if tag in _CIERRE_IMPLICITO and self._pila[-1].etiqueta == tag:
            self._pila.pop()
        nodo = Nodo(tag, {k: (v or "") for k, v in attrs}, self._pila[-1])
        self._pila[-1].hijos.append(nodo)
        if tag not in _VACIOS:
            self._pila.append(nodo)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORADOS or self._ignorando:
            return
        self._pila[-1].hijos.append(Nodo(tag, {k: (v or "") for k, v in attrs}, self._pila[-1]))

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORADOS:
            self._ignorando = max(0, self._ignorando - 1)
            return
        if self._ignorando or tag in _VACIOS:
            return
        for i in range(len(self._pila) - 1, 0, -1):
            if self._pila[i].etiqueta == tag:
                del self._pila[i:]
                return

    def handle_data(self, data: str) -> None:
        if not self._ignorando:
            # Un espacio entre dos etiquetas también separa palabras.
            self._pila[-1].hijos.append(data if data.strip() else " ")


def analizar(texto: str) -> Nodo:
    constructor = _Constructor()
    constructor.feed(texto)
    constructor.close()
    return constructor.raiz

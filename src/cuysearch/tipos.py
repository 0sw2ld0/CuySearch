"""Tipos públicos de CuySearch: resultados, páginas y errores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Periodo = Literal["dia", "semana", "mes", "año"]


class ErrorDeBusqueda(RuntimeError):
    """Ningún motor pudo responder a la consulta."""


class ErrorDeLectura(RuntimeError):
    """No se pudo descargar o convertir una página."""


@dataclass(frozen=True, slots=True)
class Resultado:
    titulo: str
    url: str
    fragmento: str = ""
    motor: str = ""
    fecha: str | None = None


@dataclass(frozen=True, slots=True)
class Busqueda:
    consulta: str
    resultados: list[Resultado]
    motor: str | None
    avisos: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Pagina:
    url: str
    titulo: str | None
    texto: str
    tipo: str | None = None
    truncada: bool = False


@dataclass(frozen=True, slots=True)
class Consulta:
    """Lo que recibe cada motor; la arma el buscador a partir de `buscar()`."""

    texto: str
    max_resultados: int = 8
    dominios: tuple[str, ...] = ()
    excluir: tuple[str, ...] = ()
    periodo: Periodo | None = None
    noticias: bool = False
    idioma: str | None = None

    def con_filtros_de_sitio(self) -> str:
        """La consulta con `site:` y `-site:`, que entienden casi todos los motores."""
        partes = [self.texto]
        if len(self.dominios) == 1:
            partes.append(f"site:{self.dominios[0]}")
        elif self.dominios:
            partes.append("(" + " OR ".join(f"site:{d}" for d in self.dominios) + ")")
        partes.extend(f"-site:{d}" for d in self.excluir)
        return " ".join(partes)

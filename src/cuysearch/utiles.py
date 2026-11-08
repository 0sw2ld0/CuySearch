"""Pequeñas utilidades de texto y URLs."""

from __future__ import annotations

import re
import unicodedata
from html import unescape
from urllib.parse import urlparse

_ETIQUETAS = re.compile(r"<[^>]*>")


def limpiar_texto(texto: str) -> str:
    """Quita etiquetas, entidades y caracteres de control; junta los espacios.

    Adaptado de `_normalize_text` de ddgs (MIT, ver PROCEDENCIA.md).
    """
    if not texto:
        return ""
    texto = unicodedata.normalize("NFC", unescape(_ETIQUETAS.sub("", texto)))
    texto = "".join(c for c in texto if unicodedata.category(c)[0] != "C" or c in "\t\n ")
    return " ".join(texto.split())


def url_publica(url: str) -> bool:
    """Una URL http(s) con dominio; no comprueba la red (eso lo hace `seguridad`)."""
    try:
        partes = urlparse(url)
    except ValueError:
        return False
    return partes.scheme in ("http", "https") and bool(partes.hostname)


def normalizar_dominio(dominio: str) -> str | None:
    dominio = (dominio or "").strip().lower()
    if "://" in dominio:
        dominio = urlparse(dominio).hostname or ""
    dominio = dominio.removeprefix("www.").strip("./")
    if not dominio or " " in dominio or "/" in dominio:
        return None
    return dominio


def en_dominios(url: str, dominios: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in dominios)

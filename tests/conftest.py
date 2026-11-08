import pytest

from cuysearch.motores import Motor, MotorBloqueado
from cuysearch.tipos import Resultado


class MotorFalso(Motor):
    """Motor sin red: devuelve lo que se le diga, o falla como se le diga."""

    def __init__(self, nombre, resultados=(), error=None):
        super().__init__()
        self.nombre = nombre
        self._resultados = list(resultados)
        self._error = error
        self.llamadas = []

    async def buscar(self, cliente, consulta):
        self.llamadas.append(consulta)
        if self._error is not None:
            raise self._error
        return [Resultado(titulo=t, url=u, fragmento="", motor=self.nombre) for t, u in self._resultados]


@pytest.fixture
def motor_falso():
    return MotorFalso


@pytest.fixture
def bloqueado():
    return MotorBloqueado("limitó la petición (HTTP 429)")

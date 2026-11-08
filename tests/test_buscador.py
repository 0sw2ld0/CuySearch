import pytest

from cuysearch import Buscador, ErrorDeBusqueda
from cuysearch.motores import Configuracion, ErrorDeMotor


async def test_pasa_al_siguiente_si_uno_falla_o_bloquea(motor_falso, bloqueado):
    uno = motor_falso("uno", error=bloqueado)
    dos = motor_falso("dos", error=ErrorDeMotor("no responde"))
    tres = motor_falso("tres", [("T", "https://ejemplo.org/t")])

    busqueda = await Buscador([uno, dos, tres]).buscar("hola mundo")

    assert busqueda.motor == "tres"
    assert [r.titulo for r in busqueda.resultados] == ["T"]
    assert busqueda.avisos == ["uno: limitó la petición (HTTP 429)", "dos: no responde"]


async def test_un_motor_bloqueado_descansa(motor_falso, bloqueado):
    uno = motor_falso("uno", error=bloqueado)
    dos = motor_falso("dos", [("D", "https://ejemplo.org/d")])
    buscador = Buscador([uno, dos], cache_segundos=0)

    await buscador.buscar("primera consulta")
    segunda = await buscador.buscar("segunda consulta")

    assert len(uno.llamadas) == 1
    assert "uno: en pausa tras un bloqueo reciente" in segunda.avisos


async def test_sin_resultados_prueba_el_siguiente_y_si_nadie_tiene_devuelve_vacio(motor_falso):
    vacio = motor_falso("vacio")
    otro = motor_falso("otro")

    busqueda = await Buscador([vacio, otro]).buscar("algo raro")

    assert busqueda.resultados == [] and busqueda.motor is None
    assert len(otro.llamadas) == 1


async def test_si_todos_fallan_lanza_error_con_los_motivos(motor_falso, bloqueado):
    buscador = Buscador([motor_falso("uno", error=bloqueado), motor_falso("dos", error=ErrorDeMotor("caído"))])

    with pytest.raises(ErrorDeBusqueda, match="uno: .*dos: caído"):
        await buscador.buscar("hola")


async def test_un_fallo_inesperado_no_tumba_la_busqueda(motor_falso):
    roto = motor_falso("roto", error=KeyError("x"))
    bueno = motor_falso("bueno", [("B", "https://ejemplo.org/b")])

    busqueda = await Buscador([roto, bueno]).buscar("hola")

    assert busqueda.motor == "bueno"
    assert busqueda.avisos == ["roto: fallo inesperado (KeyError)"]


async def test_filtra_dominios_quita_duplicados_y_respeta_el_maximo(motor_falso):
    motor = motor_falso("m", [
        ("A", "https://docs.ejemplo.org/a"),
        ("A otra vez", "https://docs.ejemplo.org/a/"),
        ("Fuera", "https://otro.org/x"),
        ("B", "https://ejemplo.org/b"),
        ("C", "https://ejemplo.org/c"),
    ])

    busqueda = await Buscador([motor]).buscar("hola", dominios=["https://www.Ejemplo.org"], max_resultados=2)

    assert [r.titulo for r in busqueda.resultados] == ["A", "B"]
    assert motor.llamadas[0].dominios == ("ejemplo.org",)


async def test_guarda_en_cache(motor_falso):
    motor = motor_falso("m", [("A", "https://ejemplo.org/a")])
    buscador = Buscador([motor])

    await buscador.buscar("hola")
    await buscador.buscar("  hola ")

    assert len(motor.llamadas) == 1


async def test_motores_por_llamada(motor_falso):
    fijo = motor_falso("fijo", [("F", "https://ejemplo.org/f")])
    otro = motor_falso("otro", [("O", "https://ejemplo.org/o")])

    busqueda = await Buscador([fijo]).buscar("hola", motores=[otro])

    assert busqueda.motor == "otro" and not fijo.llamadas


@pytest.mark.parametrize("consulta", ["", "x", "y" * 501])
async def test_rechaza_consultas_fuera_de_medida(motor_falso, consulta):
    with pytest.raises(ValueError):
        await Buscador([motor_falso("m")]).buscar(consulta)


async def test_rechaza_periodos_desconocidos(motor_falso):
    with pytest.raises(ValueError):
        await Buscador([motor_falso("m")]).buscar("hola", periodo="siglo")


def test_motores_por_nombre_y_desconocidos():
    assert Buscador("auto", config=Configuracion()).motores == ["duckduckgo", "bing", "brave", "mojeek", "wikipedia"]
    assert Buscador(["wikipedia", "duckduckgo"]).motores == ["wikipedia", "duckduckgo"]
    with pytest.raises(ValueError):
        Buscador(["google"])

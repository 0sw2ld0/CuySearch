"""El nombre se resuelve una sola vez: se conecta a la IP que se comprobó, no a lo que conteste el DNS
después («DNS rebinding»: pública al comprobar, 127.0.0.1 al conectar)."""
import http.server
import socket
import threading

import httpx
import pytest

from cuysearch import ErrorDeLectura
from cuysearch.extractor import PageExtractor

PUBLICA = "93.184.216.34"


@pytest.fixture
def dns_que_cambia(monkeypatch):
    """`*.prueba.invalid` resuelve a una IP pública la primera vez y a 127.0.0.1 las siguientes."""
    real = socket.getaddrinfo
    consultas = {}

    def falso(host, port, *args, **kwargs):
        nombre = host.decode() if isinstance(host, bytes) else str(host)
        if nombre.endswith(".prueba.invalid"):
            n = consultas[nombre] = consultas.get(nombre, 0) + 1
            ip = PUBLICA if n == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", falso)
    return consultas


@pytest.fixture
def transporte_que_anota(monkeypatch):
    """Sin red: anota cada petición tal como sale hacia el transporte."""
    peticiones = []

    def responder(request):
        peticiones.append(request)
        return httpx.Response(200, headers={"content-type": "text/plain"}, text="pública")

    original = PageExtractor._new_client

    def cliente(self):
        nuevo = original(self)
        nuevo._transport = httpx.MockTransport(responder)
        return nuevo

    monkeypatch.setattr(PageExtractor, "_new_client", cliente)
    return peticiones


@pytest.mark.parametrize("esquema", ["http", "https"])
async def test_conecta_a_la_ip_comprobada_y_conserva_el_nombre(dns_que_cambia, transporte_que_anota, esquema):
    pagina = await PageExtractor().extract(f"{esquema}://reenlace.prueba.invalid:8443/panel?x=1")

    (peticion,) = transporte_que_anota
    assert peticion.url.host == PUBLICA  # la IP validada, sin volver a preguntar al DNS
    assert peticion.url.port == 8443 and peticion.url.raw_path == b"/panel?x=1"
    assert peticion.headers["host"] == "reenlace.prueba.invalid:8443"
    if esquema == "https":  # el certificado se comprueba contra el nombre, no contra la IP
        assert peticion.extensions["sni_hostname"] == "reenlace.prueba.invalid"
    assert dns_que_cambia == {"reenlace.prueba.invalid": 1}
    assert pagina.url == f"{esquema}://reenlace.prueba.invalid:8443/panel?x=1"
    assert pagina.texto == "pública"


async def test_cada_redireccion_se_resuelve_y_se_fija_por_su_cuenta(dns_que_cambia, monkeypatch):
    peticiones = []

    def responder(request):
        peticiones.append(request)
        if request.url.path == "/salta":
            return httpx.Response(302, headers={"location": "http://otro.prueba.invalid/fin"})
        return httpx.Response(200, headers={"content-type": "text/plain"}, text="fin")

    original = PageExtractor._new_client

    def cliente(self):
        nuevo = original(self)
        nuevo._transport = httpx.MockTransport(responder)
        return nuevo

    monkeypatch.setattr(PageExtractor, "_new_client", cliente)
    pagina = await PageExtractor().extract("http://uno.prueba.invalid/salta")

    assert [(p.url.host, p.headers["host"]) for p in peticiones] == [
        (PUBLICA, "uno.prueba.invalid"),
        (PUBLICA, "otro.prueba.invalid"),
    ]
    assert pagina.url == "http://otro.prueba.invalid/fin"
    assert dns_que_cambia == {"uno.prueba.invalid": 1, "otro.prueba.invalid": 1}


@pytest.mark.red
async def test_un_dns_que_cambia_no_llega_a_un_servicio_local(dns_que_cambia):
    """De punta a punta con el transporte de verdad. Sale a la red solo para intentar conectar con la
    IP pública de pega (`pytest -m red`). Antes del arreglo se leía el servidor local."""
    visitas = []

    class Interno(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            visitas.append(self.path)
            cuerpo = b"SECRETO-INTERNO"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *args):
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", 0), Interno)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        puerto = servidor.server_address[1]
        try:
            pagina = await PageExtractor(timeout_seconds=3).extract(f"http://reenlace.prueba.invalid:{puerto}/panel")
        except ErrorDeLectura:
            pagina = None
        assert visitas == []
        assert pagina is None or "SECRETO-INTERNO" not in pagina.texto
    finally:
        servidor.shutdown()

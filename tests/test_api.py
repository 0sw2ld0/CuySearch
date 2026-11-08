import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from cuysearch import Buscador  # noqa: E402
from cuysearch.servicio.api import create_app  # noqa: E402
from cuysearch.servicio.config import Settings  # noqa: E402


@pytest.fixture
def cliente(motor_falso):
    motor = motor_falso("falso", [("Fuente de prueba", "https://example.com/")])
    app = create_app(Settings(cuysearch_api_key="secret"), Buscador([motor]))
    return TestClient(app), motor


def test_health_is_public_and_reports_version(cliente) -> None:
    client, _ = cliente

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "X-Request-ID" in response.headers


def test_search_requires_key_and_accepts_both_headers(cliente) -> None:
    client, motor = cliente
    payload = {"query": "cuy search", "domains": ["example.com"], "time_range": "week", "topic": "news"}

    assert client.post("/v1/search", json=payload).status_code == 401
    bearer = client.post("/v1/search", json=payload, headers={"Authorization": "Bearer secret"})
    clave = client.post("/v1/search", json=payload, headers={"X-CuySearch-Key": "secret"})

    assert bearer.status_code == clave.status_code == 200
    datos = bearer.json()
    assert datos["results"][0]["title"] == "Fuente de prueba"
    assert datos["provider"] == "falso"
    consulta = motor.llamadas[0]
    assert (consulta.dominios, consulta.periodo, consulta.noticias) == (("example.com",), "semana", True)


def test_search_returns_502_when_every_engine_fails(motor_falso, bloqueado) -> None:
    app = create_app(Settings(), Buscador([motor_falso("caido", error=bloqueado)]))

    response = TestClient(app).post("/v1/search", json={"query": "hola"})

    assert response.status_code == 502
    assert "caido" in response.json()["detail"]


def test_extract_reports_unsafe_urls_as_failures(motor_falso) -> None:
    app = create_app(Settings(), Buscador([motor_falso("m")]))

    response = TestClient(app).post("/v1/extract", json={"urls": ["http://127.0.0.1:9/"]})

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["failed_results"][0]["url"].startswith("http://127.0.0.1")

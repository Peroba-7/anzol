"""Testes do endpoint de saúde."""

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_saude_retorna_ok():
    """O endpoint /saude deve responder 200 com status 'ok'."""
    resposta = cliente.get("/saude")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}

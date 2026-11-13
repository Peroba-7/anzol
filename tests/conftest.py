"""Configuração comum dos testes.

Bloqueia qualquer acesso à rede durante TODOS os testes, para provar que o
Anzol nunca abre links nem consulta domínios. Só conexões com a própria máquina
(127.0.0.1 / ::1) são liberadas, porque o cliente de testes do FastAPI as usa
internamente (no Windows, o asyncio cria um par de sockets locais).
"""

import socket

import pytest

_LOCAIS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def sem_internet(monkeypatch):
    connect_original = socket.socket.connect

    def connect_vigiado(sock, endereco, *args, **kwargs):
        host = endereco[0] if isinstance(endereco, tuple) else endereco
        if host not in _LOCAIS:
            raise AssertionError(f"Tentativa de acessar a rede: {host!r}")
        return connect_original(sock, endereco, *args, **kwargs)

    def getaddrinfo_bloqueado(host, *args, **kwargs):
        raise AssertionError(f"Tentativa de consultar DNS: {host!r}")

    monkeypatch.setattr(socket.socket, "connect", connect_vigiado)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo_bloqueado)


@pytest.fixture(autouse=True)
def leitor_padrao(monkeypatch):
    """Cada teste começa com o leitor desligado, mesmo que a máquina tenha ANZOL_LEITOR."""
    monkeypatch.delenv("ANZOL_LEITOR", raising=False)
    monkeypatch.delenv("ANZOL_LEITOR_TEMPO_LIMITE", raising=False)

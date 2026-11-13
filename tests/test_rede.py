"""Confere que o bloqueio de rede dos testes (tests/conftest.py) funciona."""

import socket

import pytest


def test_bloqueio_de_rede_funciona():
    with pytest.raises(AssertionError):
        socket.getaddrinfo("bancoexemplo.example", 443)
    with socket.socket() as sock, pytest.raises(AssertionError):
        sock.connect(("192.0.2.10", 443))

"""Lista de marcas protegidas, lida de config/marcas_protegidas.txt."""

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from app.dominios import normalizar_host, separar_dominio

ARQUIVO_MARCAS = Path(__file__).resolve().parents[1] / "config" / "marcas_protegidas.txt"


def carregar_marcas(caminho: Path | str = ARQUIVO_MARCAS) -> tuple[str, ...]:
    """Lê o arquivo de marcas protegidas (um domínio por linha, '#' comenta)."""
    marcas: list[str] = []
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            marcas.append(normalizar_host(linha))
    return tuple(dict.fromkeys(marcas))  # remove repetidas mantendo a ordem


@lru_cache(maxsize=1)
def marcas_padrao() -> tuple[str, ...]:
    """Marcas do arquivo de configuração do projeto (lidas uma vez só)."""
    return carregar_marcas()


def resolver_marcas(marcas: Iterable[str] | None = None) -> tuple[str, ...]:
    """Usa a lista informada ou, se for None, a do arquivo de configuração."""
    if marcas is None:
        return marcas_padrao()
    return tuple(normalizar_host(m) for m in marcas)


def nome_da_marca(marca: str) -> str:
    """Parte do domínio que é o nome da marca: bancoexemplo.example -> bancoexemplo."""
    return separar_dominio(marca)[0]

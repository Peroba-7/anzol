"""Envia os e-mails de exemplo ao Anzol local e mostra o resultado de forma legível.

Uso (com o servidor já rodando):

    python scripts/testar.py                      # todos os arquivos de exemplos/
    python scripts/testar.py exemplos/02-legitimo.eml
    python scripts/testar.py --url http://127.0.0.1:8000/analisar

Usa só a biblioteca padrão do Python. Nenhum conteúdo do e-mail é impresso:
só o nível, o motivo e os sinais devolvidos pela API.
"""

import argparse
import json
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

URL_PADRAO = "http://127.0.0.1:8000/analisar"
PASTA_EXEMPLOS = Path(__file__).resolve().parents[1] / "exemplos"
LARGURA = 78

# O que cada exemplo da pasta exemplos/ quer mostrar.
DESCRICOES = {
    "01-golpe-obvio.eml": "Golpe óbvio (o da seção 3 da Apostila, com link enganoso).",
    "02-legitimo.eml": "E-mail legítimo do banco fictício.",
    "03-golpe-bem-feito.eml": (
        "Golpe “bem feito”: domínio próprio, SPF/DKIM/DMARC corretos e nenhum "
        "link enganoso. Mostra a LIMITAÇÃO atual: só as regras não o pegam."
    ),
    "04-lista-de-discussao.eml": (
        "E-mail legítimo de lista de discussão. Mostra um FALSO POSITIVO: a lista "
        "altera a mensagem e o DKIM/DMARC falham."
    ),
}


def enviar(caminho: Path, url: str) -> tuple[int, dict]:
    """Envia o arquivo à API e devolve (código HTTP, resposta em JSON)."""
    requisicao = urllib.request.Request(
        url,
        data=caminho.read_bytes(),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=30) as resposta:
            return resposta.status, json.load(resposta)
    except urllib.error.HTTPError as erro:
        try:
            return erro.code, json.load(erro)
        except ValueError:
            return erro.code, {"detail": erro.reason}


def recuar(texto: str, prefixo: str) -> str:
    """Quebra o texto em linhas com recuo, para ficar fácil de ler."""
    return textwrap.fill(
        texto, width=LARGURA, initial_indent=prefixo, subsequent_indent=" " * len(prefixo)
    )


def mostrar(caminho: Path, codigo: int, dados: dict) -> None:
    print("=" * LARGURA)
    print(f"Arquivo: {caminho.name}")
    if caminho.name in DESCRICOES:
        print(recuar(DESCRICOES[caminho.name], "O que é: "))
    print("-" * LARGURA)

    if codigo != 200:
        print(f"ERRO {codigo}: {dados.get('detail', 'resposta inesperada')}")
        return

    print(f"NÍVEL DE RISCO: {dados['nivel']}")
    nivel_leitor = dados.get("nivel_leitor") or "sem sugestão"
    print(
        f"  (regras: {dados.get('nivel_regras', dados['nivel'])}; "
        f"leitor {dados.get('leitor_usado', 'desligado')}: {nivel_leitor})"
    )
    if dados.get("aviso_leitor"):
        print(recuar(dados["aviso_leitor"], "Atenção: "))
    print(recuar(dados["motivo"], "Motivo: "))
    sinais = dados["sinais"]
    if not sinais:
        print("Sinais: nenhum.")
    else:
        print(f"Sinais ({len(sinais)}):")
        for sinal in sinais:
            vezes = f", {sinal['ocorrencias']}x" if sinal["ocorrencias"] > 1 else ""
            print(f"  [{sinal['peso']}{vezes}] {sinal['nome']}")
            print(recuar(sinal["descricao"], "      "))
    if dados.get("parecer"):
        print(recuar(dados["parecer"], "Parecer: "))
    print(recuar(dados["aviso"], "Aviso: "))


def main() -> int:
    # Imprime sempre em UTF-8, para os acentos saírem certos no Windows.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Testa o Anzol com e-mails de exemplo.")
    parser.add_argument("arquivos", nargs="*", type=Path, help="arquivos .eml (padrão: exemplos/)")
    parser.add_argument("--url", default=URL_PADRAO, help=f"endereço da API (padrão: {URL_PADRAO})")
    args = parser.parse_args()

    arquivos = args.arquivos or sorted(PASTA_EXEMPLOS.glob("*.eml"))
    if not arquivos:
        print("Nenhum arquivo .eml encontrado.")
        return 1

    for caminho in arquivos:
        try:
            codigo, dados = enviar(caminho, args.url)
        except FileNotFoundError:
            print(f"Arquivo não encontrado: {caminho}")
            return 1
        except urllib.error.URLError:
            print(
                f"Não consegui falar com o Anzol em {args.url}.\n"
                "O servidor está rodando? Em outro terminal, rode:\n"
                "    .venv\\Scripts\\activate\n"
                "    uvicorn app.main:app"
            )
            return 1
        mostrar(caminho, codigo, dados)
    print("=" * LARGURA)
    return 0


if __name__ == "__main__":
    sys.exit(main())

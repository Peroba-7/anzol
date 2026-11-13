"""Ponto de entrada da API Anzol.

Privacidade (LGPD): o conteúdo do e-mail enviado para /analisar nunca é guardado
nem escrito em log. Os logs registram só dados técnicos (tamanho, nível, número
de sinais e tipo de erro), nunca o texto, os endereços ou os domínios do e-mail.
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.analise import EmailInvalido, analisar_email

logger = logging.getLogger("anzol")

# Tamanho máximo do e-mail bruto aceito em /analisar (1 MB).
TAMANHO_MAXIMO_BYTES = 1_000_000

# Tipos de conteúdo aceitos: texto puro ou o formato padrão de e-mail (.eml).
TIPOS_ACEITOS = frozenset({"text/plain", "message/rfc822"})

AVISO = (
    "Este resultado foi gerado automaticamente por regras e pode errar. Ele não "
    "substitui o julgamento de uma pessoa: na dúvida, não clique em links, não "
    "envie dados e confirme pelo canal oficial da empresa."
)

app = FastAPI(
    title="Anzol",
    description=(
        "API que analisa e-mails e URLs suspeitos de phishing e devolve "
        "nível de risco, sinais encontrados e um parecer em português."
    ),
    version="0.2.0",
)


class SinalSaida(BaseModel):
    nome: str
    descricao: str
    peso: str
    ocorrencias: int


class RespostaAnalise(BaseModel):
    nivel: str
    motivo: str
    sinais: list[SinalSaida]
    aviso: str


@app.get("/saude", summary="Verifica se a API está no ar")
def saude() -> dict[str, str]:
    """Retorna um status simples indicando que a API está funcionando."""
    return {"status": "ok"}


async def _ler_corpo_limitado(request: Request) -> bytes:
    """Lê o corpo da requisição em pedaços e para assim que passar do limite.

    Assim um envio gigante é recusado sem ser carregado inteiro na memória.
    """
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > TAMANHO_MAXIMO_BYTES:
        raise HTTPException(413, _mensagem_tamanho())

    pedacos: list[bytes] = []
    total = 0
    async for pedaco in request.stream():
        total += len(pedaco)
        if total > TAMANHO_MAXIMO_BYTES:
            raise HTTPException(413, _mensagem_tamanho())
        pedacos.append(pedaco)
    return b"".join(pedacos)


def _mensagem_tamanho() -> str:
    return f"O e-mail passa do tamanho máximo de {TAMANHO_MAXIMO_BYTES // 1_000_000} MB."


@app.post(
    "/analisar",
    summary="Analisa um e-mail suspeito de phishing",
    response_model=RespostaAnalise,
    responses={
        413: {"description": "E-mail maior que o limite"},
        415: {"description": "Tipo de conteúdo não aceito"},
        422: {"description": "Entrada vazia ou que não parece um e-mail"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "description": "O e-mail bruto, com cabeçalhos e corpo (“Mostrar original”).",
            "content": {"text/plain": {"schema": {"type": "string"}}},
        }
    },
)
async def analisar(request: Request) -> RespostaAnalise:
    """Recebe o e-mail bruto como texto e devolve nível de risco e sinais.

    A análise é só do texto: nenhum link é aberto e nada é consultado na internet.
    """
    tipo = request.headers.get("content-type", "text/plain").split(";")[0].strip().lower()
    if tipo not in TIPOS_ACEITOS:
        raise HTTPException(
            415, "Envie o e-mail bruto como texto (Content-Type: text/plain ou message/rfc822)."
        )

    corpo = await _ler_corpo_limitado(request)
    try:
        texto = corpo.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(422, "O e-mail precisa estar em UTF-8.") from None
    if not texto.strip():
        raise HTTPException(422, "O e-mail está vazio.")
    if "\x00" in texto:
        raise HTTPException(422, "O e-mail contém caracteres inválidos.")

    try:
        avaliacao = await run_in_threadpool(analisar_email, texto)
    except EmailInvalido as erro:
        raise HTTPException(422, str(erro)) from None
    except Exception as erro:  # noqa: BLE001
        # Nunca registra a mensagem do erro: ela poderia conter trechos do e-mail.
        logger.error("Falha inesperada na análise (%s).", type(erro).__name__)
        raise HTTPException(500, "Erro interno ao analisar o e-mail.") from None

    logger.info(
        "Análise concluída: %d bytes, nível %s, %d sinal(is).",
        len(corpo),
        avaliacao.nivel,
        len(avaliacao.sinais),
    )
    return RespostaAnalise(
        nivel=avaliacao.nivel.value,
        motivo=avaliacao.motivo,
        sinais=[
            SinalSaida(
                nome=s.nome, descricao=s.descricao, peso=s.peso.rotulo, ocorrencias=s.ocorrencias
            )
            for s in avaliacao.sinais
        ],
        aviso=AVISO,
    )

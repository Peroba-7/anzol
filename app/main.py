"""Ponto de entrada da API Anzol.

Nesta etapa existe apenas o endpoint de saúde, usado para verificar
se o serviço está no ar. A lógica de análise de phishing virá depois.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Anzol",
    description=(
        "API que analisa e-mails e URLs suspeitos de phishing e devolve "
        "nível de risco, sinais encontrados e um parecer em português."
    ),
    version="0.1.0",
)


@app.get("/saude", summary="Verifica se a API está no ar")
def saude() -> dict[str, str]:
    """Retorna um status simples indicando que a API está funcionando."""
    return {"status": "ok"}

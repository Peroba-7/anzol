# Anzol 🎣

> 🚧 **Projeto em construção.**

O **Anzol** é uma API feita em [FastAPI](https://fastapi.tiangolo.com/) para analisar
e-mails e URLs suspeitos de *phishing*. Para cada análise, a API vai devolver:

- **nível de risco**: BAIXO, MÉDIO, ALTO ou CRÍTICO;
- **sinais encontrados**: os indícios que levaram à classificação;
- **parecer**: uma explicação em português do Brasil.

## Como rodar localmente

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Depois acesse <http://127.0.0.1:8000/saude> ou a documentação em <http://127.0.0.1:8000/docs>.

## Testes e qualidade

```bash
pytest
ruff check .
```

## Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).

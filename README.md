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

## Limitações conhecidas

- **Authentication-Results falso.** O Anzol só usa o `Authentication-Results`
  mais acima, que é o do servidor que recebeu a mensagem; os de baixo são
  ignorados, porque um golpista pode escrevê-los dentro do e-mail. Mesmo o de
  cima só é confiável se o e-mail foi copiado direto da caixa postal: quem
  monta o e-mail à mão pode colocar um cabeçalho falso no topo. Por isso um
  `pass` nunca reduz o risco nem apaga outros sinais.
- **Sem Authentication-Results, sem sinal de autenticação.** E-mails colados à
  mão podem não ter esse cabeçalho, e a ausência não é punida.
- **From duplicado.** Se houver mais de um `From`, vale o primeiro. (Reply-To e
  Return-Path repetidos são todos conferidos.)
- **Nada é consultado na internet.** O Anzol não abre links nem consulta DNS;
  a análise é só do texto.

## Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).

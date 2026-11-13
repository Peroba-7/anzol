"""Descobre o domínio principal de um endereço, sem acessar a internet.

O "domínio principal" é a parte que uma empresa registra, por exemplo:

    www.meubanco.com.br      -> meubanco.com.br
    app.contas.meubanco.com  -> meubanco.com

Para saber onde termina o sufixo público (".com.br", ".co.uk", ".github.io"...)
usamos uma lista curta embutida aqui mesmo, baseada na Public Suffix List
(https://publicsuffix.org). Ela cobre os sufixos mais comuns no Brasil e no
mundo. Quando o sufixo não está na lista, assumimos que ele tem um só nível
(".com", ".xyz", ".net"...), o que é correto para a grande maioria dos casos.
"""

import ipaddress

# Sufixos públicos com mais de um nível. Sufixos de um nível só (.com, .br,
# .xyz...) não precisam estar aqui: são o comportamento padrão.
# fmt: off
SUFIXOS_PUBLICOS: frozenset[str] = frozenset({
    # Brasil (registro.br)
    "adm.br", "adv.br", "agr.br", "app.br", "arq.br", "art.br", "ato.br",
    "b.br", "bio.br", "blog.br", "bmd.br", "cim.br", "cng.br", "cnt.br",
    "com.br", "coop.br", "dev.br", "ecn.br", "eco.br", "edu.br", "emp.br",
    "eng.br", "esp.br", "etc.br", "eti.br", "far.br", "flog.br", "fm.br",
    "fot.br", "fst.br", "g12.br", "ggf.br", "gov.br", "imb.br", "ind.br",
    "inf.br", "jor.br", "jus.br", "leg.br", "lel.br", "log.br", "mat.br",
    "med.br", "mil.br", "mp.br", "mus.br", "net.br", "nom.br", "not.br",
    "ntr.br", "odo.br", "org.br", "ppg.br", "pro.br", "psc.br", "psi.br",
    "qsl.br", "rec.br", "seg.br", "slg.br", "srv.br", "tec.br", "teo.br",
    "tmp.br", "trd.br", "tur.br", "tv.br", "vet.br", "vlog.br", "wiki.br",
    "zlg.br",
    # Outros países frequentes
    "com.ar", "gob.ar", "net.ar", "org.ar",
    "com.au", "net.au", "org.au", "gov.au", "edu.au",
    "com.cn", "net.cn", "org.cn", "gov.cn",
    "co.in", "net.in", "org.in", "gov.in",
    "co.jp", "ne.jp", "or.jp", "go.jp", "ac.jp",
    "com.mx", "gob.mx", "org.mx",
    "com.pt", "gov.pt", "org.pt",
    "co.uk", "org.uk", "gov.uk", "ac.uk", "me.uk", "ltd.uk", "plc.uk",
    "co.za", "gov.za", "org.za",
    "com.co", "gov.co", "com.pe", "gob.pe", "com.uy", "gub.uy",
    "com.py", "gov.py", "gob.cl", "com.es", "org.es", "gob.es",
    # Serviços de hospedagem onde cada cliente tem o seu subdomínio:
    # fulano.github.io e golpista.github.io têm donos DIFERENTES.
    "github.io", "gitlab.io", "blogspot.com", "herokuapp.com",
    "netlify.app", "vercel.app", "pages.dev", "workers.dev", "web.app",
    "firebaseapp.com", "azurewebsites.net", "cloudfront.net",
    "appspot.com", "wixsite.com", "weebly.com", "glitch.me",
    "ngrok.io", "ngrok-free.app", "s3.amazonaws.com",
})
# fmt: on

# Maior quantidade de níveis entre os sufixos da lista (ex.: s3.amazonaws.com = 3).
_MAX_NIVEIS_SUFIXO = max(sufixo.count(".") + 1 for sufixo in SUFIXOS_PUBLICOS)


def normalizar_host(host: str) -> str:
    """Deixa o host em minúsculas, sem ponto final e em ASCII (punycode)."""
    host = host.strip().strip(".").lower()
    try:
        # Domínios com acento (IDN) viram "xn--..." para comparar com o href.
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    return host


def eh_ip(host: str) -> bool:
    """Indica se o host é um endereço IP (v4 ou v6) em vez de um nome."""
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def dominio_principal(host: str) -> str:
    """Devolve o domínio registrável de um host (ex.: www.a.com.br -> a.com.br).

    Para endereços IP, devolve o próprio IP.
    """
    host = normalizar_host(host)
    if eh_ip(host):
        return host

    partes = host.split(".")
    # Procura o maior sufixo público conhecido que termina o host.
    for niveis in range(min(_MAX_NIVEIS_SUFIXO, len(partes) - 1), 1, -1):
        if ".".join(partes[-niveis:]) in SUFIXOS_PUBLICOS:
            return ".".join(partes[-(niveis + 1) :])
    # Padrão: sufixo de um nível (.com, .xyz...) + o nome antes dele.
    return ".".join(partes[-2:])

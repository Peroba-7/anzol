"""E-mails de exemplo compartilhados pelos testes. Tudo FICTÍCIO (.example)."""

# E-mail da seção 3 da Apostila Anzol (Aula 2), copiado sem alterações.
EMAIL_APOSTILA = """\
Return-Path: <contato@banc0exemplo-seguro.example>
Received: from mail.banc0exemplo-seguro.example (203.0.113.45)
    by mx.provedor.example (192.0.2.10); Fri, 13 Nov 2026 08:41:02 -0300
Authentication-Results: mx.provedor.example;
    spf=pass smtp.mailfrom=banc0exemplo-seguro.example;
    dkim=none;
    dmarc=fail header.from=bancoexemplo.example
From: "Banco Exemplo" <atendimento@bancoexemplo.example>
Reply-To: <suporte@banc0exemplo-seguro.example>
To: cliente@provedor.example
Subject: URGENTE: sua conta sera bloqueada em 2 horas
Date: Fri, 13 Nov 2026 08:40:51 -0300
Message-ID: <a1b2c3@banc0exemplo-seguro.example>
Content-Type: text/html; charset=utf-8

<p>Sua conta sera bloqueada.</p>
"""

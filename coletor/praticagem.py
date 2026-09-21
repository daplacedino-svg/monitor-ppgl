# -*- coding: utf-8 -*-
"""Manobras previstas pela Praticagem de Paranaguá (SINPRAPAR).

A página é uma tabela simples, uma linha por manobra. O campo "Manobra" traz o
código e o local, por exemplo:
    EA: P2EXT QB        entrada e atracação no berço 141, qualquer bordo
    AT: F84/P2INT BE    atracação vinda do fundeio F84 no berço 142, boreste
    DS: P2INT BE        desatracação do berço 142
    DF: P2EXT QB        desatracação e fundeio
    EF: / SL:           entrada para fundeio / saída (não envolvem berço)
"""
import html as H
import re
from datetime import datetime, timedelta

import requests

import config
from coletor.appa import ErroColeta, FUSO_BR

# Código da manobra -> (tipo, rótulo)
MANOBRAS = {
    "EA": ("atracacao", "Atracação"),
    "AT": ("atracacao", "Atracação"),
    "DS": ("desatracacao", "Desatracação"),
    "DF": ("desatracacao", "Desatracação"),
    "EF": ("fundeio", "Entrada para fundeio"),
    "SL": ("saida", "Saída"),
}


def baixar_pagina():
    ultimo_erro = None
    for tentativa in range(1, config.TENTATIVAS + 1):
        try:
            r = requests.get(config.URL_PRATICAGEM, headers=config.HEADERS, timeout=config.TIMEOUT_S)
            r.raise_for_status()
            html = r.content.decode("utf-8", errors="replace")
            if "Manobras Previstas" not in html:
                raise ErroColeta("Página da praticagem em formato inesperado")
            return html
        except (requests.RequestException, ErroColeta) as e:
            ultimo_erro = e
            if tentativa < config.TENTATIVAS:
                import time
                time.sleep(config.ESPERA_ENTRE_TENTATIVAS_S)
    raise ErroColeta(f"Praticagem indisponível após {config.TENTATIVAS} tentativas: {ultimo_erro}")


def _texto(celula):
    return H.unescape(" ".join(re.sub(r"<[^>]+>", " ", celula).split()))


def _quando(data_ddmm, hora, referencia):
    """A página não traz o ano; usa o mais próximo da data de referência."""
    m = re.match(r"(\d{2})/(\d{2})", data_ddmm or "")
    hm = re.match(r"(\d{1,2}):(\d{2})", hora or "")
    if not m:
        return None
    dia, mes = int(m.group(1)), int(m.group(2))
    hh, mm = (int(hm.group(1)), int(hm.group(2))) if hm else (0, 0)
    candidatos = []
    for ano in (referencia.year - 1, referencia.year, referencia.year + 1):
        try:
            candidatos.append(datetime(ano, mes, dia, hh, mm, tzinfo=FUSO_BR))
        except ValueError:
            pass  # 29/02 em ano não bissexto
    if not candidatos:
        return None
    return min(candidatos, key=lambda d: abs(d - referencia)).isoformat()


def _berco(local):
    """'F84/P2INT BE' -> (142, 'BE')"""
    for sigla, berco in config.BERCOS_PRATICAGEM.items():
        if re.search(rf"\b{sigla}\b", local or "", re.I):
            bordo = re.search(rf"\b{sigla}\b\s*(QB|BB|BE)\b", local, re.I)
            return berco, (bordo.group(1).upper() if bordo else None)
    return None, None


def interpretar(html):
    """Devolve (atualizacao, lista de manobras)."""
    m = re.search(r"Atualiza[^:]*:\s*</b>\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2})", html)
    agora = datetime.now(FUSO_BR)
    atualizacao = None
    if m:
        atualizacao = datetime.strptime(m.group(1), "%d/%m/%Y %H:%M").replace(tzinfo=FUSO_BR).isoformat()

    manobras = []
    for linha in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        c = [_texto(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.S)]
        if len(c) < 18:
            continue
        codigo, _, local = c[3].partition(":")
        codigo = codigo.strip().upper()
        tipo, rotulo = MANOBRAS.get(codigo, ("outra", codigo))
        berco, bordo = _berco(local)
        quando = _quando(c[0], c[1], agora)
        manobras.append({
            "quando": quando,
            "navio": c[2],
            "imo": c[10],
            "codigo": codigo,
            "tipo": tipo,
            "rotulo": rotulo,
            "local": local.strip(),
            "berco": berco,
            "bordo": bordo,
            "situacao": c[17],
            "agencia": c[13],
            "calado": c[7],
        })
    if not manobras:
        raise ErroColeta("Nenhuma manobra encontrada na página da praticagem")
    return atualizacao, manobras


def coletar():
    return interpretar(baixar_pagina())


def relevantes(manobras, navios_monitorados):
    """Manobras dos berços 141/142 ou de navios que o monitor acompanha.

    O cruzamento é pelo IMO; o nome é usado só quando o IMO não bate.
    `navios_monitorados` são dicionários com programacao, imo e embarcacao.
    """
    por_imo = {str(n["imo"]).strip(): n for n in navios_monitorados if n.get("imo")}
    por_nome = {_chave_nome(n["embarcacao"]): n for n in navios_monitorados if n.get("embarcacao")}
    saida = []
    for man in manobras:
        if man["tipo"] not in config.TIPOS_MANOBRA:
            continue
        navio = por_imo.get((man["imo"] or "").strip())
        casou = "imo" if navio else None
        if navio is None:
            navio = por_nome.get(_chave_nome(man["navio"]))
            casou = "nome" if navio else None
        if navio is None and not man["berco"]:
            continue
        saida.append(dict(man, programacao=navio["programacao"] if navio else None, casou_por=casou))
    return saida


def _chave_nome(nome):
    return re.sub(r"[^A-Z0-9]", "", (nome or "").upper())

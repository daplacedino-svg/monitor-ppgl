# -*- coding: utf-8 -*-
"""Download e interpretação do Line-Up da APPA.

A página traz uma tabela por seção (ATRACADOS, PROGRAMADOS, AO LARGO...).
Navios com mais de um operador/mercadoria ocupam várias linhas: as colunas
do navio (Programação, Berço, Embarcação...) vêm com rowspan e as colunas da
carga (Operador, Mercadoria, Previsto...) repetem-se em cada linha.
"""
import logging
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import requests

import config

FUSO_BR = timezone(timedelta(hours=-3))  # Brasília, sem horário de verão desde 2019
log = logging.getLogger("monitor")


class ErroColeta(Exception):
    pass


# --------------------------------------------------------------------------- download

def baixar_pagina():
    ultimo_erro = None
    for tentativa in range(1, config.TENTATIVAS + 1):
        try:
            r = requests.get(config.URL_LINEUP, headers=config.HEADERS, timeout=config.TIMEOUT_S)
            r.raise_for_status()
            html = r.content.decode("utf-8", errors="replace")
            if "ATRACADOS" not in html:
                raise ErroColeta("Página sem a seção ATRACADOS (possível bloqueio ou mudança no portal)")
            return html
        except (requests.RequestException, ErroColeta) as e:
            ultimo_erro = e
            if tentativa < config.TENTATIVAS:
                time.sleep(config.ESPERA_ENTRE_TENTATIVAS_S)
    raise ErroColeta(f"Falha após {config.TENTATIVAS} tentativas: {ultimo_erro}")


# --------------------------------------------------------------------------- HTML -> tabelas

class _LeitorTabelas(HTMLParser):
    """Extrai tabelas como listas de linhas; cada célula = (texto, rowspan, colspan)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tabelas = []
        self._pilha = []
        self._celula = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._pilha.append([])
        elif tag == "tr" and self._pilha:
            self._pilha[-1].append([])
        elif tag in ("td", "th") and self._pilha:
            a = dict(attrs)
            self._celula = {"txt": [], "rs": _int(a.get("rowspan"), 1), "cs": _int(a.get("colspan"), 1)}
        elif tag == "br" and self._celula is not None:
            self._celula["txt"].append(" ")

    def handle_endtag(self, tag):
        if tag == "table" and self._pilha:
            self.tabelas.append(self._pilha.pop())
        elif tag in ("td", "th") and self._celula is not None:
            if self._pilha and self._pilha[-1]:
                texto = " ".join("".join(self._celula["txt"]).split())
                self._pilha[-1][-1].append((texto, self._celula["rs"], self._celula["cs"]))
            self._celula = None

    def handle_data(self, data):
        if self._celula is not None:
            self._celula["txt"].append(data)


def _expandir_grade(linhas):
    """Resolve rowspan/colspan, devolvendo uma grade retangular de textos."""
    grade, pendentes = [], {}  # pendentes[col] = [texto, linhas_restantes]
    for linha in linhas:
        saida, col, it = [], 0, iter(linha)
        celula = next(it, None)
        while celula is not None or any(c >= col for c in pendentes):
            if col in pendentes:
                texto, resta = pendentes[col]
                saida.append(texto)
                if resta <= 1:
                    del pendentes[col]
                else:
                    pendentes[col][1] -= 1
                col += 1
                continue
            if celula is None:
                break
            texto, rs, cs = celula
            for _ in range(cs):
                saida.append(texto)
                if rs > 1:
                    pendentes[col] = [texto, rs - 1]
                col += 1
            celula = next(it, None)
        grade.append(saida)
    return grade


# --------------------------------------------------------------------------- normalização

def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _chave(s):
    return " ".join(_sem_acento(s).lower().split())


SECOES = {
    "atracados": ("atracado", False),
    "programados": ("programado", False),
    "ao largo para reatracacao": ("ao_largo", True),
    "ao largo": ("ao_largo", False),
    "esperados": ("esperado", False),
    "despachados": ("despachado", False),
}

COLUNAS = {
    "programacao": "programacao", "duv": "duv", "berco": "berco", "embarcacao": "embarcacao",
    "imo": "imo", "loa": "loa", "dwt": "dwt", "bordo": "bordo", "sentido": "sentido",
    "agencia": "agencia", "operador": "operador", "mercadoria": "mercadoria",
    "atracacao": "atracacao", "chegada": "chegada", "desatracacao": "desatracacao",
    "janela operacional": "janela", "prancha (t/dia)": "prancha", "tons/dia": "tons_dia",
    "previsto": "previsto", "realizado": "realizado", "saldo operador": "saldo_operador",
    "saldo": "saldo_operador", "saldo total": "saldo_total", "eta": "eta", "etb": "etb",
    "cal. cheg.": "calado_chegada", "cal. saida": "calado_saida",
}

# Colunas que pertencem ao navio (as demais pertencem a cada carga/operador)
CAMPOS_NAVIO = {"programacao", "marca_programacao", "duv", "berco", "embarcacao", "imo", "loa", "dwt",
                "calado_chegada", "calado_saida", "saldo_total"}
CAMPOS_DATA = {"atracacao", "chegada", "desatracacao", "eta", "etb"}
CAMPOS_NUM = {"loa", "dwt", "prancha", "calado_chegada", "calado_saida"}
CAMPOS_QTD = {"tons_dia", "previsto", "realizado", "saldo_operador", "saldo_total"}


def _int(v, padrao=None):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return padrao


def numero_br(txt):
    """'34.492,00' -> 34492.0 ; '500 Movs.' -> 500.0 ; '' -> None"""
    if not txt:
        return None
    parte = txt.split(" ")[0]
    if "," in parte:
        parte = parte.replace(".", "").replace(",", ".")
    try:
        return float(parte)
    except ValueError:
        return None


def unidade(txt):
    t = (txt or "").lower()
    if "mov" in t:
        return "movs"
    if "ton" in t:
        return "t"
    return None


def data_br(txt):
    """'18/09/2026 16:40' -> '2026-09-18T16:40:00-03:00'"""
    if not txt:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(txt.strip(), fmt).replace(tzinfo=FUSO_BR).isoformat()
        except ValueError:
            pass
    return None


def _converter_linha(bruta):
    reg = {}
    for campo, txt in bruta.items():
        if campo in CAMPOS_DATA:
            reg[campo] = data_br(txt)
        elif campo in CAMPOS_NUM:
            reg[campo] = numero_br(txt)
        elif campo in CAMPOS_QTD:
            reg[campo] = numero_br(txt)
            if unidade(txt):
                reg["unidade"] = unidade(txt)
        elif campo == "janela":
            partes = [p.strip() for p in re.split(r"\s+-\s+", txt or "") if p.strip()]
            reg["janela_inicio"] = data_br(partes[0]) if partes else None
            reg["janela_fim"] = data_br(partes[1]) if len(partes) > 1 else None
        elif campo == "programacao":
            # Pode vir com sufixo, ex.: "80569 - REP" (reprogramação, caso de reatracação)
            m = re.match(r"\s*(\d+)\s*(?:-\s*(.+))?$", txt or "")
            reg["programacao"] = int(m.group(1)) if m else None
            reg["marca_programacao"] = (m.group(2).strip().upper() if m and m.group(2) else None)
        elif campo == "berco":
            reg[campo] = _int(txt)
        else:
            reg[campo] = txt or None
    return reg


# --------------------------------------------------------------------------- página -> navios

def interpretar(html):
    """Devolve (emissao_portal, lista de navios de todas as seções/berços)."""
    leitor = _LeitorTabelas()
    leitor.feed(html)

    m = re.search(r"Emiss[ãa]o:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2})", html)
    emissao = data_br(m.group(1)) if m else None

    navios = []
    for tabela in leitor.tabelas:
        grade = _expandir_grade(tabela)
        if len(grade) < 2 or not grade[0]:
            continue
        secao = SECOES.get(_chave(grade[0][0]))
        if not secao:
            continue
        categoria, reatracacao = secao
        cabecalho = [COLUNAS.get(_chave(h), _chave(h).replace(" ", "_")) for h in grade[1]]

        linhas, descartadas = [], 0
        for valores in grade[2:]:
            bruta = {c: v for c, v in zip(cabecalho, valores) if c}
            reg = _converter_linha(bruta)
            if reg.get("programacao"):
                linhas.append(reg)
            elif any(v for v in bruta.values()):
                descartadas += 1
        if descartadas:
            log.warning("Seção %s: %d linha(s) sem número de programação foram ignoradas",
                        categoria, descartadas)
        navios.extend(_agrupar(linhas, categoria, reatracacao))
    return emissao, navios


def _agrupar(linhas, categoria, reatracacao):
    por_prog = {}
    for reg in linhas:
        por_prog.setdefault(reg["programacao"], []).append(reg)

    navios = []
    for prog, regs in por_prog.items():
        navio = {k: regs[0].get(k) for k in CAMPOS_NAVIO if k in regs[0]}
        navio["categoria"] = categoria
        navio["reatracacao"] = reatracacao
        cargas = [{k: v for k, v in r.items() if k not in CAMPOS_NAVIO} for r in regs]
        navio["cargas"] = cargas

        def menor(campo):
            vals = [c.get(campo) for c in cargas if c.get(campo)]
            return min(vals) if vals else None

        def maior(campo):
            vals = [c.get(campo) for c in cargas if c.get(campo)]
            return max(vals) if vals else None

        for campo in ("chegada", "atracacao", "eta", "etb", "janela_inicio"):
            navio[campo] = menor(campo)
        for campo in ("desatracacao", "janela_fim"):
            navio[campo] = maior(campo)

        navio["mercadoria"] = " + ".join(dict.fromkeys(c["mercadoria"] for c in cargas if c.get("mercadoria")))
        navio["operadores"] = list(dict.fromkeys(c["operador"] for c in cargas if c.get("operador")))
        navio["agencia"] = next((c["agencia"] for c in cargas if c.get("agencia")), None)
        navio["sentido"] = "/".join(dict.fromkeys(c["sentido"] for c in cargas if c.get("sentido")))
        unidades = {c.get("unidade") for c in cargas if c.get("unidade")}
        navio["unidade"] = unidades.pop() if len(unidades) == 1 else None
        if navio["unidade"]:
            for campo in ("previsto", "realizado"):
                vals = [c[campo] for c in cargas if c.get(campo) is not None]
                navio[campo] = round(sum(vals), 3) if vals else None
            # Com vários operadores o portal repete o "Realizado" do navio em cada linha;
            # o Saldo Total é consistente, então o realizado sai dele.
            if navio.get("previsto") is not None and navio.get("saldo_total") is not None:
                navio["realizado"] = round(navio["previsto"] - navio["saldo_total"], 3)
        navios.append(navio)
    return navios

# -*- coding: utf-8 -*-
"""Configurações do Monitor de Navios - PPGL."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# Portal da APPA (mesma página usada no bd_LineUP4.1.py - contém todas as seções)
URL_LINEUP = "https://www.appaweb.appa.pr.gov.br/appaweb/pesquisa.aspx?WCI=relLineUpRetroativo"
HEADERS = {"User-Agent": "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0; Trident/4.0)"}
TIMEOUT_S = 30
TENTATIVAS = 3
ESPERA_ENTRE_TENTATIVAS_S = 30

# Berços monitorados (PPGL)
BERCOS = {141, 142}

# Arquivos locais
ARQ_BANCO = RAIZ / "dados" / "monitor.db"
ARQ_ULTIMA_PAGINA = RAIZ / "dados" / "ultima_pagina.html"
ARQ_LOG = RAIZ / "logs" / "coletor.log"

# Site (pasta servida pelo GitHub Pages)
PASTA_SITE = RAIZ / "docs"
ARQ_ESTADO = PASTA_SITE / "dados" / "estado.json"

# Quantos dias de histórico (navios já despachados) vão para o site
DIAS_HISTORICO_SITE = 120
MAX_EVENTOS_SITE = 200

# Publicação: após cada coleta, faz commit + push de docs/dados/estado.json
PUBLICAR_GIT = True

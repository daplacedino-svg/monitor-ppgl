# -*- coding: utf-8 -*-
"""Monitor de Navios - PPGL (berços 141/142)

Uso:
    python coletar.py                 # uma coleta (use com o Agendador de Tarefas)
    python coletar.py --loop 60       # fica rodando, coletando a cada 60 min
    python coletar.py --sem-publicar  # coleta e gera o JSON, sem git push
    python coletar.py --arquivo pagina.html   # processa um HTML salvo (testes)
"""
import argparse
import logging
import sys
import time
from datetime import datetime, timedelta

import config
from coletor import appa, banco, exportar, publicar
from coletor.appa import FUSO_BR

log = logging.getLogger("monitor")


def configurar_log():
    config.ARQ_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    handlers = [logging.FileHandler(config.ARQ_LOG, encoding="utf-8")]
    if sys.stdout is not None:  # pythonw.exe (Agendador de Tarefas) não tem console
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def executar(arquivo=None, publicar_git=True):
    quando = datetime.now(FUSO_BR).isoformat(timespec="seconds")
    con = banco.conectar()
    try:
        try:
            if arquivo:
                html = open(arquivo, encoding="utf-8").read()
            else:
                html = appa.baixar_pagina()
                config.ARQ_ULTIMA_PAGINA.write_text(html, encoding="utf-8")
            emissao, navios = appa.interpretar(html)
            if len(navios) < 10:
                raise appa.ErroColeta(f"Só {len(navios)} navios interpretados - página suspeita, coleta descartada")
        except Exception as e:
            log.error("Coleta falhou: %s", e)
            banco.registrar_falha(con, quando, e)
            exportar.gerar(con)  # o site mostra o aviso de falha
            return False

        monitorados, n_eventos = banco.registrar_coleta(con, quando, emissao, navios)
        log.info("Portal: %d navios | berços %s: %d | novos eventos: %d",
                 len(navios), "/".join(map(str, sorted(config.BERCOS))), monitorados, n_eventos)
        exportar.gerar(con)
    finally:
        con.close()

    if publicar_git and config.PUBLICAR_GIT:
        log.info("Publicação: %s", publicar.publicar(f"Coleta {quando[:16]}"))
    return True


def main():
    p = argparse.ArgumentParser(description="Monitor de Navios - PPGL")
    p.add_argument("--loop", type=int, metavar="MIN", help="repete a coleta a cada MIN minutos")
    p.add_argument("--sem-publicar", action="store_true", help="não faz git push")
    p.add_argument("--arquivo", help="processa um HTML salvo em vez de acessar o portal")
    args = p.parse_args()
    configurar_log()

    while True:
        ok = executar(args.arquivo, not args.sem_publicar)
        if not args.loop:
            sys.exit(0 if ok else 1)
        prox = datetime.now() + timedelta(minutes=args.loop)
        log.info("Próxima coleta às %s", prox.strftime("%H:%M"))
        time.sleep(args.loop * 60)


if __name__ == "__main__":
    main()

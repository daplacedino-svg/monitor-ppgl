# -*- coding: utf-8 -*-
"""Publica docs/dados/estado.json no GitHub (GitHub Pages) via git."""
import subprocess

import config


def _git(*args):
    return subprocess.run(["git", *args], cwd=config.RAIZ, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def publicar(mensagem):
    if not (config.RAIZ / ".git").exists():
        return "git não inicializado nesta pasta - publicação ignorada"
    if not _git("remote").stdout.strip():
        return "nenhum repositório remoto configurado - publicação ignorada"

    arquivo = config.ARQ_ESTADO.relative_to(config.RAIZ).as_posix()
    _git("add", arquivo)
    if _git("diff", "--cached", "--quiet").returncode == 0:
        return "sem alterações para publicar"
    r = _git("commit", "-m", mensagem, "--", arquivo)
    if r.returncode != 0:
        return f"falha no commit: {r.stderr.strip() or r.stdout.strip()}"
    r = _git("push")
    if r.returncode != 0:
        return f"falha no push: {r.stderr.strip()}"
    return "publicado no GitHub"

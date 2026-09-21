# -*- coding: utf-8 -*-
"""Gera docs/dados/estado.json, o único arquivo que o site lê."""
import json
from datetime import datetime, timedelta

import config
from coletor.appa import FUSO_BR


def _horas(inicio, fim):
    if not inicio or not fim:
        return None
    return round((datetime.fromisoformat(fim) - datetime.fromisoformat(inicio)).total_seconds() / 3600, 1)


def _manobras_por_navio(con):
    """Manobras da praticagem agrupadas por programação, da mais próxima para a mais distante."""
    por_prog = {}
    for r in con.execute("SELECT * FROM manobras WHERE programacao IS NOT NULL ORDER BY quando"):
        m = json.loads(r["dados"])
        por_prog.setdefault(r["programacao"], []).append({
            "quando": m["quando"], "tipo": m["tipo"], "rotulo": m["rotulo"], "codigo": m["codigo"],
            "berco": m["berco"], "bordo": m["bordo"], "local": m["local"], "situacao": m["situacao"],
            "casou_por": m.get("casou_por"),
        })
    return por_prog


def gerar(con, praticagem_atualizacao=None, praticagem_erro=None):
    agora = datetime.now(FUSO_BR)
    manobras = _manobras_por_navio(con)
    if praticagem_atualizacao is None:
        ultima = con.execute("SELECT MAX(visto_em) FROM manobras").fetchone()[0]
        praticagem_atualizacao = ultima

    ult = con.execute("SELECT * FROM coletas ORDER BY id DESC LIMIT 1").fetchone()
    ult_ok = con.execute("SELECT * FROM coletas WHERE sucesso=1 ORDER BY id DESC LIMIT 1").fetchone()

    ativos = []
    for r in con.execute("SELECT * FROM navios WHERE ativo=1 ORDER BY berco, programacao"):
        n = json.loads(r["dados"])
        n["marcos"] = json.loads(r["marcos"] or "{}")
        n["primeira_vez"] = r["primeira_vez"]
        n["manobras"] = manobras.get(r["programacao"], [])
        ativos.append(n)

    limite = (agora - timedelta(days=config.DIAS_HISTORICO_SITE)).isoformat()
    historico = []
    for r in con.execute("SELECT * FROM navios WHERE ativo=0 AND ultima_vez >= ? ORDER BY ultima_vez DESC", (limite,)):
        n = json.loads(r["dados"])
        m = json.loads(r["marcos"] or "{}")
        historico.append({
            "programacao": r["programacao"],
            "embarcacao": r["embarcacao"],
            "imo": r["imo"],
            "berco": r["berco"],
            "situacao": r["categoria"],
            "mercadoria": n.get("mercadoria"),
            "sentido": n.get("sentido"),
            "operadores": n.get("operadores"),
            "agencia": n.get("agencia"),
            "previsto": m.get("previsto"),
            "unidade": m.get("unidade"),
            "chegada": m.get("chegada"),
            "atracacao": m.get("atracacao"),
            "desatracacao": m.get("desatracacao"),
            "espera_h": _horas(m.get("chegada"), m.get("atracacao")),
            "estadia_berco_h": _horas(m.get("atracacao"), m.get("desatracacao")),
            "ultima_vez": r["ultima_vez"],
        })

    eventos = [dict(r) for r in con.execute(
        "SELECT quando, programacao, embarcacao, berco, tipo, de, para, descricao FROM eventos "
        "ORDER BY id DESC LIMIT ?", (config.MAX_EVENTOS_SITE,))]

    estado = {
        "gerado_em": agora.isoformat(timespec="seconds"),
        "bercos": sorted(config.BERCOS),
        "ultima_coleta": dict(ult) if ult else None,
        "ultima_coleta_ok": ult_ok["quando"] if ult_ok else None,
        "emissao_portal": ult_ok["emissao_portal"] if ult_ok else None,
        "praticagem": {"atualizacao": praticagem_atualizacao, "erro": praticagem_erro},
        "navios": ativos,
        "historico": historico,
        "eventos": eventos,
    }
    config.ARQ_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.ARQ_ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(config.ARQ_ESTADO)
    return estado

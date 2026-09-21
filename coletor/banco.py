# -*- coding: utf-8 -*-
"""Histórico em SQLite: estado de cada navio, eventos (mudanças) e fotos de cada coleta."""
import json
import sqlite3
from datetime import datetime

import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS coletas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando TEXT NOT NULL,
    sucesso INTEGER NOT NULL,
    emissao_portal TEXT,
    navios_portal INTEGER,
    navios_monitorados INTEGER,
    erro TEXT
);
CREATE TABLE IF NOT EXISTS navios (
    programacao INTEGER PRIMARY KEY,
    embarcacao TEXT,
    imo TEXT,
    berco INTEGER,
    categoria TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    primeira_vez TEXT,
    ultima_vez TEXT,
    dados TEXT,      -- último registro completo vindo do portal (JSON)
    marcos TEXT      -- datas acumuladas: chegada, atracacao, desatracacao, eta_inicial... (JSON)
);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando TEXT NOT NULL,
    programacao INTEGER,
    embarcacao TEXT,
    berco INTEGER,
    tipo TEXT,
    de TEXT,
    para TEXT,
    descricao TEXT
);
CREATE TABLE IF NOT EXISTS fotos (
    coleta_id INTEGER,
    programacao INTEGER,
    categoria TEXT,
    berco INTEGER,
    dados TEXT,
    PRIMARY KEY (coleta_id, programacao)
);
CREATE TABLE IF NOT EXISTS manobras (
    chave TEXT PRIMARY KEY,   -- navio + código da manobra
    quando TEXT,
    navio TEXT,
    imo TEXT,
    codigo TEXT,
    tipo TEXT,
    berco INTEGER,
    situacao TEXT,
    programacao INTEGER,
    visto_em TEXT,
    dados TEXT
);
CREATE INDEX IF NOT EXISTS ix_eventos_quando ON eventos(quando);
"""

NOMES = {
    "removido": "Removido",
    "esperado": "Esperado",
    "ao_largo": "Ao largo",
    "programado": "Programado",
    "atracado": "Atracado",
    "despachado": "Despachado",
}


def conectar():
    config.ARQ_BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.ARQ_BANCO)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def registrar_falha(con, quando, erro):
    con.execute("INSERT INTO coletas (quando, sucesso, erro) VALUES (?, 0, ?)", (quando, str(erro)[:1000]))
    con.commit()


def _nome(navio):
    cat = NOMES.get(navio["categoria"], navio["categoria"])
    if navio["categoria"] == "ao_largo" and navio.get("reatracacao"):
        cat += " (reatracação)"
    return cat


def _descrever(nome, antes, depois):
    de, para = antes["categoria"], depois["categoria"]
    if de == "removido":
        return f"{nome} voltou ao line-up ({_nome(depois)})"
    if para == "atracado":
        return f"{nome} atracou" + (" (reatracação)" if antes.get("reatracacao") else "")
    if para == "despachado":
        return f"{nome} desatracou / despachado"
    if para == "ao_largo" and depois.get("reatracacao"):
        return f"{nome} desatracou e aguarda reatracação ao largo"
    if para == "ao_largo" and de == "esperado":
        return f"{nome} chegou e está fundeado ao largo"
    if para == "programado":
        return f"{nome} foi programado para atracação"
    return f"{nome}: {_nome(antes)} → {_nome(depois)}"


def _atualizar_marcos(marcos, navio, quando):
    """Guarda as datas importantes, que o portal deixa de mostrar quando o navio muda de seção."""
    for campo in ("chegada", "desatracacao", "etb"):
        if navio.get(campo):
            marcos[campo] = navio[campo]
    if navio.get("atracacao"):
        marcos.setdefault("atracacao", navio["atracacao"])  # 1ª atracação
        marcos["ultima_atracacao"] = navio["atracacao"]
    if navio.get("eta"):
        marcos.setdefault("eta_inicial", navio["eta"])
        marcos["eta"] = navio["eta"]
    for campo in ("previsto", "realizado", "unidade"):
        if navio.get(campo) is not None:
            marcos[campo] = navio[campo]
    vistos = marcos.setdefault("visto_como", {})
    vistos.setdefault(navio["categoria"], quando)
    return marcos


def navios_para_cruzamento(con):
    """Navios ativos nos berços monitorados, para cruzar com a praticagem."""
    return [dict(r) for r in con.execute(
        "SELECT programacao, imo, embarcacao FROM navios WHERE ativo=1")]


def _quando_curto(iso):
    if not iso:
        return "sem horário"
    d = datetime.fromisoformat(iso)
    return d.strftime("%d/%m às %H:%M")


def registrar_manobras(con, quando, manobras):
    """Guarda a última previsão da praticagem e gera eventos quando ela muda."""
    antigas = {r["chave"]: r for r in con.execute("SELECT * FROM manobras")}
    eventos, vistas = [], set()

    for man in manobras:
        chave = f"{man['imo'] or man['navio']}|{man['codigo']}"
        vistas.add(chave)
        antiga = antigas.get(chave)
        rotulo = man["rotulo"].lower()
        berco = f" no berço {man['berco']}" if man["berco"] else ""

        def evento(descricao, de=None, para=None):
            if man["programacao"] or man["berco"]:
                eventos.append((quando, man["programacao"], man["navio"], man["berco"],
                                "manobra", de, para, descricao))

        if antiga is None:
            evento(f"Praticagem: {rotulo}{berco} prevista para {_quando_curto(man['quando'])}"
                   f" ({man['situacao'].lower()})", None, man["situacao"])
        else:
            if antiga["quando"] != man["quando"]:
                evento(f"Praticagem: {rotulo}{berco} remarcada de {_quando_curto(antiga['quando'])}"
                       f" para {_quando_curto(man['quando'])}", antiga["quando"], man["quando"])
            if antiga["situacao"] != man["situacao"]:
                evento(f"Praticagem: {rotulo}{berco} de {_quando_curto(man['quando'])}"
                       f" agora está {man['situacao'].lower()}", antiga["situacao"], man["situacao"])

        con.execute(
            "INSERT INTO manobras VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(chave) DO UPDATE SET "
            "quando=excluded.quando, navio=excluded.navio, imo=excluded.imo, codigo=excluded.codigo, "
            "tipo=excluded.tipo, berco=excluded.berco, situacao=excluded.situacao, "
            "programacao=excluded.programacao, visto_em=excluded.visto_em, dados=excluded.dados",
            (chave, man["quando"], man["navio"], man["imo"], man["codigo"], man["tipo"], man["berco"],
             man["situacao"], man["programacao"], quando, json.dumps(man, ensure_ascii=False)),
        )

    sumidas = [c for c in antigas if c not in vistas]
    if sumidas:
        con.executemany("DELETE FROM manobras WHERE chave=?", [(c,) for c in sumidas])
    con.executemany("INSERT INTO eventos (quando, programacao, embarcacao, berco, tipo, de, para, descricao) "
                    "VALUES (?,?,?,?,?,?,?,?)", eventos)
    con.commit()
    return len(manobras), len(eventos)


def registrar_coleta(con, quando, emissao, todos):
    """Grava a coleta, atualiza o estado dos navios dos berços monitorados e gera eventos."""
    primeira_coleta = con.execute("SELECT COUNT(*) FROM navios").fetchone()[0] == 0
    por_prog = {}
    for n in todos:  # se aparecer em duas seções, prevalece a primeira (ordem da página)
        por_prog.setdefault(n["programacao"], n)
    monitorados = {p: n for p, n in por_prog.items() if n.get("berco") in config.BERCOS}

    cur = con.execute(
        "INSERT INTO coletas (quando, sucesso, emissao_portal, navios_portal, navios_monitorados) VALUES (?,1,?,?,?)",
        (quando, emissao, len(por_prog), len(monitorados)),
    )
    coleta_id = cur.lastrowid
    eventos = []

    def evento(n, tipo, de, para, descricao):
        if not primeira_coleta:
            eventos.append((quando, n["programacao"], n.get("embarcacao"), n.get("berco"), tipo, de, para, descricao))

    existentes = {r["programacao"]: r for r in con.execute("SELECT * FROM navios")}

    for prog, n in monitorados.items():
        ativo = 0 if n["categoria"] == "despachado" else 1
        antigo = existentes.get(prog)
        if antigo is None:
            marcos = _atualizar_marcos({}, n, quando)
            con.execute(
                "INSERT INTO navios VALUES (?,?,?,?,?,?,?,?,?,?)",
                (prog, n.get("embarcacao"), n.get("imo"), n.get("berco"), n["categoria"], ativo,
                 quando, quando, json.dumps(n, ensure_ascii=False), json.dumps(marcos, ensure_ascii=False)),
            )
            if n["categoria"] != "despachado":
                evento(n, "novo", None, n["categoria"],
                       f"{n.get('embarcacao')} entrou no line-up do berço {n.get('berco')} ({_nome(n)})")
            continue

        dados_antigos = {**json.loads(antigo["dados"]), "categoria": antigo["categoria"]}
        if antigo["categoria"] != n["categoria"] or bool(dados_antigos.get("reatracacao")) != bool(n.get("reatracacao")):
            evento(n, "status", antigo["categoria"], n["categoria"],
                   _descrever(n.get("embarcacao"), dados_antigos, n))
        if antigo["berco"] != n.get("berco"):
            evento(n, "berco", str(antigo["berco"]), str(n.get("berco")),
                   f"{n.get('embarcacao')} mudou do berço {antigo['berco']} para o {n.get('berco')}")
        marcos = _atualizar_marcos(json.loads(antigo["marcos"] or "{}"), n, quando)
        con.execute(
            "UPDATE navios SET embarcacao=?, imo=?, berco=?, categoria=?, ativo=?, ultima_vez=?, dados=?, marcos=? "
            "WHERE programacao=?",
            (n.get("embarcacao"), n.get("imo"), n.get("berco"), n["categoria"], ativo, quando,
             json.dumps(n, ensure_ascii=False), json.dumps(marcos, ensure_ascii=False), prog),
        )

    # Navios que estavam ativos nos berços monitorados e não estão mais
    for prog, antigo in existentes.items():
        if not antigo["ativo"] or prog in monitorados:
            continue
        ref = {"programacao": prog, "embarcacao": antigo["embarcacao"], "berco": antigo["berco"]}
        outro = por_prog.get(prog)
        if outro is not None:
            evento(ref, "berco", str(antigo["berco"]), str(outro.get("berco")),
                   f"{antigo['embarcacao']} foi transferido do berço {antigo['berco']} para o {outro.get('berco')}")
            con.execute("UPDATE navios SET ativo=0, berco=?, categoria=?, ultima_vez=? WHERE programacao=?",
                        (outro.get("berco"), outro["categoria"], quando, prog))
        else:
            evento(ref, "removido", antigo["categoria"], None,
                   f"{antigo['embarcacao']} saiu do line-up sem aparecer como despachado")
            con.execute("UPDATE navios SET ativo=0, categoria='removido', ultima_vez=? WHERE programacao=?",
                        (quando, prog))

    con.executemany("INSERT INTO eventos (quando, programacao, embarcacao, berco, tipo, de, para, descricao) "
                    "VALUES (?,?,?,?,?,?,?,?)", eventos)
    con.executemany("INSERT INTO fotos VALUES (?,?,?,?,?)",
                    [(coleta_id, p, n["categoria"], n.get("berco"), json.dumps(n, ensure_ascii=False))
                     for p, n in monitorados.items()])
    con.commit()
    return len(monitorados), len(eventos)

"use strict";

const CATS = {
  atracado: "Atracado",
  programado: "Programado",
  ao_largo: "Ao largo",
  esperado: "Esperado",
  despachado: "Despachado",
  removido: "Removido",
};
const ORDEM_FILA = { programado: 0, ao_largo: 1, esperado: 2 };
const RECARREGAR_MIN = 5;

let estado = null;
const $ = (s) => document.querySelector(s);

// ---------------------------------------------------------------- formatação
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dt = (iso) => (iso ? new Date(iso) : null);
const fmtNum = (v, casas = 0) => (v == null ? "—" : v.toLocaleString("pt-BR", { maximumFractionDigits: casas }));
const fmtQtd = (v, un) => (v == null ? "—" : `${fmtNum(v)} ${un === "movs" ? "movs" : "t"}`);

function fmtData(iso, comDia = true) {
  const d = dt(iso);
  if (!d) return "—";
  const tz = { timeZone: "America/Sao_Paulo" };
  const dia = d.toLocaleDateString("pt-BR", { ...tz, weekday: "short" }).replace(".", "");
  const data = d.toLocaleDateString("pt-BR", { ...tz, day: "2-digit", month: "2-digit" });
  const hora = d.toLocaleTimeString("pt-BR", { ...tz, hour: "2-digit", minute: "2-digit" });
  return comDia ? `${dia} ${data} ${hora}` : `${data} ${hora}`;
}

function fmtDur(horas) {
  if (horas == null || isNaN(horas)) return "—";
  const neg = horas < 0;
  let h = Math.abs(horas);
  let txt;
  if (h < 1) txt = `${Math.round(h * 60)} min`;
  else if (h < 24) {
    const min = Math.round(h * 60);
    txt = `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, "0")}`;
  } else {
    const hi = Math.round(h); // arredonda antes de separar, senão 7d 24h em vez de 8d
    txt = `${Math.floor(hi / 24)}d ${hi % 24}h`;
  }
  return neg ? `-${txt}` : txt;
}
const horasEntre = (a, b) => (a && b ? (dt(b) - dt(a)) / 3.6e6 : null);
const horasDesde = (iso) => horasEntre(iso, new Date().toISOString());
const relativo = (iso) => {
  const h = horasEntre(new Date().toISOString(), iso);
  if (h == null) return "";
  if (Math.abs(h) < 1 / 60) return "agora";
  return h >= 0 ? `em ${fmtDur(h)}` : `há ${fmtDur(-h)}`;
};

const chip = (cat, reatrac) =>
  `<span class="chip c-${cat}">${CATS[cat] || cat}${reatrac ? " · reatracação" : ""}</span>`;
const sentido = (s) => (s ? `<span class="sentido" title="${s.includes("Imp") && s.includes("Exp") ? "Importação/Exportação" : s.startsWith("Imp") ? "Importação (descarga)" : "Exportação (carga)"}">${esc(s)}</span>` : "");

// ---------------------------------------------------------------- render
function renderStatus() {
  const el = $("#status");
  const ok = estado.ultima_coleta_ok;
  const idade = horasDesde(ok);
  const falhou = estado.ultima_coleta && !estado.ultima_coleta.sucesso;
  const classe = falhou ? "erro" : idade > 3 ? "velho" : "";
  const prat = estado.praticagem || {};
  el.innerHTML = `<span class="ponto ${classe}"></span>Atualizado <b>${ok ? relativo(ok) : "—"}</b> · ${fmtData(ok)}<br>
    <span style="opacity:.75">Emissão APPA: ${fmtData(estado.emissao_portal)}${
      prat.atualizacao ? ` · Praticagem: ${fmtData(prat.atualizacao)}` : ""}</span>`;

  const alerta = $("#alerta");
  const msgs = [];
  if (falhou) msgs.push(`A última tentativa de coleta (${fmtData(estado.ultima_coleta.quando)}) falhou: ${esc(estado.ultima_coleta.erro)}`);
  if (idade > 3) msgs.push(`Os dados têm mais de ${Math.floor(idade)} horas. O computador que faz a coleta pode estar desligado.`);
  if (prat.erro) msgs.push(`Praticagem indisponível na última coleta (as manobras podem estar desatualizadas): ${esc(prat.erro)}`);
  alerta.hidden = !msgs.length;
  alerta.innerHTML = msgs.join("<br>");
}

function renderResumo() {
  const navios = estado.navios;
  const por = (c) => navios.filter((n) => n.categoria === c);
  const largo = por("ao_largo");
  const maiorEspera = Math.max(0, ...largo.map((n) => horasDesde(n.chegada || n.marcos.chegada) || 0));
  const esperados = por("esperado").sort((a, b) => (a.eta > b.eta ? 1 : -1));
  const itens = [
    ["atracado", por("atracado").length, "Atracados", `de ${estado.bercos.length} berços`],
    ["programado", por("programado").length, "Programados", "com atracação definida"],
    ["ao_largo", largo.length, "Ao largo", largo.length ? `maior espera: ${fmtDur(maiorEspera)}` : "nenhum aguardando"],
    ["esperado", esperados.length, "Esperados", esperados.length ? `próximo: ${fmtData(esperados[0].eta, false)}` : "—"],
  ];
  $("#resumo").innerHTML = itens
    .map(([c, v, l, d]) => `<div class="kpi c-${c}"><div class="v num">${v}</div><div class="l">${l}</div><div class="d">${d}</div></div>`)
    .join("");
}

function cardAtracado(n) {
  const m = n.marcos || {};
  const pct = n.previsto ? Math.min(100, Math.max(0, (100 * (n.realizado || 0)) / n.previsto)) : null;
  const atrac = n.atracacao || m.ultima_atracacao;
  const chegada = n.chegada || m.chegada;
  return `<div class="navio atual" tabindex="0" data-prog="${n.programacao}">
    <div class="navio-nome">${esc(n.embarcacao)} ${sentido(n.sentido)}</div>
    <div class="navio-linha">${esc(n.mercadoria)} · ${opsCurtos(n.operadores)}</div>
    ${pct != null ? `<div class="barra" role="progressbar" aria-valuenow="${pct.toFixed(0)}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>
    <div class="barra-leg"><span>${fmtQtd(n.realizado, n.unidade)} de ${fmtQtd(n.previsto, n.unidade)}</span><b class="num">${pct.toFixed(0)}%</b></div>` : ""}
    <dl class="tempos">
      <div><dt>Atracou</dt><dd>${fmtData(atrac)}<br><small>${relativo(atrac)}</small></dd></div>
      <div><dt>Fim previsto (janela)</dt><dd>${fmtData(n.janela_fim)}<br><small>${relativo(n.janela_fim)}</small></dd></div>
      <div><dt>Espera antes de atracar</dt><dd>${fmtDur(horasEntre(chegada, atrac))}</dd></div>
    </dl>
    ${manobraHTML(n)}
  </div>`;
}

// Nomes curtos (ver operadores.js); o nome completo fica no title (passar o mouse)
const opsCurtos = (ops) =>
  ops && ops.length
    ? `<span title="${esc(ops.join(" / "))}">${esc([...new Set(ops.map(nomeCurtoOperador))].join(" / "))}</span>`
    : "";
// --------------------------------------------------- praticagem (manobras)
const SITUACAO = {
  "EM ANDAMENTO": "andamento",
  "CONFIRMADA": "confirmada",
  "A CONFIRMAR": "aconfirmar",
  "PREVISTA": "prevista",
};

/** Manobra mais relevante: a próxima no futuro; se não houver, a mais recente. */
function proximaManobra(ms) {
  if (!ms || !ms.length) return null;
  const agora = new Date().toISOString();
  return ms.find((m) => m.quando && m.quando >= agora) || ms[ms.length - 1];
}

function manobraHTML(n, compacto = false) {
  const m = proximaManobra(n.manobras);
  if (!m) return "";
  const cls = SITUACAO[m.situacao] || "prevista";
  const passou = m.quando && m.quando < new Date().toISOString();
  return `<div class="manobra s-${cls}">
    <span class="manobra-t">⚓ ${esc(m.rotulo)}${m.bordo ? ` ${esc(m.bordo)}` : ""}</span>
    <b>${fmtData(m.quando, !compacto)}</b>
    <span class="manobra-sit">${esc(m.situacao)}</span>
    ${passou ? "" : `<small>${relativo(m.quando)}</small>`}
  </div>`;
}

const operadores = (ops) =>
  ops && ops.length ? `<div class="operador"><span>Operador</span> ${opsCurtos(ops)}</div>` : "";

function itemFila(n, i) {
  const m = n.marcos || {};
  let quando = "", sub = "";
  if (n.categoria === "programado") {
    const etb = n.etb || n.janela_inicio;
    quando = etb ? `ETB ${fmtData(etb)}` : "Aguardando ETB";
    sub = n.chegada ? `fundeado há ${fmtDur(horasDesde(n.chegada))}` : etb ? relativo(etb) : "";
  } else if (n.categoria === "ao_largo") {
    const chegada = n.chegada || m.chegada;
    quando = `<span class="espera">fundeado há ${fmtDur(horasDesde(chegada))}</span>`;
    sub = `chegou ${fmtData(chegada)}`;
  } else {
    quando = `ETA ${fmtData(n.eta)}`;
    const mudou = m.eta_inicial && m.eta_inicial !== n.eta;
    sub = relativo(n.eta) + (mudou ? ` · era ${fmtData(m.eta_inicial, false)}` : "");
  }
  return `<li class="navio" tabindex="0" data-prog="${n.programacao}">
    <span class="pos num">${i + 1}</span>
    <div>
      <div><b>${esc(n.embarcacao)}</b> ${sentido(n.sentido)}</div>
      <div class="navio-linha">${chip(n.categoria, n.reatracacao)} ${esc(n.mercadoria)} · ${fmtQtd(n.previsto, n.unidade)}</div>
      ${operadores(n.operadores)}
      ${manobraHTML(n, true)}
    </div>
    <div class="quando">${quando}<small>${sub}</small></div>
  </li>`;
}

function chaveFila(n) {
  const t = n.categoria === "programado" ? n.etb || n.janela_inicio || n.chegada
    : n.categoria === "ao_largo" ? n.chegada || n.marcos?.chegada
    : n.eta;
  return [ORDEM_FILA[n.categoria] ?? 9, t || "9999"];
}

function renderBercos() {
  $("#bercos").innerHTML = estado.bercos.map((b) => {
    const doBerco = estado.navios.filter((n) => n.berco === b);
    const atracados = doBerco.filter((n) => n.categoria === "atracado");
    const fila = doBerco
      .filter((n) => n.categoria in ORDEM_FILA)
      .sort((x, y) => {
        const [a1, a2] = chaveFila(x), [b1, b2] = chaveFila(y);
        return a1 - b1 || (a2 > b2 ? 1 : a2 < b2 ? -1 : 0);
      });
    const volume = fila.filter((n) => n.unidade === "t").reduce((s, n) => s + (n.previsto || 0), 0);
    return `<article class="berco">
      <div class="berco-cab"><h3>Berço ${b}</h3><span>${fila.length} na fila${volume ? ` · ${fmtNum(volume)} t` : ""}</span></div>
      <div class="no-berco">
        <div class="rotulo">No berço</div>
        ${atracados.length ? atracados.map(cardAtracado).join("<hr>") : `<div class="livre">Berço livre</div>`}
      </div>
      <div class="rotulo" style="padding:12px 16px 0">Fila</div>
      ${fila.length ? `<ol class="fila">${fila.map(itemFila).join("")}</ol>` : `<div class="fila-vazia">Nenhum navio na fila</div>`}
    </article>`;
  }).join("");
}

function renderEventos() {
  const ev = estado.eventos;
  $("#eventos").innerHTML = ev.length
    ? ev.map((e) => {
        const marca = e.tipo === "manobra" ? `<span class="chip c-manobra">⚓ praticagem</span> `
          : e.para && CATS[e.para] ? chip(e.para) + " " : "";
        return `<li class="navio" tabindex="0" data-prog="${e.programacao}"><time datetime="${e.quando}">${fmtData(e.quando)}</time><span>${marca}${esc(e.descricao)}</span></li>`;
      }).join("")
    : `<li class="sem-eventos"><span class="vazio">As mudanças de situação (chegada, atracação, desatracação…) aparecem aqui a partir das próximas coletas.</span></li>`;
}

function renderHistorico() {
  const h = estado.historico;
  const media = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null);
  $("#hist-resumo").innerHTML = estado.bercos.map((b) => {
    const esp = h.filter((x) => x.berco === b && x.espera_h != null).map((x) => x.espera_h);
    const est = h.filter((x) => x.berco === b && x.estadia_berco_h != null).map((x) => x.estadia_berco_h);
    return `<div>Berço ${b}: espera média <b>${fmtDur(media(esp))}</b> · estadia média <b>${fmtDur(media(est))}</b> <small>(${esp.length} navios)</small></div>`;
  }).join("");

  const cab = `<thead><tr><th>Navio</th><th>Berço</th><th>Mercadoria</th><th>Operador</th><th class="n">Qtd.</th><th>Chegada</th><th>Atracação</th><th>Desatracação</th><th class="n">Espera</th><th class="n">No berço</th></tr></thead>`;
  const linhas = h.length
    ? h.map((x) => `<tr data-hist="${x.programacao}">
        <td><b>${esc(x.embarcacao)}</b> ${x.situacao !== "despachado" ? chip(x.situacao) : ""}</td>
        <td>${x.berco ?? "—"}</td><td>${esc(x.mercadoria)}</td><td>${opsCurtos(x.operadores) || "—"}</td><td class="n">${fmtQtd(x.previsto, x.unidade)}</td>
        <td>${fmtData(x.chegada, false)}</td><td>${fmtData(x.atracacao, false)}</td><td>${fmtData(x.desatracacao, false)}</td>
        <td class="n">${fmtDur(x.espera_h)}</td><td class="n">${fmtDur(x.estadia_berco_h)}</td></tr>`).join("")
    : `<tr><td class="vazio" colspan="10">Ainda não há navios despachados registrados.</td></tr>`;
  $("#historico").innerHTML = cab + `<tbody>${linhas}</tbody>`;
}

// ---------------------------------------------------------------- detalhe
function abrirDetalhe(prog) {
  const n = estado.navios.find((x) => x.programacao === prog);
  const h = estado.historico.find((x) => x.programacao === prog);
  if (!n && !h) return;
  const eventos = estado.eventos.filter((e) => e.programacao === prog);
  const campo = (rot, val) => (val == null || val === "" || val === "—" ? "" : `<div><dt>${rot}</dt><dd>${val}</dd></div>`);

  let corpo;
  if (n) {
    const m = n.marcos || {};
    corpo = `<h3>${esc(n.embarcacao)}</h3>
      <div>${chip(n.categoria, n.reatracacao)} Berço ${n.berco} ${sentido(n.sentido)}</div>
      <dl>
        ${campo("Programação", n.programacao)}${campo("DUV", esc(n.duv))}${campo("IMO", esc(n.imo))}
        ${campo("LOA", n.loa && fmtNum(n.loa, 2) + " m")}${campo("DWT", n.dwt && fmtNum(n.dwt))}
        ${campo("Calado chegada / saída", n.calado_chegada && `${fmtNum(n.calado_chegada, 2)} / ${fmtNum(n.calado_saida, 2)} m`)}
        ${campo("Agência", esc(n.agencia))}
        ${campo("ETA", n.eta && fmtData(n.eta))}${campo("ETA inicial", m.eta_inicial && m.eta_inicial !== n.eta && fmtData(m.eta_inicial))}
        ${campo("Chegada", (n.chegada || m.chegada) && fmtData(n.chegada || m.chegada))}
        ${campo("ETB", n.etb && fmtData(n.etb))}
        ${campo("Atracação", (n.atracacao || m.atracacao) && fmtData(n.atracacao || m.atracacao))}
        ${campo("Janela operacional", n.janela_inicio && `${fmtData(n.janela_inicio, false)} → ${fmtData(n.janela_fim, false)}`)}
        ${campo("Previsto", fmtQtd(n.previsto, n.unidade))}${campo("Realizado", n.realizado != null && fmtQtd(n.realizado, n.unidade))}
        ${campo("Saldo", n.saldo_total != null && fmtQtd(n.saldo_total, n.unidade))}
        ${campo("No monitor desde", fmtData(n.primeira_vez))}
      </dl>
      ${(n.manobras || []).length ? `<h4>Manobras (praticagem)</h4>
        ${n.manobras.map((m) => `<div class="manobra s-${SITUACAO[m.situacao] || "prevista"}">
          <span class="manobra-t">⚓ ${esc(m.rotulo)}${m.local ? ` · ${esc(m.local)}` : ""}</span>
          <b>${fmtData(m.quando)}</b><span class="manobra-sit">${esc(m.situacao)}</span>
        </div>`).join("")}` : ""}
      <h4>Cargas / operadores</h4>
      <div class="tabela-wrap"><table class="tabela"><thead><tr><th>Operador</th><th>Mercadoria</th><th>Sentido</th><th class="n">Prancha t/dia</th><th class="n">Previsto</th><th class="n">Realizado</th></tr></thead><tbody>
      ${(n.cargas || []).map((c) => `<tr><td>${esc(c.operador)}</td><td>${esc(c.mercadoria)}</td><td>${esc(c.sentido)}</td><td class="n">${fmtNum(c.prancha)}</td><td class="n">${fmtQtd(c.previsto, c.unidade)}</td><td class="n">${c.realizado != null ? fmtQtd(c.realizado, c.unidade) : "—"}</td></tr>`).join("")}
      </tbody></table></div>`;
  } else {
    corpo = `<h3>${esc(h.embarcacao)}</h3><div>${chip(h.situacao)} Berço ${h.berco}</div>
      <dl>${campo("Programação", h.programacao)}${campo("IMO", esc(h.imo))}${campo("Mercadoria", esc(h.mercadoria))}
        ${campo("Operadores", esc((h.operadores || []).join(", ")))}${campo("Agência", esc(h.agencia))}
        ${campo("Quantidade", fmtQtd(h.previsto, h.unidade))}${campo("Chegada", fmtData(h.chegada))}
        ${campo("Atracação", fmtData(h.atracacao))}${campo("Desatracação", fmtData(h.desatracacao))}
        ${campo("Espera", fmtDur(h.espera_h))}${campo("Tempo no berço", fmtDur(h.estadia_berco_h))}</dl>`;
  }
  if (eventos.length) {
    corpo += `<h4>Movimentações</h4><ol class="eventos">${eventos.map((e) => `<li><time>${fmtData(e.quando)}</time><span>${esc(e.descricao)}</span></li>`).join("")}</ol>`;
  }
  $("#detalhe-corpo").innerHTML = corpo;
  $("#detalhe").showModal();
}

document.addEventListener("click", (ev) => {
  const alvo = ev.target.closest("[data-prog],[data-hist]");
  if (alvo && !alvo.closest("dialog")) abrirDetalhe(Number(alvo.dataset.prog || alvo.dataset.hist));
});
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && ev.target.matches?.("[data-prog]")) abrirDetalhe(Number(ev.target.dataset.prog));
});
$("#detalhe").addEventListener("click", (ev) => { if (ev.target.id === "detalhe") ev.target.close(); });

// ---------------------------------------------------------------- carga
async function carregar() {
  try {
    const r = await fetch(`dados/estado.json?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    estado = await r.json();
    renderStatus();
    renderResumo();
    renderBercos();
    renderEventos();
    renderHistorico();
  } catch (e) {
    $("#status").textContent = "Não foi possível carregar os dados";
    const a = $("#alerta");
    a.hidden = false;
    a.textContent = `Erro ao carregar dados/estado.json: ${e.message}`;
  }
}

carregar();
setInterval(carregar, RECARREGAR_MIN * 60 * 1000);

"use strict";
// Nomes curtos dos operadores, usados na fila, no card do navio atracado e no histórico.
// O nome completo continua aparecendo no detalhe do navio e ao passar o mouse.
// Para acrescentar: "NOME EXATAMENTE COMO NO PORTAL": "NOME CURTO",
// (maiúsculas/minúsculas e acentos são ignorados na comparação)
const NOMES_CURTOS_OPERADORES = {
  "PETROBRAS TRANSPORTE S.A - TRANSPETRO": "TRANSPETRO",
  "CBL - COMPANHIA BRASILEIRA DE LOGÍSTICA": "CBL",
  "CATTALINI": "CATTALINI",
  "TERIN": "TERIN",
  "ROCHA TERMINAIS PORTUARIOS E LOGISTICA S.A.": "ROCHA",
  "FORTEPAR OPERAÇÕES PORTUÁRIAS S.A.": "FORTEPAR",
  "PORTO PONTA DO FELIX S/A": "PONTA DO FÉLIX",
  "PORTSOY OPERACOES PORTUARIAS LTDA": "PORTSOY",
  "EMPORT OPERACOES PORTUARIAS LTDA": "EMPORT",
  "ALPHAMAR PORT SERVICES": "ALPHAMAR",
  "ASCENSUS - TVA PAR": "ASCENSUS",
};

const _normOp = (s) => String(s || "").normalize("NFD").replace(/\p{M}/gu, "").toUpperCase().replace(/\s+/g, " ").trim();
const _mapaOp = Object.fromEntries(Object.entries(NOMES_CURTOS_OPERADORES).map(([k, v]) => [_normOp(k), v]));

// Regra genérica para operadores fora da lista: tira razão social e termos repetitivos.
function nomeCurtoOperador(nome) {
  if (!nome) return "";
  const mapeado = _mapaOp[_normOp(nome)];
  if (mapeado) return mapeado;
  return nome
    .replace(/\b(S\.?\/?A\.?|LTDA\.?|EIRELI|ME)\b\.?/gi, "")
    .replace(/\b(OPERA[CÇ][OÕ]ES|TERMINAIS|TERMINAL) PORTU[AÁ]RI[OA]S?\b/gi, "")
    .replace(/\bE LOG[IÍ]STICA\b/gi, "")
    .replace(/[\s\-–,]+$/g, "")
    .replace(/\s+/g, " ")
    .trim() || nome;
}

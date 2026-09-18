# Monitor de Navios — PPGL (berços 141 e 142)

Acompanha os navios dos berços 141 e 142 do Píer Público de Granéis Líquidos do Porto de
Paranaguá usando o Line-Up publicado pela APPA, e publica um site com a situação atual,
a fila, as movimentações e o histórico de atracações.

```
Portal APPA ──(coletar.py, a cada hora no seu PC)──> dados/monitor.db (SQLite, histórico)
                                                  └─> docs/dados/estado.json ──git push──> GitHub Pages
```

## Estrutura

| Caminho | O que é |
|---|---|
| `coletar.py` | Script principal: baixa → interpreta → grava histórico → gera JSON → publica |
| `config.py` | Berços monitorados, URL, caminhos, liga/desliga publicação |
| `coletor/appa.py` | Download e interpretação da página (trata rowspan, números e datas BR) |
| `coletor/banco.py` | SQLite: estado dos navios, eventos (mudanças de situação), fotos de cada coleta |
| `coletor/exportar.py` | Gera `docs/dados/estado.json` |
| `coletor/publicar.py` | `git commit` + `git push` do JSON |
| `docs/` | Site estático (HTML/CSS/JS, sem build) servido pelo GitHub Pages |
| `dados/` | Banco SQLite e última página baixada (não vai para o GitHub) |
| `logs/coletor.log` | Log das coletas |

## Categorias

A página da APPA tem as seções ATRACADOS, PROGRAMADOS, AO LARGO PARA REATRACAÇÃO, AO LARGO,
ESPERADOS e DESPACHADOS. As duas "ao largo" viram uma só categoria (`ao_largo`, com o
indicador `reatracacao`). DESPACHADOS alimenta o histórico. APOIO PORTUÁRIO é ignorado.

## Uso

```powershell
pip install -r requirements.txt
python coletar.py                 # uma coleta
python coletar.py --sem-publicar  # sem git push
python coletar.py --loop 60       # fica rodando (alternativa ao Agendador)
.\agendar_tarefa.ps1              # agenda a coleta de hora em hora no Windows
```

Para ver o site localmente: `python -m http.server 8765 --directory docs` e abra http://localhost:8765.

## Publicação no GitHub Pages

1. Crie um repositório no GitHub (ex.: `monitor-ppgl`).
2. Na pasta do projeto: `git remote add origin https://github.com/<usuario>/monitor-ppgl.git` e `git push -u origin main`
   (na primeira vez o Git abre o login do GitHub e guarda a credencial).
3. No GitHub: *Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/docs`*.
4. A partir daí, cada coleta faz commit/push de `docs/dados/estado.json` e o site atualiza em ~1 min.

## Observações

- Datas no formato ISO com fuso de Brasília (-03:00).
- Com mais de um operador, o portal repete o "Realizado" do navio em cada linha; o realizado total é
  calculado como `Previsto − Saldo Total`.
- Eventos só são gerados a partir da 2ª coleta (a 1ª apenas carrega o estado inicial).
- O histórico (espera, tempo no berço) só tem a data de atracação dos navios vistos atracados
  pelo monitor; os despachados antes da 1ª coleta aparecem sem ela.

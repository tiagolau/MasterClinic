# 011 — Identidade visual Master Clinic no painel

**Data:** 2026-08-04
**Status:** aceito

## Contexto

O painel (ADRs 008–010) usava a paleta de referência da skill `dataviz` (azul/laranja/aqua)
sem nenhuma marca. O usuário pediu personalização com as cores da Master Clinic,
**mantendo o fundo preto**.

Não havia ativo de marca no repositório: as únicas cores versionadas
(`#00FFCD`, `#C24A00`) eram da LP da **mentoria** — marca diferente da clínica.

## Decisão

### Origem dos ativos

Extraídos do site oficial `masterclinicodontologia.com.br`:

- **Verde institucional `#008E45`** — cor dominante (79 ocorrências no CSS do site);
  apoios `#77DDA8` (verde-claro) e `#F2BD13` (dourado).
- **Logo** `wp-content/uploads/2022/01/logo-1.png` (186×69, PNG **branco com
  transparência**) → `static/img/logo-master-clinic.png`. Sendo branca, funciona
  sobre o fundo escuro sem tratamento. Favicon gerado recortando a marca
  (dente/folha) da porção esquerda da arte.

### Paleta — validada, não escolhida no olho

Tudo passou por `scripts/validate_palette.js` da skill `dataviz`
(`--mode dark --surface #1a1a19`):

| Uso | Valor | Resultado |
|---|---|---|
| Séries do gráfico (verde marca ↔ azul) | `#008e45` ↔ `#3987e5` | PASS — CVD ΔE 23.1, normal 25.2, contraste ≥ 3:1 |
| Rampa ordinal do funil (6 passos) | `#8fe3ba → #00702f` | PASS — L monotônica, gaps ≥ 0.06, ponta escura 2.79:1, hue spread 13° |
| Texto verde sobre superfície escura | `#2bbb77` (`--marca-clara`) | 7:1 — `#008e45` puro dá 4.11:1, insuficiente para corpo de texto |

Descartados no caminho: `#00b85c` (fora da banda de luminosidade, L 0.685) e
`#00a04e` (CVD ΔE 5.5 contra o laranja — FAIL).

### Aplicação

- **Séries:** verde da marca assumiu os *leads de tráfego* (era azul); azul foi
  para *leads novos*; laranja segue no *gasto*. Rótulo direto no título do painel
  atualizado ("tráfego (verde) × novos no CRM (azul)") — exigido porque o par
  verde↔laranja fica na faixa de aviso 6–8 de CVD.
- **Chrome:** logo no topo e no login, régua verde sob o cabeçalho, borda esquerda
  verde nos tiles e nos títulos dos cartões, botões/filtro ativo/foco em verde,
  balão da clínica no transcript em verde escuro, favicon e `theme-color`.
- **Status colors preservadas** (`good/warning/serious/critical`) — a skill trata
  como reservadas; não viraram tema.

### Bug corrigido no caminho

`.funil-barra` era um `<span>` **inline**, e elemento inline ignora `width` em
porcentagem: as barras do funil renderizavam com **0px desde a primeira versão**
(`styleWidth: 100%` / `renderWidth: 0`, confirmado via DOM). Corrigido com
`display: block` no par wrap/barra.

## Alternativas Consideradas

- **Dourado `#F2BD13` como cor de série:** rejeitado — colide com a status
  `warning` (`#fab219`), que o painel usa em prioridade média e alertas.
- **Tema claro / fundo verde:** rejeitado — o usuário pediu explicitamente
  manter o fundo preto.
- **Recriar a logo em SVG:** desnecessário — o PNG branco original serve nos
  tamanhos usados (34px no topo, 168px no login).

## Consequências

- O painel lê como Master Clinic sem perder a acessibilidade da paleta de
  referência: qualquer troca futura de cor de série **deve** passar pelo
  validador antes de subir.
- Barras do funil passaram a existir de fato (regressão silenciosa desde o ADR 008).
- A logo é servida do repositório (não hotlink do site do cliente) — o painel não
  quebra se o WordPress dele sair do ar.

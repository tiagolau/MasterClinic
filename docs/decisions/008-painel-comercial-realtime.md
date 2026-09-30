# 008 — Painel comercial realtime (Meta Ads → DataCrazy → IA diagnóstica)

**Data:** 2026-08-04
**Status:** aceito

## Contexto

A Master Clinic precisava enxergar a jornada completa do paciente — anúncio Meta →
conversa WhatsApp → lead/funil no DataCrazy → fechamento — num único lugar, com
atualização quase em tempo real, e de um "gestor comercial de IA" que lesse as
conversas do dia e apontasse oportunidades em aberto (lead quente sem resposta,
follow-up esquecido, problema de atendimento).

Restrições que moldaram o desenho:

- **Rate limit de 30 req/min** na REST do DataCrazy → o dashboard não pode bater
  na API; precisa de réplica local.
- **`lead.source` vazio em 100% dos leads** (ADR 004) → atribuição de tráfego
  depende da mensagem CTWA pré-preenchida e do `ctwa_clid`.
- **A REST de mensagens não expõe o contexto do anúncio** (`ctwaClid` /
  `externalAdReply`) — verificado nas 1.687 conversas raspadas e em conversas
  recentes: nenhum sinal de ad chega pela API.
- **Clinicorp sem credenciais** (mesmo bloqueio do ADR do funil de aniversariantes)
  → fica como fase 2; receita proxy = `business.total` do DataCrazy.

## Decisão

App único em [`dashboard/`](../../dashboard/): **FastAPI + Postgres + frontend
estático próprio**, deployado como stack Docker Swarm atrás do Traefik na VPS.

### Sincronização (réplica local)

- **Incremental (5 min):** conversas/negócios/leads vêm ordenados desc da API —
  pagina-se até o watermark (com margem de 45 min) e baixam-se mensagens apenas
  das conversas com `lastMessageDate` mais novo que o último sync local.
- **Completo (60 min):** sweep integral (leads ~8 req, negócios ~1, conversas ~2)
  + pipelines/etapas/instâncias — pega updates que não sobem ao topo da ordenação.
- **Meta (60 min):** insights nível ad **por dia** (janelas grandes davam HTTP 500
  no Graph), rejanela de 3 dias; backfill inicial de 90 dias.
- **Seed:** `python -m app.seed data/` importa a raspagem existente e evita ~1h de
  carga inicial pela API.

### Atribuição de tráfego (cascata)

1. **Anotação do fluxo X1** (`ad_id: NNN` em mensagem interna) — parseada na
   classificação;
2. **Collector próprio** `POST /ingest/ctwa` (Bearer `INGEST_TOKEN`): o fluxo X1
   ganha um bloco `api` extra enviando telefone + `ctwaClid` + `adId`; o sync casa
   por telefone (janela de 48h). *Pendente: editar o X1 no painel do DataCrazy —
   instruções no README do dashboard*;
3. **Heurística CTWA** (aberturas pré-preenchidas, portada do
   `analisar_conversas.py`) — cobre todo o histórico, sem granularidade de ad.

### IA diagnóstica diária

Job às 20h30 (configurável): monta material com métricas do dia, oportunidades
determinísticas (SQL), negócios estagnados e transcrições das conversas de
pacientes do dia (cap de 40 conversas × 3.500 chars), chama **Claude (preferido)
ou Gemini** exigindo JSON estruturado (resumo executivo, oportunidades com ação e
prioridade, alertas de atendimento, insight de tráfego, nota do dia), salva em
`diagnosticos` e envia digest no WhatsApp via uazapi (`DIGEST_PHONES`).

As **oportunidades em aberto também são calculadas por SQL** (lead com a última
mensagem dele, sem resposta há 30+ min, janela de 7 dias) — o painel não depende
da IA para o operacional.

### Segurança

Senha única (`DASHBOARD_PASSWORD`) → cookie HMAC assinado (`SECRET_KEY`, 30 dias);
collector com Bearer token próprio; Postgres só na rede interna da stack. O banco
replica conversas de pacientes — mesmo cuidado do `data/`: não expor, não versionar.

## Alternativas Consideradas

- **N8N + Metabase** (recomendação do brainstorm): rejeitado como produto final —
  o centro do pedido é o feed diagnóstico textual da IA, que BI pronto não
  apresenta bem; e o ETL já estava 80% resolvido nos scripts da raspagem.
- **Webhooks/streaming reativo:** over-engineering — latência de 5 min atende, e
  o collector CTWA já dá tempo-real no evento que importa (lead de anúncio).
- **Dashboard em Next.js/Vercel:** rejeitado — um container único (API + estáticos)
  na VPS elimina CORS, segundo deploy e custo; frontend vanilla + SVG não precisa
  de build.
- **Atribuição via campo customizado no lead:** possível pelo X1, mas o collector
  preserva histórico de eventos e não depende de escrita no CRM.

## Consequências

- Painel em produção com: tiles do dia, gasto×leads diário (2 painéis, mesmo eixo
  x), funis por etapa/unidade, tabela de campanhas (gasto, conversas, R$/conversa,
  leads CAPI/CRM), oportunidades clicáveis com transcript, negócios estagnados e
  diagnóstico IA.
- Validado localmente com dados reais: seed 1.687 conversas/7.436 leads, sync
  incremental trouxe conversas e negócios do dia, backfill Meta 90d
  (R$ 15.340, 1.513 linhas), diagnóstico Gemini gerado e coerente (apontou fila
  de 108 sem resposta e leads de tráfego ignorados).
- Ganhos aparecem zerados até a equipe marcar negócios como `won` com valor no
  CRM — o ROI por campanha completo depende disso (e da fase 2 Clinicorp).
- Pendências: editar fluxo X1 (bloco collector), definir domínio/DNS do painel,
  chave de IA no servidor (Anthropic ou Gemini), tokens uazapi para o digest.

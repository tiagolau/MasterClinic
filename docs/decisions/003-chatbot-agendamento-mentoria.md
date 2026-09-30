# 003 — Chatbot de Agendamento da Mentoria (Cal.com + DataCrazy)

**Data:** 2026-07-14
**Status:** aceito

## Contexto

O Dr. Wilton vai rodar tráfego para uma landing page com formulário de qualificação
que cria o lead direto no DataCrazy e direciona o interessado ao WhatsApp. Se o lead
preencher o formulário mas não iniciar a conversa, deve receber uma mensagem em 10 min.
O objetivo do chatbot é **agendar uma reunião de fechamento (diagnóstico) com o
Dr. Wilton via Cal.com**. O roteiro se inspira no funil high ticket do Renan Vieira
(mentor do Dr. Wilton) — ver `docs/formulário mentoria/`.

## Decisão

Criadas 4 automações no formato nativo `.dc` do DataCrazy, geradas programaticamente
por `docs/formulário mentoria/gerar_dc.py` (UUIDs e conexões consistentes):

1. **Reengajamento 10min** — `lead-created` → filtra source `LP-MENTORIA-WILTON` →
   cria card em *Novo Lead* + tag → espera 10 min → se não conversou, abertura fria e
   chama a Automação 2 (`start-another-automation`).
2. **Chatbot Agendamento** (núcleo) — gatilho duplo (`message-received` OU iniciado pela
   Auto 1) → tag CONVERSOU → saudação → valor → CTA com botões (*Quero agendar* /
   *Tenho uma dúvida*) → link Cal.com pré-preenchido → cadência de resgate (+2h/+2h/+1d/+1d
   → breakup → *Perdido*), cada etapa checando a tag REUNIAO-AGENDADA para parar.
3. **Cal.com Booking Confirmado** (esqueleto) — webhook `BOOKING_CREATED` → move card
   para *Reunião Agendada* + confirma no WhatsApp.
4. **Lembrete + No-show** (esqueleto) — lembrete ao ganhar a tag REUNIAO-AGENDADA.

**Infra criada no tenant Master Clinic:**
- 11 tags do funil (via MCP `tag_create`) — IDs em `tag-ids.json`.
- IDs de stages/tags/instâncias embutidos nos `.dc` para ficarem funcionais.

**Integração Cal.com:** abordagem **link gerenciado + webhook** (não-nativo no DataCrazy).
O bot envia o link do event type do Dr. Wilton pré-preenchido com `name`/`email`; o
Cal.com devolve `BOOKING_CREATED` por webhook para a Automação 3.

**Canal WhatsApp:** deixado a definir (`instanceId` vazio nos `.dc`). O tenant tem
Evolution API (msg livre, reengajamento sem template) e Cloud API (exige template WABA).
A escolha muda só o reengajamento de 10 min; o resto roda igual dentro da janela.

## Alternativas Consideradas

- **Bot puxa slots via API do Cal.com e cria o booking no WhatsApp:** descartado nesta
  fase (mais frágil); mantido como evolução se a fricção do link se provar alta.
- **Duplicar a "cauda" de agendamento nas Automações 1 e 2:** descartado em favor de
  `start-another-automation` (sem duplicação; exige amarração manual pós-import).
- **Reengajar via template WABA (Cloud API):** viável e "by the book", mas o volume baixo
  de leads qualificados de tráfego pago justifica msg livre via Evolution (recomendado).
- **Escrever os `.dc` à mão:** descartado — gerador Python garante UUIDs e `nextBlockId`
  consistentes (validado: 0 conexões quebradas).

## Consequências

- 4 `.dc` prontos para importar **desativados**. Automações 1 e 2 completas; 3 e 4 são
  esqueletos que dependem de validar o payload/webhook do Cal.com com teste real.
- Exige **amarrações manuais** pós-import (instância, ligação Auto1→Auto2, link Cal.com,
  variável de nome, webhook Cal.com) — documentadas em `dc/README-importacao.md`.
- Textos usam valores provisórios de `[PROMESSA]`/`[PROVA]`/nome/duração — o Dr. Wilton
  ajusta depois de validar o funcionamento.
- A landing precisa criar o lead com source `LP-MENTORIA-WILTON` (ou tag equivalente).

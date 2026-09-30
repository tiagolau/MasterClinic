# 004 — Raspagem das conversas do DataCrazy e desenho do chatbot de tráfego

**Data:** 2026-07-29
**Status:** aceito

## Contexto

A Master Clinic roda tráfego pago (Click-to-WhatsApp) para os números da clínica, mas não
havia medição de o que acontece com esses leads depois do clique. Antes de desenhar qualquer
chatbot, era preciso saber: **quais conversas vieram de tráfego, o que os pacientes perguntam
e em que tom a clínica responde** — para que o bot fosse desenhado sobre o comportamento real
da recepção, e não sobre suposição.

Existe um chatbot já desenhado no tenant ([ADR 003](003-chatbot-agendamento-mentoria.md)), mas
ele é do funil **da mentoria para dentistas** — público, oferta e roteiro completamente
diferentes do paciente que procura procedimento odontológico.

## Decisão

**1. Raspagem completa via REST do DataCrazy**, com três scripts novos:

- [`scripts/raspar_conversas_datacrazy.py`](../../scripts/raspar_conversas_datacrazy.py) —
  baixa instâncias, leads, conversas e mensagens para `data/`.
- [`scripts/analisar_conversas.py`](../../scripts/analisar_conversas.py) — classifica origem
  e intenção, extrai perguntas e mede o funil.
- [`scripts/exportar_transcricoes.py`](../../scripts/exportar_transcricoes.py) — exporta
  transcrições legíveis filtradas por origem/assunto/canal.

Resultado: **1.687 conversas, 7.436 leads, 8 canais, 0 falhas**.

**2. Identificação de tráfego pela mensagem pré-preenchida do CTWA.** Os campos nativos
(`lead.source`, `lead.sourceReferral`) estão **vazios em 100% dos leads** e a tag "Tráfego Pago"
está poluída (aplicada em massa, inclusive em conversas internas e de cobrança). O sinal
confiável é o texto que o anúncio injeta na primeira mensagem — 7 variantes catalogadas.

**3. Entregáveis de análise e desenho:**
- [`docs/analise-conversas-trafego.md`](../analise-conversas-trafego.md) — diagnóstico com números.
- [`docs/fluxo-chatbot-trafego-agendamento.md`](../fluxo-chatbot-trafego-agendamento.md) —
  fluxo passo a passo com textos prontos no tom de voz extraído das conversas.

**4. Arquitetura do fluxo: bot qualifica, humano agenda.** A ordem de qualificação é
**cidade → convênio → procedimento → nome/turno → handoff**, deliberadamente colocando os dois
maiores filtros de descarte antes de qualquer esforço de atendimento.

## Alternativas Consideradas

- **Usar a tag "Tráfego Pago" como marcador de origem:** descartada — 533 leads marcados, mas a
  amostra mostrou conversas internas da equipe, cobrança de boleto e fornecedores com a mesma tag.
- **Usar `sourceReferral` da API:** inviável hoje — nulo em todos os 7.436 leads. Fica como
  correção recomendada na origem (CTWA/CAPI), não como base da análise.
- **Bot que agenda sozinho (via agenda integrada):** descartado nesta fase. A clínica opera a
  agenda manualmente, com encaixes e remanejamento diário ("Dr. Wilton pediu para te reagendar").
  Automatizar o slot exigiria integração de agenda que não existe.
- **Bot único para todos os canais:** descartado — o canal Gerência Uazapi recebe CTWA de
  **vaga de emprego** (19 das 118 conversas de tráfego). Fluxo de RH foi separado.
- **Bot responder com áudio, imitando a recepção:** descartado. O áudio é o padrão em Mesquita,
  mas a raspagem registrou perda explícita de lead por áudio ruim.
- **Ampliar o dicionário de procedimentos até classificar tudo:** desnecessário — 52% das
  conversas de tráfego morrem antes de o lead dizer o que quer. O problema não é classificar
  melhor, é responder mais rápido.

## Consequências

- Diagnóstico quantificado do vazamento: **17% dos leads de tráfego nunca são respondidos**,
  52% mandam uma única mensagem, 32% esperam mais de 1 hora (pior caso: 48h), 31% chegam fora
  do expediente, 18% são de fora da região e 20% vêm com objeção de convênio.
- O fluxo desenhado está pronto para virar `.dc`, com todos os IDs de pipeline, etapa e tag do
  tenant já mapeados. Falta criar apenas a tag `RH-CANDIDATO`.
- Ficam **cinco decisões abertas** antes da implementação (canal oficial vs. Uazapi, transcrição
  de áudio, rodízio de handoff, correção do rastreio CTWA/CAPI, limpeza da tag "Tráfego Pago").
- Limitações da API do DataCrazy documentadas no `CLAUDE.md`: paginação só por `take`/`skip`
  (máx. 1000), rate limit de 30 req/min e bloqueio do Cloudflare sem User-Agent de browser.
- `data/` contém dados pessoais de pacientes (nome, telefone, conteúdo de conversa) e **não deve
  ser versionado nem compartilhado** — é reprodutível pelo script a qualquer momento.

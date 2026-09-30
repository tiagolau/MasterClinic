# 002 — Pipeline de Mentoria para Dentistas (Dr. Wilton Vargas) no DataCrazy

**Data:** 2026-07-13
**Status:** aceito

## Contexto

O Dr. Wilton Vargas (Master Clinic) vai oferecer uma mentoria para dentistas.
O fluxo comercial parte de um formulário preenchido por interessados e termina
numa reunião de fechamento. Era preciso um funil no CRM para gerenciar esses
leads da captação até o fechamento.

Definições do usuário:
- **CRM:** DataCrazy (tenant Master Clinic `69937b06-43cd-40d2-bd39-d3d3c9223283`)
- **Captação:** formulário próprio em landing page (a construir em etapa futura)
- **Qualificação:** o próprio formulário qualifica o lead
- **Funil:** enxuto (5 etapas + Perdido)

## Decisão

Criada a pipeline **"Mentoria Dr. Wilton Vargas"** (grupo `Comercial`,
id `554040d1-43dc-42a1-9954-f349a0c12c49`) com 6 etapas:

| # | Etapa | Regra de entrada |
|---|---|---|
| 0 | Novo Lead | Formulário preenchido, ainda não triado |
| 1 | Qualificado | Respostas batem o perfil (dentista, momento, verba) |
| 2 | Reunião Agendada | Lead escolheu data/hora da reunião de fechamento |
| 3 | Reunião Realizada | Reunião aconteceu, aguardando decisão |
| 4 | Fechado / Matriculado | Comprou a mentoria |
| 5 | Perdido | Não qualificou / não compareceu / declinou |

### Como foi criada

- A **API REST** (`https://api.g1.datacrazy.io/api/v1`) é **read-only para a
  estrutura de pipelines** — `POST /pipelines` e `/pipelines/stages` retornam 404.
  Ela permite criar/mover **leads** (`POST /leads`) e **cards/negócios**
  (`POST /businesses`, exige `leadId` + `stageId`), o que será usado na
  integração do formulário numa etapa futura.
- A criação da pipeline foi feita via **MCP Server**
  (`https://mcp.g1.datacrazy.io/api/mcp`, JSON-RPC `tools/call`, Bearer token),
  tool `pipeline_create` (aceita `name`, `description`, `group`, `stages`
  separados por vírgula). O MCP precisou ser **habilitado no painel do tenant**
  antes (senão retorna HTTP 401 `MCP Server is not enabled for this tenant`).

## Alternativas Consideradas

- **Criar a pipeline via REST:** descartada — rota inexistente (404).
- **Criar as etapas manualmente no painel:** viável, mas o usuário optou por
  habilitar o MCP para destravar também automações futuras (disparo WhatsApp,
  `business_move_stage`, etc.) via API.
- **Funil de 7 etapas (com Contato Feito / Negociação):** descartado — como o
  formulário já qualifica, o funil enxuto é suficiente.

## Consequências

- Pipeline pronta para receber cards. Integração formulário → `/leads` →
  `/businesses` (stage "Novo Lead") fica para etapa futura, junto da landing e
  do agendamento — o usuário pediu para focar **somente na pipeline** por ora.
- **Cores das etapas** são atribuídas automaticamente pelo DataCrazy e **não são
  controláveis via API/MCP** (a tool só aceita nomes). "Novo Lead" e "Perdido"
  saíram com a mesma cor; ajuste semântico (verde=ganho, vermelho=perda) deve ser
  feito manualmente no painel se desejado.
- MCP Server agora habilitado no tenant Master Clinic — 80 tools disponíveis para
  automações futuras.

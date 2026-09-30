# MasterClinic

Projeto de gestão de templates WhatsApp Business API (WABA) e materiais de
comunicação para a clínica Master Clinic.

**Repositório:** https://github.com/tiagolau/MasterClinic (**privado**). Ficam fora do git
(`.gitignore`): `data/` e `logs/` (dados de pacientes), `*.csv`, `.env`, `.venv` e
`dc-monitor/*.dc` (tokens uazapi embutidos). **Nunca commitar token** — segredos vão no
`~/.claude/.env` (ex.: `UAZAPI_TOKEN_MASTERCLINIC_{MESQUITA,GERENCIA,FINANCEIRO}`). O deploy na
VPS Tecminas continua por `scp`, não por `git pull`.

## Stack

- **Python 3** para scripts de submissão WABA
- **Bash** para utilidades (geração de vídeo via Veo 3)
- **Graph API v25.0** da Meta para gerenciar templates WABA
- **Veo 3** (`veo-3.0-fast-generate-001`) para gerar mídias de headers

## Estrutura

```
.
├── docs/decisions/          # ADRs (Architecture Decision Records)
├── templates/templates.json # Catálogo de templates WABA com metadados
├── scripts/
│   ├── submeter_templates.py  # Envia templates para Graph API
│   └── gerar_videos_veo.sh    # Gera vídeos curtos via Veo 3
├── media/                   # Vídeos gerados (.mp4)
├── logs/                    # Logs de submissão e jobs Veo
└── gerar_proposta_templates.py  # (legado) Gerador de proposta DOCX
```

## WABAs da Master Clinic

Todas na BM `476121126154261`, todas `business_verification_status: not_verified`.
Levantamento e replicação de templates em 2026-08-10 (ver [ADR 012](docs/decisions/012-replicacao-templates-entre-wabas.md)):

| WABA ID | Nome | Número | Plataforma | Templates |
|---|---|---|---|---|
| `306417967823808` | Master Clinic Odontologia Especializada | +55 31 8686-8825 | CLOUD_API | 6 (origem do acervo) |
| `1350953883747065` | Master Clinic (Financeiro) | +55 31 9076-1166 | CLOUD_API | 6 |
| `616632296165144` | Financeiro - Recepção | +55 31 8469-7236 | CLOUD_API | 6 |
| `105152822451126` | Danielle Carvalho Master Clinic | +55 31 8489-1752 | CLOUD_API | 6 |
| `695879211426557` | Master clinic (Mesquita) | +55 33 9136-0115 | **ON_PREMISE** | 0 — bloqueada |
| `108400492289717` | Master Clinic Odontologia Especializada | +55 31 92006-8948 | **ON_PREMISE** | 0 — bloqueada |

⚠️ **WABAs `ON_PREMISE` não gerenciam templates.** POST devolve `code 100` /
`error_subcode 2494160` ("A conta do WhatsApp Business não tem permissão para
gerenciar modelos") — restrição da WABA, não do token. Só migrando o número para
Cloud API. A Meta valida **conteúdo antes de permissão**, então um payload
inválido nessas contas retorna erro de conteúdo e mascara o bloqueio real.

Replicar o acervo para uma WABA nova:

```bash
source ~/.claude/.env
python3 scripts/replicar_templates_waba.py --dry-run
python3 scripts/replicar_templates_waba.py --destino <waba_id>
```

O script re-sobe as mídias de header pela Resumable Upload API (a URL `scontent`
que o GET devolve **não** é aceita como `header_handle` no POST), é idempotente
por `(nome, idioma)` e loga em `logs/replicacao_TIMESTAMP.json`.

Histórico do bloqueio de escrita anterior: [docs/decisions/001](docs/decisions/001-submissao-templates-waba.md).

## DataCrazy CRM (Master Clinic)

- **Tenant:** `69937b06-43cd-40d2-bd39-d3d3c9223283` (name `gestao`, role admin). Token em `DATACRAZY_API_KEY_MASTERCLINIC` no `~/.claude/.env`. ⚠️ O token **inclui o prefixo `dc_`** — sem ele dá 401. Renovar em `crm.datacrazy.io/config/api` logado na Master Clinic (gerar token novo **revoga o anterior**).
- **Base REST:** `https://api.g1.datacrazy.io/api/v1` (auth `Authorization: Bearer`). Plano **Enterprise — REST liberada**. Cria/move `leads` e `businesses`, mas é **read-only para pipelines/stages** (POST 404).
- **Peculiaridades da REST** (descobertas na raspagem, ver [ADR 004](docs/decisions/004-raspagem-conversas-e-fluxo-trafego.md)):
  - **Cloudflare bloqueia (403 `error code: 1010`)** sem `User-Agent` de browser.
  - **Rate limit: 30 requisições/minuto** (429 `Too many requests`), janela de 1 min.
  - Paginação: `limit`/`page`/`offset` são **ignorados**; use `take` (máx. 1000) + `skip`.
  - **O filtro `pipelineId` de `GET /businesses` é ignorado** — retorna todos os negócios do tenant independente do filtro. Para saber o pipeline real de um negócio, use o campo aninhado `stage.pipeline` do próprio registro retornado (ver [ADR 006](docs/decisions/006-reestruturacao-funis-crm-master-clinic.md)).
  - Mensagens: `GET /conversations/{id}/messages` → `{messages, histories}`; `received: true` = lead, `false` = clínica.
  - `conversation.contact.externalId` é o **leadId** (não o telefone); o telefone está em `contact.phoneNumber`.
- **MCP Server:** `https://mcp.g1.datacrazy.io/api/mcp` (JSON-RPC `tools/call`, mesmo Bearer, stateless). **Habilitado** no tenant — 80 tools. Usar `pipeline_create`/`pipeline_stages_save` para estrutura de funil e `additional_field_create` para campos customizados (a REST não faz isso).
  - ⚠️ **O MCP aceita argumentos errados em silêncio**: retorna `success` e não faz nada. Sempre ler o `inputSchema` em `tools/list` antes de escrever em massa, e **conferir o resultado por GET na REST**. Exemplo real: `lead_add_tag`/`lead_remove_tag` usam `{id, tagIds}` com **`tagIds` em string separada por vírgula** — passar `{leadId, tagIds: [array]}` responde sucesso sem alterar nada.
  - ⚠️ **`lead_list_businesses` devolve campos achatados** (`pipelineId`, `stageId`, `stageName`, `pipelineName`), **sem** objeto `stage` — o oposto da REST, que aninha em `stage.pipeline`. Ler `b["stage"]["pipelineId"]` dá sempre `None`; foi isso que fez o sync Clinicorp criar 169 negócios duplicados ([ADR 014](docs/decisions/014-correcao-duplicacao-negocios-sync-clinicorp.md)).
  - ⚠️ **Rate limit do MCP não é HTTP 429**: vem `201` com `result.isError` e `"Too many requests"` no corpo. Tratar leitura com erro como "lista vazia" leva a criar duplicado — distinguir falha de ausência.
  - ⚠️ **`pipeline_stages_save` recusa apagar etapa com negócio associado** (`"Cannot delete stage X because it is associated with existing businesses"`). Para reestruturar etapas de um funil com dados reais, mova os negócios para outro funil/etapa temporário antes, restage, e devolva os negócios às etapas equivalentes novas.
- **Pipelines** (reestruturados em 2026-07-29, ver [ADR 006](docs/decisions/006-reestruturacao-funis-crm-master-clinic.md) — segue a [Especificação Técnica de CRM V2](docs/Especificação%20Técnica%20de%20Configuração%20e%20Matrificação%20do%20CRM%20V2.docx)):
  - **Mentoria Dr. Wilton Vargas** (`554040d1-43dc-42a1-9954-f349a0c12c49`, grupo `Comercial`): funil da mentoria para dentistas. 6 etapas: Novo Lead → Qualificado → Reunião Agendada → Reunião Realizada → Fechado / Matriculado (+ Perdido). Ver [docs/decisions/002](docs/decisions/002-pipeline-mentoria-dentistas-datacrazy.md).
  - **Funil Principal - Mesquita** (`7c922803-5c98-4733-9f72-55189ac97916`, grupo `Clínico`, ex-`Vendas - Mesquita`) e **Funil Principal - Ipatinga** (`10cd55a8-b076-4119-b3bc-333b295f5a42`, grupo `Clínico`, ex-`Vendas - Ipatinga`): Agendamento (Entrada) → Avaliação Realizada → Agendamento 2ª Consulta e Follow-up → Orçamento (2ª Consulta) → Ganho / Perdido.
  - **Acompanhamento - Mesquita** (`b08016d6-61a1-4341-bb90-181a432423d9`) e **Acompanhamento - Ipatinga** (`8c829b9e-3b13-4af8-9187-0d7b9569d42e`), grupo `Pós-Venda`: Avaliação de Atendimento → Em Tratamento / Manutenção → Retorno de Rotina.
  - **Aniversariantes - Mesquita** (`d7aa2f46-d3ad-422b-b700-ae77b0d7c71e`) e **Aniversariantes - Ipatinga** (`82f1cf60-ee0d-4e9c-b458-8dc774ba4318`), grupo `Relacionamento`: Mês do Aniversário → Contato Realizado → Convertido / Não Convertido. **Bloqueado** — depende de sincronização com Clinicorp (sem credenciais no ambiente ainda). Ver [docs/spec-automacao-clinicorp-aniversariantes.md](docs/spec-automacao-clinicorp-aniversariantes.md).
  - **Agendamentos** (`d0d8b215-5340-4d4e-a5e9-485d726a267f`, grupo `Operações`): Solicitado → Agendado → Confirmado → Concluído → Falta.
  - **Campos customizados de metrificação** (grupo "Metrificação Comercial"): Status da Avaliação Inicial, Contador de Follow-ups, Data do Agendamento da Segunda Consulta, Origem do Lead (Canal/UTM, entity `lead`), Dentista/Avaliador Responsável, Forma de Pagamento Pretendida, Tipo de Procedimento. Opções são valores padrão de clínica odontológica — revisar no painel se não baterem com a equipe/formas de pagamento reais. Motivo de Perda usa os 8 motivos nativos já existentes (`loss_reason_list`); Valor do Orçamento usa o campo nativo `business.total`.
- **Canais conectados (8):** `Oficial Master Clinic` (Cloud API, WABA `306417967823808` — canal principal de tráfego), `Recepção Master Clinic` (Cloud API, +55 31 8469-7236), `CRC Master Clinic` (inativo), `Mesquita Uazapi`, `Gerência Uazapi` (recebe CTWA de **vaga de emprego**), `Financeiro` (Uazapi), Instagram e Messenger `@drwiltonvargas.dentista`.

## Chatbot de tráfego pago → agendamento (WhatsApp)

Bot de trilho por botões que assume a conversa quando um card nasce na etapa
**Agendamento (Entrada)** do Funil Principal da unidade, vende a avaliação e faz o
handoff para a recepção. Gerado por [`scripts/gerar_dc_trafego.py`](scripts/gerar_dc_trafego.py)
em [`dc-trafego/`](dc-trafego/) (4 arquivos `.dc`, 2 por unidade: chatbot + resgate). Ver
[ADR 005](docs/decisions/005-chatbot-trafego-por-unidade.md) (desenho) e
[ADR 006](docs/decisions/006-reestruturacao-funis-crm-master-clinic.md) (correção do
gatilho após a reestruturação dos funis). Importação manual em
[dc-trafego/README-importacao.md](dc-trafego/README-importacao.md) — sem API MCP para
editar automação já importada, então qualquer mudança de estágio/gatilho exige reimportar.

## Monitor de desconexão das instâncias uazapi

Alerta no WhatsApp quando uma instância uazapi cai. Webhook `connection` da uazapi →
gatilho HTTP de uma automação DataCrazy → debounce 3 min → `GET /instance/status`
confirma → alerta por uma instância **diferente** da que caiu. Gerado por
[`scripts/gerar_dc_monitor_instancias.py`](scripts/gerar_dc_monitor_instancias.py) em
[`dc-monitor/`](dc-monitor/). Ver [ADR 007](docs/decisions/007-monitor-instancias-uazapi.md)
e [dc-monitor/README-importacao.md](dc-monitor/README-importacao.md).

**Servidor uazapi:** `https://masterclinic.uazapi.com` (auth: header `token: <token da instância>`;
tokens em `config.token` de `instance_list` no MCP do DataCrazy). Doc: `docs.uazapi.com`, OpenAPI
real em `https://docs.uazapi.com/openapi-bundled.json`.

⚠️ **A uazapi aceita múltiplos webhooks por instância, mas só com `action: "add"`.** `POST /webhook`
sem `action` entra no "modo simples" e **sobrescreve** o webhook existente — que é o
`messaging.g1.datacrazy.io/webhooks/uazapi/{tenant}/{instanceId}` que entrega as mensagens ao CRM.
Sobrescrever derruba o atendimento das 3 unidades. Sempre conferir com `GET /webhook` depois.

## Painel comercial realtime (dashboard/)

Dashboard que cruza Meta Ads → DataCrazy → Clinicorp com IA diagnóstica
diária. FastAPI + Postgres + frontend estático. **EM PRODUÇÃO:**
https://painel.mapeamento.online (domínio provisório; senha em
`PAINEL_MC_PASSWORD` no `~/.claude/.env`), stack `painel-mc` na **VPS Tecminas**
(`173.212.205.156`, creds `VPS_TECMINAS_*`), código em `/opt/painel-mc`, Traefik
rede `Mapeamento` + `letsencryptresolver`. IA = Gemini do cliente
(`GEMINI_API_KEY_MASTERCLINIC`, conta só acessa modelos gemini-3+; em uso
`gemini-3-flash-preview`). Digest diário 20h30 → WhatsApp da Gerência via
instância Mesquita. Ver [ADR 008](docs/decisions/008-painel-comercial-realtime.md),
[ADR 009](docs/decisions/009-integracao-clinicorp-painel.md),
[ADR 010](docs/decisions/010-deploy-painel-vps-tecminas.md),
[ADR 011](docs/decisions/011-identidade-visual-painel.md) e
[dashboard/README.md](dashboard/README.md).

⚠️ **Cores do painel são validadas, não escolhidas no olho.** Verde da marca
`#008E45` (extraído do site oficial), séries e rampa do funil aprovadas em
`validate_palette.js` da skill `dataviz` (`--mode dark --surface #1a1a19`).
Qualquer troca de cor de série precisa passar pelo validador antes de subir —
ver [ADR 011](docs/decisions/011-identidade-visual-painel.md).

- **Sync:** incremental 5 min (listas do DataCrazy vêm ordenadas desc → pagina até
  watermark), sweep completo 60 min, Meta insights por ad/dia (janelas grandes dão
  500 no Graph — buscar 1 dia por vez). Seed inicial via `python -m app.seed data/`.
- **Atribuição:** cascata anotação X1 → collector `POST /ingest/ctwa` (bloco `api`
  a adicionar no fluxo X1) → heurística CTWA. A REST de mensagens NÃO expõe
  `ctwaClid`/ad — confirmado.
- **IA:** job diário 20h30, Claude ou Gemini (`AI_PROVIDER=auto`), JSON estruturado
  + digest WhatsApp via uazapi (`DIGEST_PHONES`).
- **Ad accounts:** tráfego de pacientes = `act_146238145960571` (client da BM
  `476121126154261`); mentoria = `act_256216457271970`.
- Rodar local: Postgres via brew (`brew services start postgresql@17`), venv em
  `dashboard/.venv`, `DATABASE_URL=postgresql://tiagolau@localhost:5432/painel`.

## Clinicorp (API — validada 2026-08-04)

- **Auth:** Basic (`CLINICORP_API_USER=masterclinic` + `CLINICORP_API_TOKEN`, no
  `~/.claude/.env`), sempre com `subscriber_id=masterclinic` na query.
- **Base:** `https://api.clinicorp.com/rest/v1`. Endpoints validados:
  `GET /business/list` (clínica `5499925683503104`) e
  `GET /appointment/list?from=...&to=...` (`PatientName`, `MobilePhone`,
  `CheckinTime` em **epoch ms** = compareceu, `FirstAppointment`). Buscar **1 dia
  por requisição** — range grande corta a resposta. `patient/list` e
  `patient/list_birthdays` NÃO existem com esses nomes (404); endpoint de
  pacientes ainda por descobrir (necessário pro funil Aniversariantes).
- Ver [ADR 009](docs/decisions/009-integracao-clinicorp-painel.md).
- **Sem webhook de saída** na API (testado: `webhook*`, `subscription/list`, `event/list` → 404).
  Status da agenda em `GET /appointment/status_list` (`CONFIRMED`, `CHECKOUT` = Atendido,
  `MISSED` = Faltou etc.); cada agendamento tem `StatusId` e `z_LastChange_Date`.

### Sync Clinicorp → DataCrazy (cron na VPS Tecminas)

[`scripts/cron_sync_clinicorp_datacrazy.py`](scripts/cron_sync_clinicorp_datacrazy.py), a cada
10 min em `/etc/cron.d/sync_clinicorp_datacrazy`, log em `/var/log/clinicorp_datacrazy_sync.log`.
Move os cards do Funil Principal/Agendamentos conforme a agenda, grava orçamento e ganho, e cria o
card de Acompanhamento no pagamento. **Só cria negócio se o lead não tiver nenhum naquele funil;
senão move o aberto mais antigo.** Ver [ADR 013](docs/decisions/013-sincronizacao-continua-clinicorp-datacrazy.md)
e [ADR 014](docs/decisions/014-correcao-duplicacao-negocios-sync-clinicorp.md).

## Análise de conversas e chatbot de tráfego

Raspagem completa das conversas (1.687 conversas, 7.436 leads) e desenho do fluxo de
chatbot para leads de tráfego pago. Ver [ADR 004](docs/decisions/004-raspagem-conversas-e-fluxo-trafego.md).

```bash
source ~/.claude/.env
python3 scripts/raspar_conversas_datacrazy.py        # baixa tudo para data/ (~1h, 30 req/min)
python3 scripts/analisar_conversas.py --json         # relatório + data/analise.json
cd scripts && python3 exportar_transcricoes.py --trafego --assunto paciente --n 20
```

- [docs/analise-conversas-trafego.md](docs/analise-conversas-trafego.md) — diagnóstico com números
- [docs/fluxo-chatbot-trafego-agendamento.md](docs/fluxo-chatbot-trafego-agendamento.md) — fluxo com textos prontos

⚠️ **`data/` contém dados pessoais de pacientes** — não versionar nem compartilhar. É reprodutível pelo script.

**Como identificar tráfego:** `lead.source` e `lead.sourceReferral` estão **vazios em 100%** dos leads
e a tag "Tráfego Pago" está poluída. O sinal confiável é a **mensagem pré-preenchida do Click-to-WhatsApp**
na primeira mensagem do lead (7 variantes catalogadas em `ABERTURAS_CTWA` no analisador).

## Trackeamento CAPI (CTWA) — instâncias uazapi

Fluxo `X1 Uazapi` envia `LeadSubmitted` para a Meta quando o lead chega por anúncio
click-to-WhatsApp. Roteador JS `instanceId → {waba, dataset}`; token CAPI único (System User
`122116067186885827` da BM `476121126154261`). Ver [docs/decisions/003](docs/decisions/003-trackeamento-capi-uazapi-multi-instancia.md).

| Instância | Nome | Número | WABA | Dataset |
|---|---|---|---|---|
| `6a60fb2d9afe657f0c991354` | Mesquita | 55 33 9136-0115 | `695879211426557` | `1431423535578167` |
| `6a60fa47daf8b7fddb04ee7f` | Gerência | 55 31 8489-1752 | `105152822451126` | `1036765985424876` |
| `6a60fb7a9afe657f0c999799` | Financeiro | 55 31 9076-1166 | `1350953883747065` | `1834437841272372` |

Payload uazapi ≠ Cloud API: o clid vem em `content.contextInfo.externalAdReply.ctwaClid`
(não em `referral.ctwa_clid`) e o ad id em `...externalAdReply.sourceID`.

## Padrões de template adotados

- Variáveis **numeradas** (`{{1}}`, `{{2}}`), numeração começa em 1 dentro de cada componente
- **Sem emojis** no body — assinatura institucional pura
- Quick Reply com **descarte gentil** ("Bloquear contato", "Não tenho mais interesse") em templates de alto volume
- Footer "Master Clinic — Atendimento" em templates de tom formal
- 7 esqueletos diferentes do catálogo `~/.claude/skills/templates-waba/references/esqueletos-aprovados.md` pra variar estrutura e proteger quality rating

## Submeter templates

```bash
cd /Users/tiagolau/Devs/MasterClinic
source ~/.claude/.env
python3 scripts/submeter_templates.py --apenas-sem-video    # 12 templates sem header VIDEO
python3 scripts/submeter_templates.py --apenas-com-video    # T05 + T10 (requer HANDLE_VIDEO_* env)
python3 scripts/submeter_templates.py                       # tudo
```

Logs em `logs/submit_TIMESTAMP.json`.

## Variáveis de ambiente

Carregadas via `~/.claude/.env`:
- `FB_ACCESS_TOKEN` — token Graph API (escopo `whatsapp_business_management`)
- `GOOGLE_API_KEY` — Veo 3
- `HANDLE_VIDEO_RECEPCAO`, `HANDLE_VIDEO_DR_WILTON` — preenchidas após upload das mídias

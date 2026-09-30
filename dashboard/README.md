# Painel Master Clinic

Dashboard comercial em tempo quase-real que cruza a jornada completa do paciente:

```
Anúncio Meta ──▶ Conversa WhatsApp ──▶ Lead/Funil DataCrazy ──▶ (fase 2: Clinicorp)
```

- **Sync incremental** do DataCrazy a cada 5 min (leads, conversas, mensagens, negócios) respeitando o rate limit de 30 req/min
- **Insights Meta Ads** por anúncio/dia (gasto, conversas iniciadas, leads CAPI)
- **Classificação automática** de conversas (tráfego × orgânico, paciente × vaga × fornecedor, procedimento citado, pediu preço, SLA de resposta) — mesma heurística validada do ADR 004
- **Oportunidades em aberto** determinísticas (lead esperando resposta, negócio estagnado)
- **Diagnóstico diário por IA** (Claude ou Gemini): lê as conversas do dia e aponta oportunidades, alertas de atendimento e leitura de tráfego — com resumo enviado no WhatsApp via uazapi
- **Collector CTWA** (`POST /ingest/ctwa`) para atribuição por anúncio alimentada pelo fluxo X1 do DataCrazy

## Rodar local

```bash
cd dashboard
cp .env.example .env    # preencher
docker compose up --build -d
# seed inicial com a raspagem já existente (evita ~1h de API):
docker compose exec app python -m app.seed /caminho/do/data   # ou ver "Seed" abaixo
open http://localhost:8000
```

Sem seed, o app detecta o banco vazio e faz a carga completa sozinho pela API
(~1h por causa do rate limit). Com seed, só baixa o delta.

### Seed a partir da raspagem local

O diretório `data/` do repositório (gerado por `scripts/raspar_conversas_datacrazy.py`)
pode ser importado direto:

```bash
# com o Postgres do compose de pé:
DATABASE_URL=postgresql://painel:painel@localhost:5433/painel \
  python3 -m app.seed ../data
```

## Deploy na VPS (Docker Swarm + Traefik)

```bash
# do Mac → VPS (o projeto não está em git remoto; copiar direto)
rsync -av --exclude .venv --exclude .env dashboard/ root@SUA_VPS:/opt/painel-mc/

# na VPS
cd /opt/painel-mc
cp .env.example .env && vim .env       # preencher tudo
docker build -t painel-mc:latest .
env $(grep -v '^#' .env | xargs) docker stack deploy -c stack.yml painel-mc
```

Pré-requisitos: Swarm ativo, rede externa `traefik-public` com Traefik + Let's Encrypt
(padrão das minhas VPS — ver skill `vps-docker-swarm`), DNS de `PAINEL_DOMAIN`
apontando pra VPS.

Atualização:

```bash
git pull && docker build -t painel-mc:latest . && docker service update --force painel-mc_app
```

## Atribuição por anúncio (collector CTWA)

A REST do DataCrazy não expõe o `ctwa_clid`/ad_id das mensagens. Para atribuição
exata por anúncio, o fluxo **X1 Uazapi** (que já captura esses campos para a CAPI)
ganha um bloco `api` extra que chama o collector:

- **URL:** `https://SEU_DOMINIO/ingest/ctwa`
- **Método:** POST · **Header:** `Authorization: Bearer <INGEST_TOKEN>`
- **Body (JSON):**

```json
{
  "telefone": "{{telefone do lead}}",
  "instanceId": "{{instanceId da sessão}}",
  "ctwaClid": "{{[Javascript-1]resultado ou campo do clid}}",
  "adId": "{{sourceID do criativo}}",
  "messageTimestamp": "{{messageTimestamp}}"
}
```

Posicionar o bloco em paralelo ao envio CAPI (depois do guard de `dataset_id`),
com `errorNextBlockId` apontando pro fluxo normal — falha no collector não pode
travar o trackeamento. Enquanto o bloco não existir, o painel ainda classifica
tráfego pela mensagem CTWA e pelas anotações do X1 (quando presentes); só a
quebra por anúncio individual fica sem dado.

## Endpoints

| Rota | Uso |
|---|---|
| `GET /` | dashboard (senha via `DASHBOARD_PASSWORD`) |
| `POST /api/login` | `{senha}` → cookie de sessão (30 dias) |
| `GET /api/health` | status do banco + últimas sincronizações (sem auth) |
| `GET /api/resumo?dias=30` | métricas, série, funis, campanhas, oportunidades |
| `GET /api/diagnosticos?n=7` | diagnósticos de IA salvos |
| `POST /api/diagnostico/rodar` | gera diagnóstico agora |
| `POST /api/sync/rodar` | `{tipo: incremental\|completo\|meta}` |
| `GET /api/conversa/{id}` | transcript para o modal |
| `POST /ingest/ctwa` | collector de atribuição (Bearer `INGEST_TOKEN`) |

## Jobs agendados

| Job | Frequência | O que faz |
|---|---|---|
| `sync_incremental` | 5 min | conversas/negócios/leads novos + mensagens com atividade |
| `sync_completo` | 60 min | sweep integral + pipelines/instâncias |
| `sync_meta` | 60 min | insights por ad dos últimos 3 dias (rejanela) |
| `diagnostico` | diário `DIAGNOSTICO_HORA`:30 | IA + digest WhatsApp |

## Variáveis de ambiente

Ver [.env.example](.env.example). Obrigatórias: `DATACRAZY_API_KEY_MASTERCLINIC`,
`DASHBOARD_PASSWORD`, `SECRET_KEY`, `POSTGRES_PASSWORD` (deploy). O diagnóstico IA
usa `ANTHROPIC_API_KEY` (preferido) ou `GEMINI_API_KEY`.

⚠️ O banco replica conversas de pacientes (dados pessoais). Não expor o Postgres,
não versionar dumps.

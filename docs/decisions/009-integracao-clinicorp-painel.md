# 009 — Integração Clinicorp no painel comercial (fase 2)

**Data:** 2026-08-04
**Status:** aceito

## Contexto

O painel comercial (ADR 008) fechava a jornada só até o funil do DataCrazy — a
ponta "consulta agendada → paciente compareceu" dependia do Clinicorp, sem
credenciais até então. Em 2026-08-04 o cliente entregou o acesso à API
(usuário API `masterclinic` + token), salvo em `CLINICORP_API_USER` /
`CLINICORP_API_TOKEN` no `~/.claude/.env`.

## Decisão

### API Clinicorp (validada em produção)

- **Base:** `https://api.clinicorp.com/rest/v1` — **Basic auth**
  (`usuário:token`), sempre com `subscriber_id=masterclinic` na query.
- `GET /business/list` → clínica (id `5499925683503104`, CARVALHO E VARGAS /
  Master Clinic, Ipatinga).
- `GET /appointment/list?from=YYYY-MM-DD&to=YYYY-MM-DD` → agendamentos com
  `PatientName`, `MobilePhone`, `Procedures`, `CategoryDescription`,
  `CheckinTime` (**epoch ms** — presença = compareceu), `FirstAppointment`,
  `StatusId`, `Clinic_BusinessId`.
- Range grande numa chamada só corta a resposta — o sync busca **1 dia por
  requisição** (mesmo padrão do sync Meta).
- `patient/list` e `patient/list_birthdays` **não existem** nesses nomes
  (404) — endpoint de pacientes/aniversariantes fica para descoberta futura
  (relevante para o funil Aniversariantes, ainda bloqueado).

### Integração no painel

- `app/clinicorp.py` (cliente) + `app/sync_clinicorp.py` (job a cada 30 min,
  janela −7d/+14d) → tabela `clinicorp_agendamentos` (telefone normalizado
  para dígitos; `CheckinTime` convertido para `HH:MM` local).
- **Cruzamento da jornada por telefone** (últimos 8 dígitos): agenda ×
  `conversas` do CRM → cada consulta mostra se o paciente está no CRM e se a
  conversa é de tráfego. Métricas: consultas/dia, comparecimentos, primeiras
  consultas, consultas vindas de tráfego.
- **Dashboard:** tile "Consultas hoje" + cartão "Agenda Clinicorp" (hora,
  paciente, procedimento, categoria, origem, check-in em verde; linha clicável
  abre o transcript quando há conversa no CRM).
- **IA diagnóstica:** o material diário agora inclui a agenda do dia com
  status de comparecimento — habilita alertas de no-show e correlação
  conversa × consulta.

## Alternativas Consideradas

- **Webhook do Clinicorp:** não investigado nesta fase — polling de 30 min
  atende (agenda muda em ritmo humano).
- **Cruzamento por nome do paciente:** rejeitado — telefone é chave natural e
  já normalizada nos dois lados; nome tem grafia inconsistente.

## Consequências

- Jornada completa no painel: anúncio → conversa → funil → **consulta →
  comparecimento**. Validado com dados reais: 261 agendamentos na janela,
  20 hoje, 5 check-ins, cruzamento acusando pacientes presentes no CRM.
- `de_trafego` usa só `origem='trafego'` (sinal forte); pacientes com a tag
  poluída "Tráfego Pago" aparecem como "no CRM", não como tráfego — coerente
  com o ADR 004.
- Falta receita/orçamento do Clinicorp (endpoint financeiro não descoberto) —
  ROI monetário ainda depende do `business.total` do DataCrazy.
- O funil Aniversariantes (spec própria) continua bloqueado só pela falta do
  endpoint de pacientes — a autenticação já está resolvida.

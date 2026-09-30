-- Schema do painel Master Clinic (Postgres 15+)
-- Aplicado automaticamente no boot do app (idempotente).

CREATE TABLE IF NOT EXISTS sync_state (
    chave         text PRIMARY KEY,
    valor         jsonb NOT NULL DEFAULT '{}'::jsonb,
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS instancias (
    id            text PRIMARY KEY,
    nome          text,
    plataforma    text,
    provider      text,
    numero        text,
    dados         jsonb,
    sync_em       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pipelines (
    id            uuid PRIMARY KEY,
    nome          text,
    grupo         text,
    dados         jsonb,
    sync_em       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS etapas (
    id            uuid PRIMARY KEY,
    pipeline_id   uuid,
    nome          text,
    ordem         int,
    dados         jsonb,
    sync_em       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
    id            uuid PRIMARY KEY,
    nome          text,
    telefone      text,
    email         text,
    criado_em     timestamptz,
    atualizado_em timestamptz,
    fonte         text,          -- lead.source (vazio em ~100% hoje, mas fica pronto)
    tags          jsonb,
    dados         jsonb,
    sync_em       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_leads_telefone ON leads (telefone);
CREATE INDEX IF NOT EXISTS idx_leads_criado ON leads (criado_em);

CREATE TABLE IF NOT EXISTS conversas (
    id                     text PRIMARY KEY,
    nome                   text,
    telefone               text,
    lead_id                uuid,
    instancia_id           text,
    instancia_nome         text,
    criada_em              timestamptz,
    ultima_msg_em          timestamptz,
    ultima_msg_recebida_em timestamptz,
    finalizada             boolean,
    dados                  jsonb,
    -- classificação (recalculada a cada sync de mensagens)
    origem                 text,      -- trafego | tag_trafego | organico | desconhecida
    evidencia_origem       text,
    assunto                text,      -- paciente | vaga | fornecedor
    procedimentos          jsonb,
    pediu_preco            boolean,
    chegou_agendamento     boolean,
    primeira_msg_lead      text,
    n_msgs                 int,
    n_lead                 int,
    n_clinica              int,
    resposta_min           numeric,   -- minutos até a 1ª resposta da clínica
    ultima_msg_de_lead     boolean,   -- true = bola está com a clínica
    ad_id                  text,      -- atribuição: anotação X1 ou collector
    ctwa_clid              text,
    msgs_sync_em           timestamptz,
    sync_em                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conversas_criada ON conversas (criada_em);
CREATE INDEX IF NOT EXISTS idx_conversas_ultima ON conversas (ultima_msg_em);
CREATE INDEX IF NOT EXISTS idx_conversas_telefone ON conversas (telefone);

CREATE TABLE IF NOT EXISTS mensagens (
    id            text PRIMARY KEY,
    conversa_id   text NOT NULL,
    corpo         text,
    recebida      boolean,       -- true = lead, false = clínica
    interna       boolean,
    criada_em     timestamptz,
    dados         jsonb
);
CREATE INDEX IF NOT EXISTS idx_mensagens_conversa ON mensagens (conversa_id, criada_em);

CREATE TABLE IF NOT EXISTS negocios (
    id                 uuid PRIMARY KEY,
    lead_id            uuid,
    etapa_id           uuid,
    status             text,          -- in_process | won | lost (conforme API)
    total              numeric,
    criado_em          timestamptz,
    atualizado_em      timestamptz,
    movido_em          timestamptz,
    status_alterado_em timestamptz,
    motivo_perda_id    text,
    dados              jsonb,
    sync_em            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_negocios_etapa ON negocios (etapa_id);
CREATE INDEX IF NOT EXISTS idx_negocios_lead ON negocios (lead_id);
CREATE INDEX IF NOT EXISTS idx_negocios_criado ON negocios (criado_em);

CREATE TABLE IF NOT EXISTS meta_insights (
    data                date NOT NULL,
    conta               text NOT NULL,
    campanha_id         text,
    campanha            text,
    adset_id            text,
    adset               text,
    ad_id               text NOT NULL,
    ad                  text,
    gasto               numeric DEFAULT 0,
    impressoes          bigint DEFAULT 0,
    cliques             bigint DEFAULT 0,
    conversas_iniciadas int DEFAULT 0,   -- onsite_conversion.messaging_conversation_started_7d
    leads_meta          int DEFAULT 0,   -- action_type = lead (CAPI LeadSubmitted)
    dados               jsonb,
    sync_em             timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (data, ad_id)
);
CREATE INDEX IF NOT EXISTS idx_meta_data ON meta_insights (data);

-- Collector de CTWA (alimentado pelo fluxo X1 do DataCrazy via POST /ingest/ctwa)
CREATE TABLE IF NOT EXISTS ctwa_eventos (
    id           bigserial PRIMARY KEY,
    recebido_em  timestamptz NOT NULL DEFAULT now(),
    telefone     text,
    instancia_id text,
    ctwa_clid    text,
    ad_id        text,
    msg_ts       timestamptz,
    dados        jsonb
);
CREATE INDEX IF NOT EXISTS idx_ctwa_telefone ON ctwa_eventos (telefone);

-- Agendamentos do Clinicorp (fase 2 — fecha a jornada até a cadeira)
CREATE TABLE IF NOT EXISTS clinicorp_agendamentos (
    id                 bigint PRIMARY KEY,
    paciente           text,
    paciente_id        bigint,
    telefone           text,          -- só dígitos
    data               date,
    hora_ini           text,
    hora_fim           text,
    procedimentos      text,
    categoria          text,
    status_id          bigint,
    checkin_em         text,          -- CheckinTime — preenchido = compareceu
    primeira_consulta  boolean,
    clinica_id         bigint,
    dentista_id        bigint,
    dados              jsonb,
    sync_em            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cc_ag_data ON clinicorp_agendamentos (data);
CREATE INDEX IF NOT EXISTS idx_cc_ag_tel ON clinicorp_agendamentos (telefone);

-- Pagamentos recebidos (Clinicorp) — a "venda realizada" da clínica.
-- payment/list filtra por ReceivedDate; não há endpoint de orçamento na API.
CREATE TABLE IF NOT EXISTS clinicorp_pagamentos (
    id             bigint PRIMARY KEY,
    paciente_id    bigint,
    paciente       text,
    valor          numeric,
    recebido_em    date,          -- ReceivedDate (base do filtro e das métricas)
    pago_em        timestamptz,   -- PaymentDate
    forma          text,          -- Boleto / Cartão de Crédito / Pix / ...
    tipo           text,          -- BOLETO_INTERNAL / CREDIT_CARD_EXTERNAL / ...
    parcela        int,
    parcelas       int,
    cancelado      boolean,
    recebido       boolean,
    clinica_id     bigint,
    dados          jsonb,
    sync_em        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cc_pag_data ON clinicorp_pagamentos (recebido_em);
CREATE INDEX IF NOT EXISTS idx_cc_pag_paciente ON clinicorp_pagamentos (paciente_id);

-- Cache de pacientes: patient/get?PatientId=X devolve o telefone, que é a chave
-- para ligar o pagamento à conversa do CRM (e daí ao anúncio de origem).
CREATE TABLE IF NOT EXISTS clinicorp_pacientes (
    id          bigint PRIMARY KEY,
    nome        text,
    telefone    text,          -- só dígitos
    email       text,
    nascimento  text,
    dados       jsonb,
    sync_em     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cc_pac_tel ON clinicorp_pacientes (telefone);

CREATE TABLE IF NOT EXISTS diagnosticos (
    id                bigserial PRIMARY KEY,
    data              date UNIQUE NOT NULL,
    gerado_em         timestamptz NOT NULL DEFAULT now(),
    modelo            text,
    resumo            text,
    json              jsonb,
    enviado_whatsapp  boolean NOT NULL DEFAULT false
);

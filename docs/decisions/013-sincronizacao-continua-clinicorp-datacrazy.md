# 013 — Sincronização Contínua de Ciclo de Vida Clinicorp ⇄ DataCrazy

**Data:** 2026-09-24  
**Status:** aceito e em produção  

## Contexto

A Master Clinic utiliza o Clinicorp como software de gestão odontológica (PMS/prontuário/agenda) e o DataCrazy como CRM comercial e de atendimento omnichannel. Identificou-se que centenas de pacientes com histórico clínico e agendamentos no Clinicorp não possuíam lead correspondente no DataCrazy, impedindo o acompanhamento de funil, métricas de no-show, régua de relacionamento e remarketing.

Além disso, as movimentações de etapas comerciais no DataCrazy dependiam de operação manual dos atendentes, gerando desatualização entre o que acontecia na recepção/clínica e o status dos cards nos funis do CRM.

## Decisão

### 1. Diagnóstico e Carga Inicial em Lote
- Varredura de agendamentos no Clinicorp de 2024 a 2026 identificou **1.934 pacientes únicos**.
- Cruzamento por telefone normalizado (DDI 55 + DDD + celular de 9 dígitos) apontou **1.432 pacientes já presentes (74%)** e **502 ausentes (26%)**.
- Foi criada a tag oficial **`Clinicorp`** (`ffbd0c5a-f63b-4c66-855a-99181c529a5f`) no DataCrazy.
- Desenvolvido o script [`scripts/sincronizar_clinicorp_datacrazy.py`](../../scripts/sincronizar_clinicorp_datacrazy.py) com throttle estrito de 2,2s (< 30 req/min) e enriquecimento de perfil (`patient/get` para e-mail limpo e CPF).
- **Resultado da carga inicial:** 502 pacientes inseridos no DataCrazy com 100% de sucesso (tags `Clinicorp` e `Paciente Ativo`), registrado em `logs/sincronizacao_clinicorp_datacrazy.json`.

### 2. Investigação de Webhooks do Clinicorp
- A análise da especificação oficial da API do Clinicorp (Swagger v1 em `https://sistema.clinicorp.com/api-docs/`) revelou que **não há endpoint REST público para cadastro/gerenciamento de webhooks de saída**. O endpoint `/crm/add_leads` é apenas de entrada (recebe leads externos no Clinicorp).
- Webhooks de saída do Clinicorp dependem de solicitação manual ao suporte/gerente de contas da plataforma.
- Para não travar a operação nem depender de terceiros, optou-se por uma arquitetura de sincronização recorrente por polling inteligente em alta frequência.

### 3. Automação do Ciclo de Vida em 3 Fases
Desenvolvido o motor inteligente [`scripts/cron_sync_clinicorp_datacrazy.py`](../../scripts/cron_sync_clinicorp_datacrazy.py) que conecta as duas plataformas em 3 fases:

#### Fase 1: Agendamentos & Avaliações
- Janela de busca móvel: de **3 dias no passado até 7 dias no futuro**.
- Cria o lead automaticamente se não existir no DataCrazy.
- Se 1ª consulta (`FirstAppointment == "X"`):
  - No **Funil Principal** (`7c922803...`), cria ou move o card para **`Avaliação Agendada`** (`e9839ca5...`).
  - No **Funil Agendamentos** (`d0d8b215...`), cria o card em **`Agendado`** (`c7bc5ab9...`) ou **`Confirmado`** (`1feb298d...`) caso `PatientConfirm == "X"`.
- Se 2ª consulta / retorno:
  - No Funil Principal, move para **`Agendamento 2ª Consulta e Follow-up`** (`64e5e4ee...`).

#### Fase 2: Presença (Check-in) e No-Show (Faltas)
- Para consultas com horário chegado ou ultrapassado:
  - Se `CheckinTime` preenchido (paciente fez check-in no totem/balcão):
    - Funil Principal ➔ move para **`Avaliação Realizada`** (`217e02d4...`).
    - Funil Agendamentos ➔ move para **`Concluído`** (`ad95f43b...`).
  - Se horário passou sem `CheckinTime` (faltou / cancelou):
    - Funil Principal ➔ move para **`Follow-Up Humanizado`** (`a7a9d4ca...`) para resgate pela recepção.
    - Funil Agendamentos ➔ move para **`Falta`** (`b1a06f1e...`).

#### Fase 3: Orçamentos, Fechamento e Pós-Venda
- **Orçamentos (`GET /estimates/list`):**
  - Identifica propostas emitidas no Clinicorp.
  - Funil Principal ➔ move para **`Orçamento (2ª Consulta)`** (`1c0188a1...`) e atualiza o total do negócio (`business.total`) com o valor em R$ da proposta.
- **Pagamentos / Contratos Fechados (`GET /payment/list`):**
  - Identifica pagamentos confirmados (`PaymentReceived == "X"`).
  - Funil Principal ➔ negócio é marcado como **`Ganho`** (`8c2aab90...`).
  - Funil Acompanhamento (Mesquita ou Ipatinga) ➔ cria card em **`Avaliação de Atendimento`** (`11b4aafe...` / `4291c947...`) para iniciar a pesquisa de satisfação e pós-venda.

### 4. Cache Inteligente de Estado
- O script mantém o arquivo `data/synced_lifecycle_cache.json`.
- Para cada agendamento/orçamento/pagamento, é armazenado o hash de estado (`fp_stage`, `ag_stage`, `amount`).
- Se nada mudou em relação ao ciclo anterior, o script faz **zero chamadas de escrita** na API do DataCrazy.
- Isso reduz o tempo médio de execução de cada ciclo para **~8 a 12 segundos**, eliminando qualquer risco de 429 (rate limit).

### 5. Deploy na VPS Tecminas
- Implantado em `/opt/painel-mc/scripts/cron_sync_clinicorp_datacrazy.py`.
- Cron configurado em `/etc/cron.d/sync_clinicorp_datacrazy` rodando a cada **10 minutos** (`*/10 * * * *`).
- Logs em `/var/log/clinicorp_datacrazy_sync.log` com rotação automática em `/etc/logrotate.d/clinicorp_datacrazy_sync`.

## Consequências

- **Base Unificada:** Todos os pacientes do Clinicorp agora existem como leads no DataCrazy com dados de contato e tags de segmentação.
- **Autonomia Operacional:** Atendentes e dentistas realizam agendamentos, check-in e orçamentos no Clinicorp, e o CRM se autoatualiza sem trabalho manual duplicado.
- **Pós-Venda Conectado:** O pagamento no Clinicorp aciona a entrada no funil de Acompanhamento no DataCrazy.
- **Rastreabilidade:** Logs centralizados no servidor Linux da clínica monitoram todas as sincronizações em tempo real.

# Especificação de automação: sincronização Clinicorp e Aniversariantes do Mês

**Status:** Desbloqueado e em produção. Automação 1 implementada via [`scripts/cron_sync_clinicorp_datacrazy.py`](../scripts/cron_sync_clinicorp_datacrazy.py) (cron a cada 10 min na VPS Tecminas, ver [ADR 013](decisions/013-sincronizacao-continua-clinicorp-datacrazy.md)). Endpoint de aniversariantes (`GET /patient/birthdays?date=...`) validado na API oficial do Clinicorp.

## Histórico de Desbloqueio

Em 2026-09-24, as credenciais da API Clinicorp foram validadas no ambiente e a integração do ciclo de vida completo (agendamento, presença, orçamento e pagamento) foi implementada no script de sincronização contínua. Os dados de `birthDate` agora estão acessíveis via `patient/get` e pelo endpoint dedicado `patient/birthdays`.

## Automação 1 — Sincronização Clinicorp → CRM

**Objetivo (doc):** atualizações de presença, agendamento e cadastro no Clinicorp devem
automatizar as movimentações de etapas correspondentes no CRM.

**Pré-requisito de correlação:** cada lead do DataCrazy precisa de um identificador que
aponte para o paciente no Clinicorp. Duas opções:
- Usar o campo nativo `lead.externalId` (já existe no schema de negócio, hoje vazio) para
  guardar o ID do paciente Clinicorp.
- Ou criar um `additional_field` tipo `string` (`entity: lead`, nome "ID Clinicorp").

**Mapeamento evento → ação** (a implementar como automação `.dc`, gatilho por webhook
recebido do Clinicorp — formato exato depende da API do Clinicorp, a confirmar):

| Evento Clinicorp | Ação no CRM |
|---|---|
| Paciente confirmou presença na 1ª consulta | Mover business para etapa **Avaliação Realizada** (Status da Avaliação Inicial = Compareceu) no Funil Principal |
| Paciente faltou | Manter etapa, setar Status da Avaliação Inicial = Faltou, incrementar Contador de Follow-ups |
| Reagendamento registrado | Status da Avaliação Inicial = Reagendou, atualizar Data do Agendamento da Segunda Consulta |
| Orçamento fechado (contrato assinado) | `business_won` no Funil Principal → criar business em **Acompanhamento** na etapa Avaliação de Atendimento |
| Novo agendamento de retorno/rotina | Mover business do Acompanhamento para **Retorno de Rotina** |
| Cadastro novo/atualizado no Clinicorp | Criar/atualizar lead no DataCrazy (nome, telefone, `birthDate`) |

**Como implementar quando houver acesso:**
1. Confirmar com o Clinicorp se ele expõe webhook de saída ou só API para polling.
2. Se webhook: apontar para um endpoint que traduza o payload Clinicorp em chamadas
   MCP (`business_move_stage`, `lead_set_additional_field`, `business_won`) — pode ser um
   pequeno serviço externo (n8n, por exemplo) já que o DataCrazy não recebe webhook de
   terceiro diretamente num bloco `.dc`.
3. Se só API/polling: um script agendado (cron) que busca mudanças recentes no Clinicorp
   e replica no DataCrazy via MCP, no mesmo padrão dos scripts já existentes no projeto
   (`scripts/raspar_conversas_datacrazy.py` como referência de uso do MCP em lote).

## Automação 2 — Aniversariantes do Mês

**Objetivo (doc):** alimentar os funis `Aniversariantes - Mesquita` / `Aniversariantes -
Ipatinga` espelhando a base do Clinicorp, disparar régua de relacionamento e monitorar
conversão (quem virou cliente a partir do contato).

**Pré-requisito:** `birthDate` populado nos leads (via sync do Automação 1, ou export
mensal do Clinicorp).

**Desenho proposto** (o DataCrazy não tem gatilho nativo de "todo dia X verificar
aniversariantes" — precisa ser um script agendado, não um `.dc`):

1. **Script mensal** (cron, todo dia 1º): busca no DataCrazy (ou direto no Clinicorp,
   se a API permitir filtrar por mês de nascimento) todos os leads com `birthDate` no mês
   corrente.
2. Para cada lead, cria um `business` na etapa **Mês do Aniversário** do funil
   `Aniversariantes - <unidade>` correspondente (unidade determinada pelo canal/instância
   do último contato do lead).
3. Dispara a régua de mensagens (via automação `.dc` separada, gatilho `business-created-
   trigger` na etapa Mês do Aniversário — esse pedaço já é nativo do DataCrazy).
4. Quando o lead responde e a recepção agenda, mover manualmente (ou por automação de
   tag) para **Contato Realizado**.
5. Fechamento do mês: quem virou consulta/venda → mover para **Convertido**; quem não
   respondeu ou recusou → **Não Convertido**. Esses dois últimos estágios são o que
   permite medir a taxa de conversão pedida na especificação.

**Questão em aberto (a doc pede alinhamento com a "Acelero"):** a coleta de aniversariantes
deve cobrir toda a base cadastrada no Clinicorp, ou só quem já passou pela avaliação
inicial? Isso muda o volume de disparo e precisa de decisão de negócio antes de implementar
o passo 1.

## O que falta para desbloquear

- Credenciais/API docs do Clinicorp (endpoint, autenticação, e se existe webhook de saída).
- Decisão sobre o escopo da base de aniversariantes (pergunta acima).
- Confirmação de qual campo usar para correlacionar lead ↔ paciente Clinicorp.

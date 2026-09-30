# 006 — Reestruturação dos funis comerciais conforme Especificação Técnica de CRM V2

**Data:** 2026-07-29
**Status:** aceito

## Contexto

O documento [`Especificação Técnica de Configuração e Matrificação do CRM
V2.docx`](../Especificação%20Técnica%20de%20Configuração%20e%20Matrificação%20do%20CRM%20V2.docx)
define 3 funis (Principal, Acompanhamento, Aniversariantes), campos obrigatórios de
metrificação e integrações com Clinicorp/Celebram. O CRM da Master Clinic (DataCrazy,
tenant `69937b06-43cd-40d2-bd39-d3d3c9223283`) já tinha os funis `Vendas - Mesquita` e
`Vendas - Ipatinga` (este criado no mesmo dia, ainda vazio), com 6 etapas cada
(Lead → Consulta → Avaliação → Tratamento → Retorno → Manutenção) misturando comercial
e pós-venda num funil só — não batia com o desenho da especificação.

## Decisão

**1. Reestruturação dos 2 funis existentes** em vez de criar do zero. Antes de mexer,
conferi os dados reais via API (o filtro `pipelineId` da REST está quebrado — retorna
todas as businesses do tenant, ignorando o filtro; a forma confiável é ler o objeto
aninhado `stage.pipeline`). Achado: só 3 negócios reais no tenant todo, todos de teste,
todos em `Vendas - Mesquita` (2 em "Lead", 1 em "Avaliação"); `Vendas - Ipatinga` vazio.
Risco de migração era mínimo.

- `Vendas - Mesquita` → renomeado para **`Funil Principal - Mesquita`**
- `Vendas - Ipatinga` → renomeado para **`Funil Principal - Ipatinga`**
- Etapas de ambos reescritas para as 5 da especificação: **Agendamento (Entrada) →
  Avaliação Realizada → Agendamento 2ª Consulta e Follow-up → Orçamento (2ª Consulta) →
  Ganho / Perdido**.
- O `pipeline_stages_save` do MCP recusa apagar etapa com negócio associado
  (`"Cannot delete stage Lead because it is associated with existing businesses"`), então
  os 3 negócios de teste foram movidos temporariamente para o funil `Agendamentos` antes
  da reestruturação e devolvidos às etapas equivalentes depois
  (`Lead` → `Agendamento (Entrada)`, `Avaliação` → `Avaliação Realizada`).

**2. Dois novos funis por unidade, grupo `Pós-Venda`:** `Acompanhamento - Mesquita` e
`Acompanhamento - Ipatinga`, com as 3 etapas da especificação (Avaliação de Atendimento →
Em Tratamento / Manutenção → Retorno de Rotina). Nascem vazios — o negócio passa do Funil
Principal (quando marcado `Ganho`) para cá manualmente ou por automação futura.

**3. Dois novos funis por unidade, grupo `Relacionamento`:** `Aniversariantes -
Mesquita` e `Aniversariantes - Ipatinga`. A especificação só descreve uma etapa
("Mês do Aniversário"), mas pede explicitamente monitorar conversão — por isso o funil
ganhou 3 etapas a mais para viabilizar essa métrica: **Mês do Aniversário → Contato
Realizado → Convertido / Não Convertido**.

**4. 7 campos customizados** criados via `additional_field_create` (grupo
"Metrificação Comercial"): Status da Avaliação Inicial, Contador de Follow-ups, Data do
Agendamento da Segunda Consulta, Origem do Lead (Canal/UTM), Dentista/Avaliador
Responsável, Forma de Pagamento Pretendida, Tipo de Procedimento. As listas de opção
usam valores padrão de clínica odontológica (decisão do usuário) — precisam ser
revisadas no painel se não baterem com a equipe/formas de pagamento reais da clínica.
**Motivo de Perda** não virou campo novo — o DataCrazy já tinha 8 motivos de perda
nativos (`loss_reason_list`) que cobrem bem o pedido da especificação, e **Valor do
Orçamento** usa o campo nativo `business.total` em vez de um campo customizado.

**5. Bug encontrado e corrigido na mesma sessão:** o chatbot de tráfego pago do
[ADR 005](005-chatbot-trafego-por-unidade.md), gerado no mesmo dia, dispara via
`business-created-trigger` exatamente nas etapas antigas `Lead` (`93d6050a…` Mesquita,
`218e4105…` Ipatinga) e move o card para a etapa `Consulta` no handoff — etapas que a
reestruturação apagou. Corrigido em
[`scripts/gerar_dc_trafego.py`](../../scripts/gerar_dc_trafego.py): gatilho e handoff
agora apontam para `Agendamento (Entrada)` (`ab4a1b39…` Mesquita, `fa389511…` Ipatinga)
— como o novo modelo de 5 etapas não tem uma etapa distinta para "consulta agendada",
o handoff deixou de mover o card (fica em Agendamento (Entrada) do início ao fim do bot).
Os 4 `.dc` foram regenerados e o
[`README-importacao.md`](../../dc-trafego/README-importacao.md) atualizado.
**Se os `.dc` antigos já tinham sido importados no painel DataCrazy antes desta
correção, é preciso reimportar os arquivos atualizados** — não há API MCP para editar
automação já importada.

**6. Sincronização Clinicorp e Aniversariantes ficam como especificação, não
implementação.** Não há credenciais do Clinicorp no ambiente (`~/.claude/.env` não tem
`CLINICORP_*`) e nenhum lead do CRM tem `birthDate` preenchido (checado numa amostra de
200). O fluxo completo — mapeamento evento→ação e desenho do disparo mensal de
aniversariantes — está documentado em
[`docs/spec-automacao-clinicorp-aniversariantes.md`](../spec-automacao-clinicorp-aniversariantes.md),
pronto para implementar assim que houver acesso à API do Clinicorp.

## Alternativas Consideradas

- **Criar funis novos do zero, mantendo `Vendas - Mesquita`/`Vendas - Ipatinga` intactos:**
  descartado a pedido do usuário — geraria dois pares de funis fazendo papéis
  sobrepostos, e a migração dos 3 negócios de teste era trivial o suficiente para não
  justificar o funil duplicado.
- **Funil de Aniversariantes único para a clínica toda:** descartado a pedido do
  usuário em favor de separar por unidade, espelhando os outros dois funis e permitindo
  saber de qual unidade veio a conversão.
- **Pedir os valores reais de dentistas/formas de pagamento/procedimentos antes de criar
  os campos:** descartado a pedido do usuário, que preferiu valores padrão de mercado
  agora e ajuste posterior no painel — evita travar a entrega numa informação que não
  muda a estrutura, só o conteúdo das opções.
- **Implementar a automação Clinicorp com um webhook genérico "no escuro":**
  descartado — sem a documentação real da API do Clinicorp, qualquer automação seria
  best-effort e poderia falhar silenciosamente. Preferível deixar a especificação pronta
  e sinalizada como bloqueada.

## Consequências

- `Vendas - Mesquita` e `Vendas - Ipatinga` não existem mais com esse nome — qualquer
  automação, relatório ou link salvo que referencie o nome antigo ou as etapas antigas
  precisa ser atualizado (o chatbot de tráfego já foi corrigido nesta sessão; vale
  verificar se há outras referências fora deste repositório, ex.: dashboards externos).
- O CRM ganhou 4 funis novos (2 Acompanhamento + 2 Aniversariantes), hoje vazios —
  populá-los depende de automação futura (fechamento comercial → Acompanhamento) ou da
  integração Clinicorp (→ Aniversariantes).
- As listas de opção dos campos customizados são placeholders de mercado e precisam de
  revisão manual pela clínica antes de virarem confiáveis para BI.
- A automação Clinicorp/Aniversariantes segue bloqueada até haver credenciais — nenhum
  dado real de aniversário ou sincronização de presença é gerado no CRM ainda.

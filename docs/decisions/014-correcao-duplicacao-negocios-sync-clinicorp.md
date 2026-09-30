# 014 — Correção da duplicação de negócios no sync Clinicorp → DataCrazy

**Data:** 2026-09-24
**Status:** aceito — corrige a implementação da [ADR 013](013-sincronizacao-continua-clinicorp-datacrazy.md)

## Contexto

O card de um paciente apareceu com 5 negócios
abertos, todos criados em 24/09: dois no Funil Principal (#893 às 03:50 e #1195 às
12:30), dois em Agendamentos (#894 e #1196) e um em Acompanhamento - Ipatinga (#1216).
A cada mudança de status na agenda o sync criava um card novo na etapa de destino e
deixava o anterior parado.

Não era só esse paciente. Levantamento pela REST em 24/09 (1.211 negócios no tenant):

- **137** pares (lead, funil) com mais de um negócio
- **169** negócios excedentes (14% da base): 124 no Funil Principal, 38 em Agendamentos, 7 em Acompanhamento
- 145 criados em 24/09 e 23 em 23/09
- Pior caso: 4 negócios do mesmo lead no mesmo funil (3 pacientes)

O log de produção (`/var/log/clinicorp_datacrazy_sync.log`) mostrava **0 linhas `MOVIDO`**
desde o início do cron: o ramo que move negócio nunca executou.

## Causa

Duas falhas no [`cron_sync_clinicorp_datacrazy.py`](../../scripts/cron_sync_clinicorp_datacrazy.py):

1. **Campo no lugar errado.** O script procurava o funil em `b["stage"]["pipelineId"]`,
   mas a tool MCP `lead_list_businesses` devolve os campos **achatados**
   (`pipelineId`, `stageId`, `stageName`, `pipelineName`, sem objeto `stage`). A busca
   nunca achava o negócio existente e o script sempre caía no `business_create`. O
   bug estava em 5 pontos: Fases 1/2 (Funil Principal e Agendamentos) e Fase 3
   (orçamento, ganho e Acompanhamento). Consequência extra: a Fase 3 nunca moveu
   para "Orçamento", nunca gravou valor e nunca marcou Ganho; só criava card de
   Acompanhamento, um por pagamento (daí os duplicados no pós-venda com parcelas).
2. **Falha de leitura tratada como "não existe".** O MCP não devolve HTTP 429: o
   rate limit vem como `201` com `result.isError` e `"Too many requests"` no corpo.
   O `datacrazy_mcp` devolvia `{"error": ...}`, o `res.get("data", [])` virava `[]`
   e o script criava negócio (e lead) novo. O mesmo acontecia com qualquer outro
   erro de leitura.

O cache por agendamento (`phone_data`) limitava o estrago: só duplicava quando o
status mudava, não a cada 10 minutos.

## Decisão

Regra: **o sync move o negócio existente do lead. Só cria quando o lead não tem
nenhum negócio naquele funil.**

- `negocio_do_funil()` lê `pipelineId` achatado (com fallback para as formas
  aninhadas da REST). Se houver qualquer negócio no funil, não cria. Move o **aberto
  mais antigo** (menor `code`), para convergir no card original enquanto existirem
  duplicados. Se só houver negócio ganho/perdido, não reabre e não cria.
- `datacrazy_mcp()` detecta `isError` e a chave `error` no corpo, retenta rate limit
  com backoff (20s, 40s, 60s) e **não retenta criação** em timeout/5xx, porque a
  requisição pode ter sido aplicada.
- `obter_negocios_do_lead()` e a busca de lead devolvem `None` quando a leitura
  falha. O script pula o agendamento sem escrever nada.
- O cache só é gravado quando todas as escritas do agendamento deram certo. Se algo
  falhar, o próximo ciclo reprocessa.
- `criados_no_ciclo` impede criar duas vezes o mesmo (lead, funil) no mesmo ciclo
  (paciente novo com dois agendamentos na janela, ou duas parcelas pagas), caso a
  listagem ainda não mostre o card recém-criado.
- **Trava `flock`** (`data/sync_clinicorp.lock`): se o ciclo anterior ainda estiver
  rodando, o novo sai sem fazer nada. O backoff de rate limit pode esticar um ciclo
  além dos 10 min do cron, e dois processos juntos criariam em dobro.

## Validação

- **Dados reais do paciente do caso (só leitura):** o script corrigido move #893 (Funil
  Principal) e #894 (Agendamentos), os mais antigos, e reconhece o #1216 no
  Acompanhamento. Não cria nada.
- **Caminhos de erro simulados:** rate limit persistente, erro não-JSON e falha na
  busca de lead resultam em "não escreve". Timeout em `business_create` não é
  retentado.
- **Ensaio do ciclo completo** com todas as escritas interceptadas e cache vazio
  (171 agendamentos): **0 `business_create`**, 107 movimentações nas Fases 1/2,
  30 orçamentos, 44 ganhos, 0 erros. Nada saiu de Ganho nem de Orçamento.
- **Trava:** com o lock ocupado, uma segunda execução sai imediatamente.

## Ganho automático: desligado por gatilho errado

Verificação feita no mesmo dia, depois do deploy:

- **Nunca houve ganho automático.** 0 linhas `FECHAMENTO` no log desde o início, e
  nenhum dos 9.070 leads tem negócio ganho ou perdido (`metrics.purchaseCount` e
  `lostBusinessesCount` zerados). O bug do campo `stage` também impedia essa parte.
- **Arrastar para a coluna "Ganho" não marca o negócio como ganho.** Um negócio (#1221) foi
  movido à mão para a coluna Ganho às 14:57 e continua `status: in_process`. Nenhuma
  automação nativa do DataCrazy converteu. A coluna é só uma etapa; ganho é status,
  gravado por `business_won`.
- **O gatilho do script (pagamento recebido) está errado.** Dos 81 pagamentos da
  semana, 55 são boleto e a maioria é parcela de tratamento antigo (3/12, 5/12…).
  Com o bug corrigido, cada parcela marcaria como ganho o card atual do paciente, e
  o MCP não tem ferramenta para reabrir negócio. **A chamada `business_won` por
  pagamento foi removida** às 15:10:39 do mesmo dia, antes de disparar alguma vez.
- **O gatilho certo existe no Clinicorp:** `estimates/list` traz `Status`
  (`OPEN`/`APPROVED`) e `ApprovedDate`. Foram 14 aprovados e 19 em aberto na semana.
  Isso bate com o item 6 da proposta do Leonardo (orçamento aprovado → Ganho).
  Falta implementar. A chave de cache `est_{id}` também precisa incluir o status,
  senão a passagem de `OPEN` para `APPROVED` nunca é vista.
- Continua ativo: pagamento cria card em Acompanhamento se o lead não tiver nenhum
  nesse funil. Isso inclui quem paga parcela de tratamento antigo.

## Resultado

- Implantado em 24/09 ~14:57 em `/opt/painel-mc/scripts/cron_sync_clinicorp_datacrazy.py`
  (backup da versão anterior: `...py.bak-20260924-duplicacao`). O ciclo das 15:00
  rodou sem erro.
- A carga inicial que criou 244 negócios entre 00:42 e 01:12 (horário de Brasília) de 24/09 rodou
  **nesta máquina local** (o cache local foi gravado às 01:12 e depois copiado para a VPS),
  por isso não aparece no log da VPS. Não há agendamento local ativo.

## Alternativas Consideradas

- **Nunca criar negócio pelo sync:** descartada. Paciente novo no Clinicorp ficaria
  fora do funil.
- **Buscar os negócios pela REST (`GET /businesses`)** em vez do MCP: descartada. O
  filtro `pipelineId` da REST é ignorado (ADR 006) e o limite é de 30 req/min.
- **Mover o negócio mais recente em vez do mais antigo:** descartada. O mais antigo
  carrega o histórico (conversas, notas, atividades) e é o que a limpeza vai manter.

## Consequências

- O ramo de movimentação passa a rodar pela primeira vez, e a Fase 3 (orçamento com
  valor, Ganho) também. Movimentos que antes apareciam como card novo agora movem o
  card original. Isso inclui voltar etapa: por exemplo, um negócio em "Orçamento"
  volta para "Agendamento 2ª Consulta" se o paciente marcar retorno. É o mesmo
  mapeamento de antes, só que agora aplicado ao card existente.
- Os 169 duplicados já criados **não somem com a correção**. Enquanto não forem
  limpos, o sync move o mais antigo de cada grupo e os clones ficam parados.
- Leitura com falha agora atrasa a sincronização daquele paciente em um ciclo
  (10 min), em vez de gerar duplicado.

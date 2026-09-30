# 005 — Chatbot de tráfego por unidade, trilho de botões e limpeza da tag

**Data:** 2026-07-29
**Status:** aceito
**Sucede:** [004](004-raspagem-conversas-e-fluxo-trafego.md) (que deixou 5 decisões em aberto)

## Contexto

O ADR 004 entregou o diagnóstico das conversas e o desenho do fluxo, mas deixou cinco
pontos para o cliente decidir. Todos foram decididos:

1. **Um fluxo por unidade** (Ipatinga e Mesquita separados) — não um bot único.
2. **Forçar o clique em botão** enquanto o humano não assume.
3. **Bot sem nome próprio** — apenas "assistente da Master Clinic".
4. Rastreio CTWA/CAPI **já corrigido** na origem.
5. **Manter a tag "Tráfego Pago" só nos leads identificados como Click-to-WhatsApp**,
   limpando o resto.

## Decisão

**1. Dois fluxos, quatro arquivos `.dc`** em [`dc-trafego/`](../../dc-trafego/), gerados por
[`scripts/gerar_dc_trafego.py`](../../scripts/gerar_dc_trafego.py):

| Arquivo | Canal | Blocos |
|---|---|---|
| `1-ipatinga-chatbot.dc` | Oficial Master Clinic (Cloud API) | 22 |
| `1-ipatinga-resgate.dc` | Oficial Master Clinic | 14 |
| `2-mesquita-chatbot.dc` | Mesquita Uazapi | 22 |
| `2-mesquita-resgate.dc` | Mesquita Uazapi | 14 |

As unidades diferem em canal, `provider` (`WHATSAPP_CLOUD_API` vs `UAZAPI`), endereço,
botões de cidade e funil (`Vendas - Ipatinga` e `Vendas - Mesquita`).

**1.1. Gatilho por negócio criado, não por palavra-chave.** O chatbot dispara em
`business-created-trigger` na etapa **Lead** do funil da unidade
(`218e4105…` para Ipatinga, `93d6050a…` para Mesquita). Já existe um fluxo anterior que
identifica a origem do lead, cria o lead e abre o card — **se o card nasceu, o lead mandou
mensagem**. O chatbot deixou de casar as 8 aberturas do Click-to-WhatsApp e de criar card;
sua única ação de entrada é a tag `CONVERSOU`, que arranca o resgate.

Isso elimina o ponto mais frágil do desenho anterior: cada campanha nova pré-preenche uma
frase diferente, e a lista de palavras-chave envelheceria em silêncio. Também evita
disparar para paciente da casa que escreva algo parecido, e concentra a qualificação de
origem em um lugar só.

**2. Chatbot e resgate são automações separadas.** Um bloco `chat` com botões tem
`nextBlockId: ""` e **pausa a automação até o clique** — que é justamente o mecanismo que
força o botão. Como o fluxo fica parado ali, uma cadência em série nunca dispararia. O
resgate roda como automação própria, disparada por `lead-tag-added-trigger` na tag
`CONVERSOU` e interrompida pela tag `AGUARDANDO-AGENDAMENTO`.

**3. Trilho 100% por botão**, no máximo 3 por mensagem (limite de quick reply da Cloud API).
Isso obrigou a desdobrar "o que você procura" em duas perguntas encadeadas e a **remover a
coleta de nome** — pedir nome completo exigiria texto livre. O nome do contato já vem do
WhatsApp e a recepcionista confirma no handoff.

**3.1. Roteiro reescrito na lógica de CRC: vender a avaliação, não o tratamento.**
A primeira versão abria a qualificação com *"a Master Clinic atende apenas de forma
particular — não trabalhamos com convênios nem com o Brasil Sorridente"*. Era um erro
conceitual: **antecipar objeção derruba o lead antes de existir qualquer valor na conversa.**

A sequência passou a ser **acolher → investigar a necessidade → construir o valor da
avaliação → fechar por alternativa → confirmar viabilidade → entregar ao humano**:

| Antes | Depois |
|---|---|
| 1. Cidade (triagem fria) | 1. *"Como podemos cuidar do seu sorriso?"* |
| 2. Convênio (objeção antecipada) | 2. Acolhimento da necessidade |
| 3. Procedimento | 3. **Valor da avaliação** (examina, tira dúvidas, monta o plano) |
| 4. Turno | 4. Turno — *"manhã ou tarde?"*, nunca *"quando você quer vir?"* |
| 5. Handoff | 5. Viabilidade: *"fica tranquilo chegar aqui?"* |
| | 6. Handoff |

Três regras derivadas, agora **verificadas automaticamente pelo gerador**: o bot não fala
de convênio, preço ou parcelamento; não dá informação a ponto de tornar a visita
dispensável; e não faz pergunta aberta onde cabe alternativa fechada. Uma lista de
assuntos vetados é checada em todas as mensagens a cada geração — texto proibido reprova
o build.

O filtro geográfico saiu do início e foi para depois da escolha de turno, quando o lead já
está comprometido. O argumento do atendimento social das quartas (1 kg de alimento) foi
preservado na documentação **como carta de contorno para o humano**, a ser usada quando o
lead disser que só tem convênio — não antes.

**4. Limpeza da tag "Tráfego Pago"** via
[`scripts/limpar_tag_trafego.py`](../../scripts/limpar_tag_trafego.py) (MCP `lead_add_tag`
/ `lead_remove_tag`), mantendo a tag apenas nos 72 leads com abertura Click-to-WhatsApp.
O estado anterior é salvo em `data/limpeza_tag_trafego.json` antes de qualquer escrita,
o que torna a operação reversível.

Duas descobertas na execução:

- **O MCP do DataCrazy aceita argumentos errados em silêncio.** A primeira rodada usou
  `{leadId, tagIds: [array]}`; o schema real é `{id, tagIds}` com **`tagIds` em string
  separada por vírgula**. As 481 chamadas retornaram sucesso e **não alteraram nada**.
  O script passou a conferir por GET na REST depois de escrever.
- **Houve um evento de aplicação em massa.** Em 2026-07-29, às 07:24 (BRT), 1.407 leads
  ganharam a tag no mesmo minuto — 1.080 já existentes e 328 criados ali. O padrão dos
  novos (nomes como `194442078195897@lid` e IDs numéricos) indica **sincronização de
  contatos do WhatsApp**, não leads de anúncio. Foi pontual: nas horas seguintes só
  entraram leads individuais.

**Resultado final verificado na API:** 73 leads com a tag numa base de 7.766 — os 72
identificados por Click-to-WhatsApp mais um lead novo (`Cazé`, 10:13 BRT) que já nasceu
com a tag aplicada pelo fluxo de rastreio corrigido, ou seja, um positivo legítimo.

**5. Validação dos `.dc` contra a especificação do formato.** O gerador confere UUIDs,
conexões órfãs, o limite de 3 botões e — o mais importante — **cada nome de componente
contra `~/.claude/skills/datacrazy-automacoes/references/formato-dc-completo.md`**.

## Alternativas Consideradas

- **Bot único para as duas unidades, com ramificação por canal:** descartado a pedido do
  cliente. Também seria pior na prática: endereço, funil e opções de cidade divergem, e o
  `provider` do canal (Cloud API vs Uazapi) precisa ser fixado por bloco de mensagem.
- **Gatilho por palavra-chave do Click-to-WhatsApp:** era o desenho inicial, e foi
  substituído por `business-created-trigger`. A lista de aberturas quebra a cada campanha
  nova, e a origem já é resolvida pelo fluxo que cria o card. As 8 frases catalogadas
  seguem documentadas na [análise](../analise-conversas-trafego.md) como evidência de
  identificação de tráfego, não mais como gatilho.
- **Qualificar por cidade e convênio logo no início:** era o desenho inicial e foi
  descartado. Filtrar cedo parece eficiente — descarta 18% de fora da região e 20% de
  convênio antes de gastar atendimento — mas cobra o preço de abrir a conversa com uma
  triagem fria e uma negativa. Os dois filtros continuam no fluxo, só que **depois** de o
  lead demonstrar necessidade e escolher turno (a distância) ou **só se o lead levantar**
  (o convênio).
- **Fallback de texto livre no bloco de botões:** era o desenho inicial — usar o
  `nextBlockId` do chat como caminho de "respondeu texto". **Inválido no formato:** com
  botões, `nextBlockId` deve ser `""`. O comportamento nativo (fluxo pausado) já entrega o
  que o cliente pediu.
- **Interpretar texto livre com bloco `ai` (`chat-intent-ai`):** descartado nesta fase —
  gasta Crazy Tokens, adiciona um ponto de falha e contraria o pedido de forçar o botão.
- **Coletar nome com `text-input-message`:** descartado — aceitaria texto livre, furando a
  regra do trilho de botões.
- **Cadência de resgate dentro do mesmo `.dc`:** impossível, pelo motivo técnico acima.
- **Deletar a tag "Tráfego Pago" e criar uma nova limpa:** descartado — quebraria filtros e
  automações existentes que já referenciam o ID da tag.

## Consequências

- Os 4 `.dc` importam **desativados**, com `instanceId` vazio: é obrigatório selecionar o
  canal em cada bloco de mensagem ao importar (9 blocos no chatbot, 4 no resgate, por unidade).
- **Nenhuma tag nova foi criada** — os fluxos usam só as 6 que já existiam no tenant.
- O chatbot passa a **depender do fluxo que cria o card**: se aquele fluxo parar de abrir
  negócio na etapa Lead, o bot silenciosamente não dispara. É o trade-off aceito em troca
  de não depender do texto do anúncio.
- O bot passa a responder em segundos, 24h, atacando os 17% de leads nunca respondidos e os
  31% que chegam fora do expediente.
- **Texto livre e áudio saem do caminho crítico**: não avançam o fluxo. É intencional, mas
  significa que um lead que só manda áudio fica parado até o resgate de 30 min. Se isso
  incomodar, o caminho é o bloco `ai` → `audio-transcription-ai`.
- A tag "Tráfego Pago" passa a ser um filtro confiável de origem no CRM (72 leads reais,
  contra os 533 anteriores).
- Fica pendente: **endereço da unidade Mesquita** (placeholder no texto), rodízio de
  atendentes na notificação (`attendantsIds: []` notifica todos) e o fluxo de RH do canal
  Gerência Uazapi, que não foi implementado.

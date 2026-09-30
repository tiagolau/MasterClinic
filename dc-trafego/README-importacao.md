# Chatbot de tráfego → agendamento humano — importação

Gerado por [`scripts/gerar_dc_trafego.py`](../scripts/gerar_dc_trafego.py).
Desenho: [fluxo-chatbot-trafego-agendamento.md](../docs/fluxo-chatbot-trafego-agendamento.md).
Base de evidência: [analise-conversas-trafego.md](../docs/analise-conversas-trafego.md).

## Os arquivos

**Um fluxo por unidade, cada fluxo em dois arquivos:**

| Arquivo | Canal | O que faz |
|---|---|---|
| `1-ipatinga-chatbot.dc` | Oficial Master Clinic (Cloud API) | trilho de botões até o handoff |
| `1-ipatinga-resgate.dc` | Oficial Master Clinic | cadência +30min/+4h/+1d/+3d |
| `2-mesquita-chatbot.dc` | Mesquita Uazapi | trilho de botões até o handoff |
| `2-mesquita-resgate.dc` | Mesquita Uazapi | cadência +30min/+4h/+1d/+3d |

**Gatilho do chatbot:** negócio criado na etapa **Agendamento (Entrada)** do funil
principal da unidade.
O fluxo que roda antes já identifica a origem, cria o lead e abre o card — **se o card
nasceu, o lead mandou mensagem**. Por isso o chatbot não casa palavras-chave do
Click-to-WhatsApp nem cria card: ele só assume a conversa a partir daí.

**Por que o resgate é separado:** um bloco de mensagem com botões **pausa a automação
até o clique**. Se a cadência estivesse em série com o chatbot, ela nunca dispararia.
O resgate roda como automação própria, disparada pela tag `CONVERSOU` e parando assim
que o lead ganha `AGUARDANDO-AGENDAMENTO`.

Todos importam **desativados** (`active: false`).

## A estratégia do roteiro

O único objetivo do bot é **fazer o lead querer a avaliação** e entregá-lo para a recepção
fechar o horário. Sequência: acolher → investigar a necessidade → dar valor à avaliação →
fechar por alternativa (manhã/tarde) → confirmar que consegue vir → handoff.

**O bot nunca fala de convênio, preço ou parcelamento.** São objeções: só se tratam quando
o lead levanta, e quem trata é o humano. Abrir a conversa com *"não atendemos convênio"*
derruba o lead antes de existir qualquer valor — por isso saiu do fluxo.

O argumento do **atendimento social das quartas** (1 kg de alimento) continua sendo uma
carta forte, mas de contorno: usar quando o lead disser que só tem convênio, não antes.

## Como o "forçar botão" funciona

Toda pergunta do bot é um bloco `chat` com botões e `nextBlockId: ""`. O DataCrazy
**só avança quando o lead clica** — não existe caminho para texto livre. Cada pergunta
já traz `👇 *Toque em uma das opções abaixo*` para o lead saber o que fazer.

O bot só solta o lead em três situações: handoff (humano assume), urgência (dor, handoff
imediato) e descarte por distância. Em todas elas, `stop-chat-automations-action` desliga
o bot naquela conversa.

## Passo a passo da importação

1. **Importe os 4 arquivos** em `Automações → Importar`.
2. **Selecione o canal em cada bloco de mensagem** — o `instanceId` foi deixado vazio
   de propósito. São 9 blocos de chat no chatbot e 4 no resgate, por unidade.
   - Ipatinga → `Oficial Master Clinic`
   - Mesquita → `Mesquita Uazapi`
3. **Confira o gatilho do chatbot**: *negócio criado* na etapa **Agendamento (Entrada)**
   do funil da unidade. Deve apontar para `Funil Principal - Ipatinga` ou
   `Funil Principal - Mesquita` conforme o arquivo (ADR 006 renomeou e reestruturou
   esses funis — a etapa antiga "Lead" não existe mais).
4. **Preencha o endereço da unidade Mesquita** — o texto está como
   *"unidade Mesquita — confirmar endereço com a recepção"*. Aparece em 2 blocos.
5. **Teste com o seu próprio número** antes de ativar: mande uma mensagem que faça o
   fluxo anterior criar o card na etapa Agendamento (Entrada) — é isso que dispara o chatbot.
6. **Ative** — primeiro o chatbot, depois o resgate.

## O que conferir no teste

- [ ] O card cai na etapa **Agendamento (Entrada)** e o bot responde em seguida
- [ ] O bot se apresenta como "assistente da Master Clinic" (sem nome próprio)
- [ ] A primeira pergunta é sobre a **necessidade**, não sobre cidade ou convênio
- [ ] Os botões aparecem (3 no máximo por mensagem — limite da Cloud API)
- [ ] Digitar texto livre **não** avança o fluxo
- [ ] "Estou com dor" pula direto para o handoff, com notificação 🔴
- [ ] O bot **nunca** menciona convênio, preço ou parcelamento
- [ ] A pergunta de localização só aparece **depois** de o lead escolher o turno
- [ ] "Sou de outra cidade" → "Não, é longe demais" encerra e marca `PERDIDO-BREAKUP`
- [ ] No handoff: a recepção recebe notificação e **o bot para** (o card permanece em
      Agendamento (Entrada) — a etapa avança manualmente quando a recepção confirma o
      comparecimento)
- [ ] Com o bot parado, responder no lugar dele não dispara mais nada
- [ ] O resgate **não** dispara para quem já tem `AGUARDANDO-AGENDAMENTO`

## IDs usados (tenant `69937b06-43cd-40d2-bd39-d3d3c9223283`)

⚠️ **Atualizado pelo ADR 006** — os funis `Vendas - Ipatinga`/`Vendas - Mesquita` foram
renomeados e reestruturados para `Funil Principal - Ipatinga`/`Funil Principal - Mesquita`
(5 etapas conforme a especificação de CRM). As etapas antigas `Lead` e `Consulta` foram
apagadas; não existe mais uma etapa de handoff distinta — o card permanece em
`Agendamento (Entrada)` do início ao handoff.

**Pipelines/etapas**

| Unidade | Gatilho e handoff (etapa Agendamento (Entrada)) |
|---|---|
| Ipatinga | Funil Principal - Ipatinga `fa389511…` |
| Mesquita | Funil Principal - Mesquita `ab4a1b39…` |

**Tags** (todas já existiam — nenhuma tag nova foi criada)

`CONVERSOU` · `AGUARDANDO-AGENDAMENTO` · `Requer Retorno` · `PERDIDO-BREAKUP` ·
`Novo Paciente`

O chatbot **não** aplica `Tráfego Pago` nem `LEAD` — isso é do fluxo que cria o lead e o card.

## Regras que o bot respeita (extraídas das conversas reais)

- Nunca fala valor — *"quem te passa certinho é o próprio doutor, no dia da consulta"*
- Nunca fala parcelamento — *"é com o financeiro"*
- Nunca menciona convênio nem Brasil Sorridente — é assunto do humano, se surgir
- Nunca manda áudio (a raspagem registrou perda de lead por áudio ruim)
- Nunca agenda — leva o lead a querer a avaliação e entrega para o humano fechar

**Para a recepção, quando a objeção de convênio aparecer** (20% dos leads de tráfego
perguntam), o texto que a clínica já usa:

> A Master Clinic não atende convênios, apenas consultas particulares.
>
> Como alternativa, o Dr. Wilton realiza atendimento social às quartas-feiras. Nesse dia,
> a consulta é realizada mediante a doação de 1 kg de alimento não perecível, que será
> destinado a ações sociais.
>
> Se desejar, posso verificar um horário disponível para você.

Acolhe, reenquadra e volta para o agendamento — sempre terminando com o horário.

## Pendências conhecidas

- **Endereço da unidade Mesquita** — placeholder no texto.
- **Anúncio de vaga de emprego** cai no canal `Gerência Uazapi` com as mesmas aberturas
  CTWA (19 das 118 conversas de tráfego). Esses fluxos não cobrem esse canal — se o
  anúncio de vaga voltar a rodar, vale um `.dc` de RH separado.
- **Transcrição de áudio**: 43 dos 99 leads de tráfego envolveram áudio. Como o bot só
  aceita botão, o áudio do lead simplesmente não avança o fluxo — o resgate cutuca em
  30 min. Se quiser tratar áudio, o caminho é o bloco `ai` → `audio-transcription-ai`.

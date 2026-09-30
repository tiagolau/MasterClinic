# Fluxo do chatbot de tráfego → agendamento humano (DataCrazy)

**Data:** 2026-07-29
**Base:** [analise-conversas-trafego.md](analise-conversas-trafego.md) — 1.687 conversas raspadas
**Objetivo:** responder em <1 min e levar o lead até **querer a avaliação**, entregando-o
à recepcionista só para fechar o horário.

O bot **não agenda e não vende tratamento**. Ele acolhe, investiga a necessidade, constrói
o valor da avaliação e entrega. O horário quem dá é humano — é assim que a clínica trabalha
hoje e é onde ela converte.

> **Status:** implementado. Os `.dc` prontos para importar estão em
> [dc-trafego/](../dc-trafego/) — ver [README de importação](../dc-trafego/README-importacao.md).
>
> **Decisões aplicadas (2026-07-29):**
> 1. **Um fluxo por unidade** — Ipatinga e Mesquita separados, com canal, pipeline,
>    endereço e botões de cidade próprios.
> 2. **Avanço só por botão** até o humano assumir — nenhuma pergunta aceita texto livre.
> 3. **Bot sem nome próprio** — se identifica como *"assistente da Master Clinic"*.
> 4. **Rastreio CTWA/CAPI já corrigido** na origem.
> 5. **Tag "Tráfego Pago" limpa** — mantida só nos leads identificados por Click-to-WhatsApp.

---

## Princípios de desenho (cada um resolve um vazamento medido)

| Princípio | Vazamento que fecha |
|---|---|
| Responder em segundos, 24h | 17% nunca respondidos + 31% chegam fora do expediente |
| Abrir pela **necessidade**, não por triagem | 52% mandavam 1 mensagem e sumiam |
| Construir o valor da **avaliação** antes de qualquer logística | leads que "só queriam saber" e evaporavam |
| Filtro geográfico **depois** do lead escolher turno | 18% são de fora — mas triagem fria derruba os outros 82% |
| **Objeção só quando aparece** (convênio, preço) | 20% perguntam de convênio, mas antecipar mata a conversa |
| Nunca falar valor | regra da clínica ("valores só com o Dr.") |
| Só texto, nunca áudio | conversas perdidas por áudio ruim |
| **Avanço só por botão** | tira o texto livre e o áudio do caminho crítico |
| **Um fluxo por unidade** | endereço, funil e opções de cidade são diferentes |
| Handoff com contexto pronto | recepcionista não relê a conversa toda |

---

## O que muda entre as duas unidades

Mesmo esqueleto, quatro diferenças:

| | Ipatinga | Mesquita |
|---|---|---|
| Canal | Oficial Master Clinic (Cloud API) | Mesquita Uazapi |
| Endereço na mensagem | Av. Brasil, 685 — Iguaçu, Ipatinga | *a preencher* |
| Funil | Vendas - Ipatinga | Vendas - Mesquita |
| Gatilho (etapa Lead) | `218e4105…` | `93d6050a…` |

---

## Gatilho

**Evento:** `business-created-trigger` — **negócio criado na etapa `Lead`** do funil de
vendas da unidade (`Vendas - Ipatinga` ou `Vendas - Mesquita`).

O fluxo que roda antes já identifica a origem do lead, cria o lead e abre o card. **Se o
card nasceu, é porque o lead mandou mensagem** — então o chatbot não precisa casar as
aberturas do Click-to-WhatsApp por palavra-chave nem recriar nada.

Ganhos sobre o gatilho por palavra-chave:

- **Não quebra quando a campanha muda o texto** do anúncio — era o ponto mais frágil do
  desenho anterior, já que cada campanha nova pré-preenche uma frase diferente.
- **Não dispara para paciente da casa** que por acaso escreva uma frase parecida.
- **A qualificação de origem fica em um lugar só** — no fluxo que já existe.
- **Separa naturalmente as unidades**: cada funil tem seu gatilho, sem depender do canal.

**Única condição no fluxo:** `lead-has-tag(AGUARDANDO-AGENDAMENTO)` — se o lead já foi
entregue ao humano, o bot não reaborda.

**Ação de entrada:** só a tag `CONVERSOU`, que é o que arranca a cadência de resgate.
As tags de origem e o card já vêm prontos do fluxo anterior.

---

## A lógica: vender a avaliação, não o tratamento

O único objetivo do primeiro contato é **ocupar uma cadeira na agenda**. Tudo que não
serve a isso sai do caminho. Três regras derivam daí:

1. **Nunca abrir com objeção.** Convênio, preço e distância são objeções — só se tratam
   quando o lead levanta, e quem trata é o humano. Antecipar *"não atendemos convênio"*
   derruba o lead antes de existir qualquer valor na conversa.
2. **Nunca dar informação demais.** Quem já "sabe tudo" pelo WhatsApp não precisa ir até
   a clínica. O bot desperta o interesse e transfere a resolução para a avaliação.
3. **Nunca perguntar aberto o que pode ser fechado.** "Quando você quer vir?" devolve o
   problema ao lead. "De manhã ou à tarde?" fecha.

Sequência: **acolher → investigar → dar valor à avaliação → fechar por alternativa →
confirmar viabilidade → entregar ao humano**.

---

## Passo 1 — Acolhida e necessidade (dispara em segundos, 24h)

> Olá! Tudo bem? 😊
>
> Aqui é a assistente da **Master Clinic Odontologia Especializada** — unidade {Ipatinga|Mesquita} ✨
>
> Que bom ter você por aqui! Me conta como podemos cuidar do seu sorriso 💚
>
> 👇 **Toque em uma das opções abaixo**

**Botões:** `Estou com dor` · `Quero fazer um tratamento` · `Levar meu filho`

Sem nome próprio: a recepção humana assina com o nome dela (Jhovanna, Jhessilee) quando
assume. O bot nunca finge ser uma pessoa.

A primeira pergunta é sobre **a necessidade do lead**, não sobre logística. É o que abre
a conversa e o que dá à recepção o contexto para trabalhar depois.

*Por quê:* mata os 17% de não-resposta e os 31% que chegam de madrugada.

---

## Passo 2 — Acolher a resposta

### 2a. `Estou com dor` → handoff imediato

> Poxa, dor de dente não dá sossego mesmo 🛑
>
> Já estou avisando a recepção pra te encaixar o quanto antes. Fica aqui comigo que já te respondem!

→ tags `Requer Retorno` + `AGUARDANDO-AGENDAMENTO`, notificação **🔴 URGÊNCIA**, bot para.
Dor não passa por funil.

### 2b. `Quero fazer um tratamento` → investigação

> Que bom que você decidiu cuidar disso! 💚
>
> E o que você gostaria de resolver?
> 👇 **Toque em uma das opções abaixo**

**Botões:** `Implante ou prótese` · `Aparelho / ortodontia` · `Limpeza e avaliação`

### 2c. `Levar meu filho`

> Que bom! Cuidar desde cedo faz toda a diferença no sorriso dele 🧒✨

---

## Passo 3 — O valor da avaliação

O coração do fluxo. É aqui que o bot constrói o motivo de ir até a clínica:

> O primeiro passo aqui é uma **avaliação** com o nosso especialista 🦷
>
> Ele examina o seu caso com calma, tira todas as suas dúvidas e monta o plano ideal
> pra você — assim você já sai daqui sabendo exatamente o que precisa ser feito, sem surpresa.
>
> Vou reservar um horário pra você, tá bom?

Repare no que **não** está aqui: preço, duração, nome de procedimento, condição de
pagamento. A avaliação resolve tudo isso presencialmente — que é o argumento para ir.

---

## Passo 4 — Fechamento por alternativa

> Você prefere vir de manhã ou à tarde? 🗓️
> 👇 **Toque em uma das opções abaixo**

**Botões:** `De manhã` · `À tarde` · `Tanto faz`

O bot não pergunta *se* o lead quer agendar — pergunta *quando*. A pergunta pressupõe
o agendamento.

O bot **não pede nome**: exigiria texto livre, e o WhatsApp já traz o nome do contato.
Quem confirma o nome completo é a recepcionista.

---

## Passo 5 — Viabilidade (o filtro geográfico, no lugar certo)

> Perfeito! Nossa unidade fica em **{endereço}** 📍
>
> Fica tranquilo pra você chegar até aqui?
> 👇 **Toque em uma das opções abaixo**

**Botões:** `Sim, tranquilo` · `Sou de outra cidade`

- **Sim** → handoff.
- **Sou de outra cidade** →
  > Entendi! Temos pacientes que vêm de outras cidades, principalmente para implante e
  > prótese — nesses casos a gente organiza o tratamento em menos visitas, pra compensar
  > a viagem.
  >
  > Você conseguiria vir até {cidade}?

  **Botões:** `Sim, consigo ir` · `Não, é longe demais`
  - **Sim** → tag `Requer Retorno` + handoff (a recepção sabe que é deslocamento).
  - **Não** → despedida gentil, tag `PERDIDO-BREAKUP`, perde o card, bot para.

*Por que aqui e não no começo:* 18% dos leads de tráfego são de fora da região, mas
perguntar cidade na primeira mensagem é uma triagem fria que derruba os outros 82%. Neste
ponto o lead já disse o que precisa e já escolheu turno — está comprometido. E o
enquadramento ("pacientes vêm de outras cidades para implante") converte parte de quem
teria desistido sozinho.

---

## Passo 6 — Handoff para o humano

> Prontinho! ✨
>
> Já passei tudo para a nossa recepção — ela vai confirmar o melhor horário com você
> aqui mesmo, em instantes.
>
> 📍 {endereço da unidade}
> 🗓️ Segunda a sexta, de 08:00 às 12:30 e 13:30 às 18:30

> Enquanto isso, já nos segue no Instagram? 😁
> @masterclinicipatinga
> @dradaniellecarvalho
> @drwiltonvargas.dentista

**Ações:**
- tags `AGUARDANDO-AGENDAMENTO` + `CONVERSOU` + `Novo Paciente`
- move o card para a etapa **Consulta** do funil da unidade
- **notificação interna** para a recepção, com a unidade identificada
- `stop-chat-automations-action` — **o bot para naquela conversa**; humano assume

A tag `AGUARDANDO-AGENDAMENTO` é também o sinal que interrompe a cadência de resgate.

---

## O que o bot nunca diz

| Tema | Por quê | Quem responde |
|---|---|---|
| **Convênio / Brasil Sorridente** | é objeção — antecipar derruba o lead | humano, se o lead levantar |
| **Preço, valor** | sem diagnóstico, preço vira objeção | o doutor, na consulta |
| **Parcelamento** | idem | o financeiro, na clínica |
| **Atendimento social das quartas** | é argumento de contorno, não de abertura | humano, ao tratar a objeção de convênio |

Os textos que a recepção já usa para essas objeções estão registrados na
[análise](analise-conversas-trafego.md#5-regras-de-negócio-a-codificar-no-bot) — inclusive
o do atendimento social, que continua sendo uma carta forte **na hora certa**: quando o
lead diz que só tem convênio, e não antes.

---

## Como o "só por botão" trata os desvios

Todo bloco de pergunta tem `nextBlockId: ""` e só avança pelo botão. Na prática:

| Lead faz | O que acontece |
|---|---|
| Clica no botão | fluxo avança |
| **Digita texto livre** (pergunta preço, endereço, "oi") | fluxo **não avança** — o resgate cutuca em 30 min repetindo a pergunta com os botões |
| **Manda áudio** | idem — sai do caminho crítico, que era o objetivo |
| Não responde nada | cadência de resgate |

Foi a escolha explícita: em vez de tentar interpretar texto livre (e errar), o bot mantém
o lead no trilho. **Quem trata objeção é o humano** — e é assim que tem que ser, porque
objeção se contorna com escuta, não com resposta automática.

Se o lead digitar *"vocês atendem Unimed?"*, o bot não responde. A conversa fica visível
para a recepção, que assume. O padrão de resposta extraído das conversas reais, para uso
dela:

| Objeção | Resposta da clínica |
|---|---|
| **Convênio / plano** | *A Master Clinic não atende convênios, apenas consultas particulares.* → e então a carta forte: *Como alternativa, o Dr. Wilton realiza atendimento social às quartas-feiras. Nesse dia, a consulta é realizada mediante a doação de 1 kg de alimento não perecível, que será destinado a ações sociais. Se desejar, posso verificar um horário disponível para você.* |
| **Valor** | *Sobre valores, quem te passa certinho é o próprio doutor, no dia da consulta — depende da avaliação do seu caso 🙏🏼* |
| **Parcelamento** | *O parcelamento é direto com nosso financeiro. Na sua consulta eles te explicam todas as opções 💚* |
| **Currículo / vaga** | *Para vagas, é só enviar seu currículo por este formulário: https://forms.gle/97hYFUyH82yCu4Sc8* |

Repare que a resposta de convênio **termina puxando o agendamento** — acolhe, reenquadra e
volta para o horário. É o mesmo movimento do bot, feito por gente.

---

## Cadência de resgate (automação separada por unidade)

Dispara quando o lead ganha a tag `CONVERSOU` (entrada no chatbot) e **para** assim que
ele ganha `AGUARDANDO-AGENDAMENTO` — condição checada antes de cada mensagem.

| Quando | Mensagem |
|---|---|
| **+30 min** | *Oi! Conseguiu ver minha mensagem? 😊 É rapidinho — só pra eu organizar seu atendimento com a nossa recepção.* |
| **+4 h** | *Passando aqui de novo pra não te deixar sem resposta 🙏🏼 Ainda quer que eu veja um horário pra você?* |
| **+1 dia** | *Oi! A agenda costuma fechar rápido 🗓️ Quer que eu reserve um horário no seu nome?* |
| **+3 dias (breakup)** | *Vou encerrar seu atendimento por aqui pra não te incomodar, tá bom? 💚 Quando precisar, é só me mandar uma mensagem que a gente te atende na hora. Fica com Deus 🙏🏼* → tag `PERDIDO-BREAKUP` + perde o card |

"Conseguiu ver minha mensagem?" é a frase que a recepção já usa — mantida de propósito.

---

## Fluxo separado: canal Gerência (vaga de emprego) — **não implementado**

Não faz parte dos `.dc` gerados. Fica documentado para quando o anúncio de vaga voltar
a rodar. Mesmo gatilho CTWA, canal `Gerência Uazapi`:

> Olá! Tudo bem? 😊 Aqui é a Master Clinic.
> Vi que você tem interesse na nossa vaga!

> Pedimos por gentileza que preencha esse formulário e anexe seu currículo.
> Se o seu perfil atender aos requisitos, vamos analisar e entramos em contato
> para dar continuidade ao processo. Muito obrigada! 🙏🏽✨
> https://forms.gle/97hYFUyH82yCu4Sc8

→ tag `RH-CANDIDATO`, sem card comercial, sem handoff para recepção.

*Por quê:* 19 das 118 conversas de tráfego são currículo. Hoje consomem a recepção
comercial e viram ruído no funil.

---

## Pendências que sobraram

1. **Endereço da unidade Mesquita** — está como placeholder nos `.dc`.
2. **Transcrição de áudio** — 43 dos 99 leads envolveram áudio. Como o bot só aceita
   botão, o áudio do lead não avança o fluxo; o resgate cutuca em 30 min. Para tratar
   áudio de verdade, o caminho é o bloco `ai` → `audio-transcription-ai`.
3. **Quem recebe o handoff** — a notificação vai para todos hoje (`attendantsIds: []`).
   Definir o rodízio por unidade no painel.
4. **Anúncio de vaga** — cai no canal `Gerência Uazapi` com as mesmas aberturas CTWA
   (19 das 118 conversas). Se voltar a rodar, precisa de um `.dc` de RH separado.

---

## Implementação

Cada unidade virou **dois `.dc`**: o chatbot e a cadência de resgate.

**Por que dois:** um bloco de mensagem com botões **pausa a automação até o clique** —
é exatamente isso que força o lead a usar os botões. Como o fluxo fica parado ali, uma
cadência em série nunca dispararia. O resgate roda como automação própria, disparada pela
tag `CONVERSOU` e parando assim que o lead ganha `AGUARDANDO-AGENDAMENTO`.

| Arquivo | Canal | Blocos |
|---|---|---|
| [`1-ipatinga-chatbot.dc`](../dc-trafego/1-ipatinga-chatbot.dc) | Oficial Master Clinic (Cloud API) | 22 |
| [`1-ipatinga-resgate.dc`](../dc-trafego/1-ipatinga-resgate.dc) | Oficial Master Clinic | 14 |
| [`2-mesquita-chatbot.dc`](../dc-trafego/2-mesquita-chatbot.dc) | Mesquita Uazapi | 22 |
| [`2-mesquita-resgate.dc`](../dc-trafego/2-mesquita-resgate.dc) | Mesquita Uazapi | 14 |

Gerados por [`scripts/gerar_dc_trafego.py`](../scripts/gerar_dc_trafego.py), que valida
UUIDs, conexões órfãs, o limite de 3 botões e **os nomes de componente contra a spec do
formato `.dc`** (`~/.claude/skills/datacrazy-automacoes/references/formato-dc-completo.md`).

IDs já mapeados no tenant:

| Recurso | ID |
|---|---|
| Pipeline **Vendas - Ipatinga** | `10cd55a8-b076-4119-b3bc-333b295f5a42` |
| └ etapa **Lead** (gatilho) | `218e4105-52a3-4591-8d70-3bced5b289c1` |
| └ etapa **Consulta** (handoff) | `784b415e-5d51-417e-9ba1-eceb371188a1` |
| Pipeline **Vendas - Mesquita** | `7c922803-5c98-4733-9f72-55189ac97916` |
| └ etapa **Lead** (gatilho) | `93d6050a-c790-40f9-a213-4f07803ac013` |
| └ etapa **Consulta** (handoff) | `ce634311-aabc-4f69-9280-bf7817f8bdd6` |
| Tag `AGUARDANDO-AGENDAMENTO` | `7309d983-fefa-4b83-93be-fe1d7b2131c0` |
| Tag `CONVERSOU` | `09e51ab5-96ab-4955-bf61-cf13120bd880` |
| Tag `Requer Retorno` | `cc8ae801-9bd3-413a-b0d6-ff47cb990f84` |
| Tag `Convênio Pendente` | `75740cd4-34c7-444a-9679-fa77f0a6bbc0` |
| Tag `PERDIDO-BREAKUP` | `81db8417-cae7-4291-8098-3c44cb272db8` |
| Tag `Novo Paciente` | `e424604f-2966-4722-9339-c8b35d887a7f` |

O chatbot **não** usa mais `Tráfego Pago` nem `LEAD`: elas são responsabilidade do fluxo
que cria o lead e o card. Nenhuma tag nova precisa ser criada.

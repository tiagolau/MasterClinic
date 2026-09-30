# Plano — Chatbot de Agendamento (Mentoria Dr. Wilton Vargas)

**Data:** 2026-07-14
**Status:** proposta (aguardando validação para virar .dc)
**Pipeline:** Mentoria Dr. Wilton Vargas (`554040d1-43dc-42a1-9954-f349a0c12c49`)
**Inspiração:** funil high ticket do Renan Vieira (mentor do Dr. Wilton) — ver
`Funil High Ticket mensagens whatsapp mentoria.pdf`

---

## 1. Visão geral do funil

```
Tráfego pago (Meta) ──> Landing Page ──> Formulário de qualificação
                                              │
                                    POST cria Lead no DataCrazy
                                    (source: LP-MENTORIA-WILTON)
                                              │
                          ┌───────────────────┴───────────────────┐
                          │                                        │
              Lead clica no wa.me e ENVIA msg         Lead NÃO envia msg
                    (caminho QUENTE)                    (caminho FRIO)
                          │                                        │
                 Gatilho: Mensagem Recebida            Gatilho: Lead Criado
                          │                             + delay 10 min
                          │                                        │
                          └──────────────> CHATBOT <───────────────┘
                                              │
                          Saudação + valor + CTA "agendar reunião"
                                              │
                                  Envia link Cal.com (pré-preenchido)
                                              │
                          Cal.com BOOKING_CREATED ──webhook──> DataCrazy
                                              │
                                 Card → "Reunião Agendada"
                                              │
                     Lembrete no dia · No-show → recuperação
                                              │
                          Reunião → Dr. Wilton fecha (closer)
                                     │              │
                                  Ganho          Perdido
```

O chatbot **não fecha a venda** — o fechamento high ticket é feito pelo Dr. Wilton
na reunião (como no funil do Renan). O papel do bot é: **reengajar, dar contexto/valor
e levar o lead qualificado até o horário agendado no Cal.com**, com a menor fricção possível.

---

## 2. Decisão crítica: qual número/canal usar

O comportamento do reengajamento de 10 min depende do provider:

| Canal | Reengajar quem não respondeu | Risco | Recomendação |
|---|---|---|---|
| **Evolution API** (*Atendimento Mesquita* / *Gerência*) | Mensagem **livre**, sem template, a qualquer hora | Ban se houver spam/volume alto para não-contatos | ✅ **Recomendado** — volume é baixo (leads de tráfego qualificado que pediram contato) |
| **Cloud API** (*Recepção* / *CRC* / *Oficial*) | Só via **template WABA aprovado** (fora da janela 24h) | Zero risco de ban, mas exige template aprovado + custo por conversa | Alternativa "by the book" |

**Recomendação:** usar um número **Evolution API** dedicado à mentoria (ou criar um novo).
O lead já demonstrou interesse ativo (preencheu formulário de tráfego pago), então a
mensagem em 10 min é esperada — baixo risco. Se preferir o caminho oficial, dá para
reaproveitar a expertise de templates WABA deste próprio projeto (skill `templates-waba`)
e submeter um template de reengajamento (categoria UTILITY).

> Uma vez que o lead responde qualquer coisa, a janela abre e **todo o resto do chatbot
> roda com mensagem livre** independente do canal.

---

## 3. Integração com Cal.com

Cal.com não é nativo do DataCrazy — integra por **link + webhook** (bloco `api`/HTTP).

**Abordagem recomendada — "link gerenciado" (robusta):**

1. Dr. Wilton cria um **event type** no Cal.com (ex.: *Reunião de Diagnóstico — 30 min*),
   com a disponibilidade real dele.
2. O chatbot envia o **link do Cal.com pré-preenchido** com os dados do formulário para
   reduzir fricção:
   ```
   https://cal.com/dr-wilton/diagnostico?name={leadName}&email={leadEmail}&notes=Lead+mentoria
   ```
3. Cal.com dispara **webhook `BOOKING_CREATED`** para uma rota HTTP do DataCrazy →
   Automação 3 confirma, move o card e agenda lembretes.
4. `BOOKING_CANCELLED` / no-show → trilha de recuperação.

Isso mantém o espírito do Renan (oferecer horário e conduzir ao agendamento), mas o
**Cal.com garante disponibilidade real** — melhor que fixar "10h ou 18h" no texto.

*Alternativa avançada (fase 2):* o bot puxa os slots via API do Cal.com (`GET /slots`),
mostra 2–3 opções em botões e cria o booking via `POST /bookings` — tudo dentro do
WhatsApp. Mais elegante, porém mais frágil; só vale se a fricção do link se provar alta.

---

## 4. Mapeamento: funil do Renan → chatbot no DataCrazy

| Nó do funil do Renan | Tradução no DataCrazy | Etapa da pipeline |
|---|---|---|
| Abordagem / "ligo direto" | Mensagem de abertura (quente ou proativa em 10 min) | Novo Lead |
| Não atendeu → msg + áudio + 2 horários | Cadência de resgate (texto → áudio → botão agendar) | Novo Lead → Qualificado |
| "Qual das duas opções prefere?" | CTA de agendamento → link Cal.com | Qualificado |
| Agenda reunião | Webhook Cal.com `BOOKING_CREATED` | Reunião Agendada |
| "Dia da reunião — lembro que vou ligar" | Lembrete automático no dia | Reunião Agendada |
| No-show → recuperação p/ remarcar | Trilha no-show (novo link Cal.com) | Reunião Agendada |
| Aplica script / encerra ligação | Reunião com Dr. Wilton (closer humano) | Reunião Realizada |
| "Enviou link de pagamento → aguardando compra" | Tag `AGUARDANDO-COMPRA` + follow-up 1h/dia seguinte | Reunião Realizada |
| Comprou → ótimo | `business_won` | Fechado / Matriculado |
| "Não desiste até levar um não" / breakup | Follow-up de objeções → breakup → `business_lose` | Perdido |
| Figurinha "Deus está vendo que esqueceu de mim" | Sticker de resgate (adaptar tom à marca) | — |

---

## 5. Automações (arquivos .dc a gerar)

Cada uma é um fluxo separado no DataCrazy. Todas nascem com `active: false` para teste.

### Automação 1 — `MENTORIA · Reengajamento 10min`
- **Gatilho:** Lead Criado (filtro source/tag `LP-MENTORIA-WILTON`)
- Cria card em **Novo Lead** · tag `FORM-RESPONDIDO`
- `delay 10min`
- **Condição:** tem tag `CONVERSOU`?
  - **Sim** → encerra (o caminho quente já assumiu)
  - **Não** → tag `REENGAJADO-10MIN` → dispara mensagem de abertura → chama Automação 2

### Automação 2 — `MENTORIA · Chatbot Agendamento` (núcleo)
- **Gatilho:** Mensagem Recebida (instância da mentoria) *ou* iniciada pela Automação 1
- Ações: tag `CONVERSOU`, parar automação de reengajamento
- **Chat 1 (saudação):** "Oi {leadName}! Aqui é a equipe do Dr. Wilton Vargas 😊
  Vi que você preencheu nosso formulário da mentoria…"
- **Chat 2 (valor):** mensagem ou **áudio pré-gravado** — o que a mentoria destrava
  (referência ao Renan/Dr. Wilton, prova, transformação)
- **Chat 3 (botões, máx 3):** `Quero agendar` · `Tenho uma dúvida`
  - **Dúvida** → responde FAQ / transfere a atendente → volta ao CTA
  - **Agendar** → move card **Qualificado** · tag `AGUARDANDO-AGENDAMENTO` → envia link Cal.com
- **Cadência de resgate** (se não agendar/responder — inspirada no Renan):
  - `+2h` → "?" / lembrete leve para subir a conversa
  - `+1 dia` → áudio/mensagem de reforço + reenvia link
  - `+2 dias` → sticker de resgate (tom adaptado)
  - `+3 dias` → **breakup** → move **Perdido** · tag `PERDIDO-BREAKUP`

### Automação 3 — `MENTORIA · Cal.com Booking Confirmado`
- **Gatilho:** Webhook HTTP (rota `/calcom-mentoria`, `BOOKING_CREATED`)
- `javascript`: extrai nome, email, telefone, data/hora do payload
- **Condição:** localiza lead (email/telefone)
- Ações: move card **Reunião Agendada** · tag `REUNIAO-AGENDADA` · remove `AGUARDANDO-AGENDAMENTO` · para cadência de resgate
- **Chat:** "Perfeito {leadName}! Sua reunião com o Dr. Wilton está confirmada para
  {data} às {hora}. 📅"
- Cria atividade / agenda lembrete (Automação 4)

### Automação 4 — `MENTORIA · Lembrete + No-show`
- **Lembrete:** `delay` até a data do booking → "Hoje é o dia! O Dr. Wilton te espera às {hora} 👇" · tag `LEMBRETE-ENVIADO`
- **No-show:** webhook Cal.com (cancel/no-show) *ou* condição pós-horário → tag `NO-SHOW`,
  trilha de recuperação (novo link Cal.com), `EM-RECUPERACAO`

### Automação 5 — `MENTORIA · Pós-reunião / Fechamento` *(fase 2, semi-automática)*
- Baseada no script de fechamento do Renan (link de pagamento → aguardando compra →
  follow-up 1h → dia seguinte → quebra de objeções). O closer é o Dr. Wilton;
  o DataCrazy entra com **etiquetas + lembretes para o closer** e cadência de follow-up.

---

## 6. Etiquetas / tags do funil

`LP-MENTORIA-WILTON` (source) · `FORM-RESPONDIDO` · `CONVERSOU` · `REENGAJADO-10MIN` ·
`AGUARDANDO-AGENDAMENTO` · `REUNIAO-AGENDADA` · `LEMBRETE-ENVIADO` · `NO-SHOW` ·
`EM-RECUPERACAO` · `AGUARDANDO-COMPRA` · `MATRICULADO` · `PERDIDO-BREAKUP`

## 7. Campos customizados (do formulário de qualificação)

A definir conforme as perguntas do form (ex.: CRO, tempo de atuação, tem consultório,
faturamento atual, especialidade, principal desafio). Guardados como `additional-field[...]`
no lead e exibidos no card para o Dr. Wilton chegar na reunião já contextualizado.

---

## 8. Pré-requisitos (o que precisa existir antes de gerar os .dc)

1. **Número/canal escolhido** (decisão da seção 2) — Evolution API recomendado.
2. **Cal.com do Dr. Wilton**: event type + disponibilidade + webhook `BOOKING_CREATED`
   apontando para a rota HTTP do DataCrazy.
3. **Landing + formulário**: POST criando o lead no DataCrazy com source `LP-MENTORIA-WILTON`
   e botão final `wa.me` do número da mentoria (com mensagem pré-preenchida).
4. **Campos customizados** criados no DataCrazy batendo as perguntas do form.
5. **Textos e áudio** de abertura/valor aprovados pelo Dr. Wilton (tom da marca).

---

## 9. Próximos passos sugeridos

1. Definir canal (Evolution vs Cloud API) e número da mentoria.
2. Configurar o Cal.com (event type + webhook).
3. Fechar os textos/áudio do chatbot (posso rascunhar inspirado no Renan, adaptado à
   odontologia/Dr. Wilton).
4. Gerar os `.dc` das Automações 1–4 (fase 1) e importar desativados para teste.
5. Testar ponta a ponta com um lead-teste; depois ativar.

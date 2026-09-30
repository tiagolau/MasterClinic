# Copy Deck — Chatbot Mentoria Dr. Wilton Vargas

**Data:** 2026-07-14
**Status:** rascunho para aprovação do Dr. Wilton
**Base:** cadência high ticket do Renan Vieira, adaptada ao tom consultivo/odontológico
**Acompanha:** `plano-chatbot-agendamento-datacrazy.md`

---

## Notas de tom

- **Renan** é direto e agressivo (figurinha "Deus está vendo…", breakup "vou para o
  próximo"). Aqui o tom é **consultivo, caloroso e profissional** — o Dr. Wilton é
  referência clínica, não um vendedor de infoproduto. Mantemos a **espinha de
  conversão** (escassez, prova, condução ao agendamento), suavizando o linguajar.
- Mensagens curtas, quebradas em balões (estilo WhatsApp real).
- Emojis com parcimônia (1 por balão no máximo).
- Variáveis DataCrazy: `{leadName}` / `leadFirstName`. Botões: máx 3, textos curtos.

## Valores preenchidos (provisórios — Dr. Wilton troca depois de funcionar)

Os `.dc` gerados já usam estes valores. Trocar quando o Dr. Wilton definir os oficiais:

| Placeholder | Valor usado |
|---|---|
| `[PROMESSA]` | "estruturar o consultório para faturar com previsibilidade e sair do operacional" |
| `[PROVA]` | "é referência em gestão e crescimento de consultórios odontológicos" *(sem número inventado — trocar por dado real: "+X dentistas mentorados")* |
| `[NOME_MENTORIA]` | "Mentoria Dr. Wilton Vargas" |
| `[DURACAO_CALL]` | 30 minutos |
| Link Cal.com | `https://cal.com/dr-wilton/diagnostico?name={leadFirstName}&email={leadEmail}` *(placeholder — trocar pelo real)* |

---

## A. Abertura

### A1. Caminho QUENTE (lead mandou mensagem primeiro)
> Oi {leadName}! 👋 Aqui é a equipe do Dr. Wilton Vargas.
>
> Vi que você preencheu o formulário da mentoria `[NOME_MENTORIA]` — que bom te ver por aqui!
>
> Posso te explicar rapidinho como funciona e já deixar sua conversa com o Dr. Wilton agendada?

### A2. Caminho FRIO (não respondeu em 10 min — mensagem proativa)
> Oi {leadName}, tudo bem? 😊 Aqui é a equipe do Dr. Wilton Vargas.
>
> Você preencheu o formulário da nossa mentoria há pouco e queria garantir que seu
> lugar não se perca.
>
> Tenho uma novidade rápida sobre como o Dr. Wilton pode te ajudar a `[PROMESSA]`. Posso te contar?

*(Ambas seguem para o bloco B.)*

---

## B. Mensagem de valor

### B1. Versão texto
> A mentoria do Dr. Wilton é para dentistas que querem `[PROMESSA]` — sem depender de
> sorte ou de trabalhar cada vez mais horas.
>
> Ele já `[PROVA]`, e agora abriu um número limitado de vagas para acompanhar dentistas
> de perto.
>
> O primeiro passo é uma **conversa de diagnóstico** (rápida, `[DURACAO_CALL]`) direto
> com ele, pra entender seu momento e ver se faz sentido pra você.

### B2. Roteiro do áudio (30–45s, gravado pela equipe/Dr. Wilton)
> "Oi {leadName}, aqui é o Dr. Wilton! Que bom que você se interessou pela mentoria.
> Olha, eu criei esse programa porque vejo muitos dentistas excelentes clinicamente,
> mas presos no operacional, sem conseguir `[PROMESSA]`. Na nossa conversa de diagnóstico
> eu vou entender exatamente o seu momento e te mostrar o caminho — sem compromisso.
> Bora marcar? Escolhe o melhor horário pra você que eu te espero lá."

*Nota: o áudio aumenta muito a conexão no high ticket (é o "áudio do Renan").
Recomendo gravar na voz do próprio Dr. Wilton.*

---

## C. CTA / botões

> Quer agendar sua conversa de diagnóstico com o Dr. Wilton? 👇

**Botões:** `Quero agendar` · `Tenho uma dúvida`

---

## D. Ramo "Tenho uma dúvida"

> Claro, {leadName}! Me conta rapidinho qual é a sua dúvida que eu te ajudo. 😊
>
> *(Se for algo fora do script → transfere para atendente humano.)*

*Após esclarecer, retoma o CTA da seção C.*

---

## E. Envio do link Cal.com (botão "Quero agendar")

> Perfeito, {leadName}! 🙌
>
> É só escolher o melhor dia e horário neste link — já vai preenchido com seus dados:
>
> 👉 https://cal.com/dr-wilton/diagnostico?name={leadName}&email={leadEmail}
>
> Assim que você confirmar, eu te mando a confirmação por aqui. Te espero! 😊

---

## F. Cadência de resgate (não agendou / parou de responder)

### F1. +2h — subir a conversa
> {leadName}, conseguiu escolher um horário? 😊 Se tiver qualquer dificuldade com o
> link, me fala que eu te ajudo por aqui.

### F2. +1 dia — reforço de valor + reenvio
> Oi {leadName}! Não quero que você perca essa chance de conversar direto com o Dr. Wilton.
>
> As vagas da mentoria são limitadas e os horários de diagnóstico enchem rápido.
>
> Segue o link de novo, é bem rapidinho: 👉 https://cal.com/dr-wilton/diagnostico?name={leadName}&email={leadEmail}

### F3. +2 dias — resgate leve (substitui a "figurinha" do Renan)
> {leadName}, passando aqui de novo 👀 Seria uma pena deixar seu diagnóstico com o
> Dr. Wilton pra trás. Bora marcar?

*(Opcional: um sticker leve da marca no lugar da figurinha do Renan — tom elegante,
nada religioso/agressivo.)*

### F4. +3 dias — breakup (elegante, com escassez)
> {leadName}, vou encerrar seu atendimento por aqui pra liberar o horário para outro
> dentista na fila. 🙏
>
> Se mudar de ideia, é só me mandar uma mensagem que eu reservo um novo horário com o
> Dr. Wilton pra você. Sucesso! 😊

*→ move card para **Perdido** (tag `PERDIDO-BREAKUP`).*

---

## G. Confirmação de agendamento (webhook Cal.com)

> Prontinho, {leadName}! ✅ Sua conversa de diagnóstico com o Dr. Wilton está confirmada:
>
> 📅 {data} às {hora}
>
> Vou te enviar um lembrete no dia. Qualquer imprevisto, é só me avisar por aqui. Até lá! 😊

---

## H. Lembrete no dia da reunião

> Bom dia, {leadName}! ☀️ Hoje é o dia da sua conversa com o Dr. Wilton, às {hora}.
>
> Separa uns minutinhos num lugar tranquilo — vai ser muito produtivo. Te espero! 🙌

---

## I. No-show / recuperação

### I1. Logo após o horário perdido
> {leadName}, senti sua falta na conversa com o Dr. Wilton hoje. 😕 Aconteceu algum
> imprevisto?
>
> Sem problema — bora remarcar? Escolhe um novo horário aqui: 👉 https://cal.com/dr-wilton/diagnostico?name={leadName}&email={leadEmail}

### I2. +1 dia sem remarcar
> Oi {leadName}! O Dr. Wilton ainda tem um horário reservado pra te ouvir. Quer que eu
> garanta pra você antes que preencha? Só me mandar "sim".

*(Se seguir sem resposta → cadência F3/F4.)*

---

## Resumo de uso por automação

| Automação | Textos usados |
|---|---|
| 1 · Reengajamento 10min | A2 → B → C |
| 2 · Chatbot Agendamento | A1 → B → C → D → E → F1–F4 |
| 3 · Booking Confirmado | G |
| 4 · Lembrete + No-show | H · I1 · I2 |

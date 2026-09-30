# Análise das conversas de WhatsApp — Master Clinic

**Data:** 2026-07-29
**Fonte:** raspagem completa do DataCrazy (tenant `69937b06-43cd-40d2-bd39-d3d3c9223283`)
**Volume:** 1.687 conversas (1.679 com mensagens), 7.436 leads, 8 canais conectados

Gerado por [scripts/raspar_conversas_datacrazy.py](../scripts/raspar_conversas_datacrazy.py)
+ [scripts/analisar_conversas.py](../scripts/analisar_conversas.py).
Dados brutos em `data/` (não versionado).

---

## 1. Como identificamos o que veio de tráfego

Testamos quatro sinais. Só um se provou confiável:

| Sinal | Veredito |
|---|---|
| `lead.sourceReferral` (CTWA nativo) | **Vazio em 100% dos 7.436 leads** — o DataCrazy não está gravando o referral do anúncio |
| `lead.source` | **Nulo em 100%** dos leads |
| Tag **"Tráfego Pago"** (533 leads) | **Não confiável** — aparece em conversa interna da equipe, cobrança de boleto e fornecedor. Foi aplicada em massa, não por origem real |
| **Mensagem pré-preenchida do Click-to-WhatsApp** | ✅ **Confiável** — é o texto que o anúncio injeta no WhatsApp do lead |

As aberturas de anúncio encontradas (assinatura do tráfego):

| Ocorrências | Texto que o anúncio pré-preenche |
|---|---|
| 32 | `Olá! Tenho interesse e queria mais informações, por favor.` |
| 26 | `Olá! Posso saber mais informações sobre isto?` |
| 22 | `Olá! Diga como podemos ajudar você.`<br>`Obs: não atendemos pelo Brasil Sorridente.` |
| 15 | `Olá! Posso ter mais informações sobre isso?` |
| 10 | `Olá! Tenho interesse. Gostaria de informações, por favor!` |
| 6 | `Olá, vim pelo site.` |
| 4 | `Olá! Tenho interesse em levar meu filho. Gostaria de informações, por favor!` (campanha de odontopediatria) |

> **Falso positivo descartado:** `campaign_event_trigger` (44 ocorrências) parece tráfego mas é
> clique em botão de lembrete de consulta — paciente já da casa, não lead novo.

**Resultado:** **118 conversas de tráfego confirmado**, das quais **99 são de paciente**
e **19 são de candidatos a vaga de emprego**.

---

## 2. O tráfego cai em três canais, e um deles é de RH

| Canal | Tipo | Tráfego total | Sendo paciente |
|---|---|---|---|
| **Oficial Master Clinic** (Cloud API, WABA `306417967823808`) | Ipatinga | 63 | 62 |
| **Mesquita Uazapi** (não-oficial) | Unidade Mesquita | 19 | 19 |
| **Gerência Uazapi** (não-oficial) | **Vaga de emprego** | 36 | 18 |

O canal **Gerência** recebe CTWA de anúncio de **vaga**, com a mesma abertura pré-preenchida
das campanhas de paciente. O chatbot precisa desviar esse fluxo — ou vai oferecer consulta
odontológica para quem quer mandar currículo.

Canais ociosos: **Recepção Master Clinic** (+55 31 8469-7236, Cloud API) e **CRC Master Clinic**
(inativa). Instagram e Messenger do Dr. Wilton recebem volume marginal.

---

## 3. Onde o dinheiro do tráfego está vazando

### 3.1 Ninguém responde na hora — e metade nunca volta

| Métrica (99 leads de tráfego/paciente) | Valor |
|---|---|
| Nunca receberam resposta | **17 (17%)** |
| Lead mandou 1 mensagem só e a conversa morreu | **51 (52%)** |
| Esperaram mais de 1 hora pela 1ª resposta | 26 de 82 (32%) |
| Esperaram mais de 6 horas | 12 de 82 |
| Pior caso | **2 dias** (48h) |
| Chegaram fora do horário comercial | **31 (31%)** |

Casos reais: lead escreveu **03:01** → resposta às **13:04**. Lead de **25/07 18:54** →
resposta em **27/07 12:56** (42h). O anúncio roda 24h; a recepção atende 8h–18h30.

### 3.2 O tráfego traz gente de fora da região

| Grupo | DDD fora de 31/33 |
|---|---|
| Leads de tráfego | **18 de 99 — 18%** |
| Base geral de conversas | 97 de 1.139 — 8,5% |

O tráfego traz **o dobro** de leads de fora da região. Nas transcrições aparecem
**Uberlândia, Juiz de Fora, Teófilo Otoni, Curvelo, Ipuiúna** — e a conversa morre em
*"Muito longe, me desculpe."*

A própria equipe já mediu isso. Extraído de uma conversa interna de 28/07:

> Foi um total de quantos leads? **19**
> Quantos de fora? **18**
> Quantos da Ipatinga e região? **1**
> Quantas interações? **10**
> Quantos agendamentos? **0**

### 3.3 Convênio é a objeção nº 1

**20 dos 99 leads de tráfego (20%)** perguntam sobre convênio ou plano logo de cara —
Amil, Unimed, **Usisaúde**, **Usiodonto**, "plano da Vale", Brasil Sorridente, SUS.
Em Ipatinga isso é estrutural (cidade da Usiminas). Na base inteira são 38 menções.

A clínica **não atende convênio nenhum**. Hoje isso só é descoberto depois de horas de espera.

### 3.4 Atendimento por áudio derruba conversa

**43 dos 99** leads de tráfego foram respondidos por áudio (no canal Mesquita é a norma).
Resultado registrado numa conversa:

> LEAD: *Agradeço, a gravação está muito ruim*
> LEAD: *Não entendi nada*
> LEAD: *Eu não estou interessada*

---

## 4. Tom de voz da clínica

Extraído das mensagens outbound mais repetidas — é o padrão que o bot deve imitar.

### Assinatura pessoal, sempre com nome próprio
```
Boa tarde, tudo bem? Meu nome é Jhovanna, sou recepcionista aqui na Master Clinic.✨🙏🏼
```
```
Olá, Bom dia, tudo bem ?!
O meu nome é Jhessilee, e faço parte da equipe da Master Clinic✨💚
```
Recepção assina como **Jhovanna**, **Jhessilee**, **Larissa**; financeiro como **Grasiele**.

### Boas-vindas automática (72 disparos)
```
Seja bem-vindo a Master Clinic !
Já nos segue no Instagram ?
@masterclinicipatinga
@dradaniellecarvalho
@drwiltonvargas.dentista

Te retorno o mais breve possível.

🔴Nosso horário de funcionamento:
Segunda a sexta de 08:00 às 12:30 e 13:30 às 18:30.
```

### Características do tom
- **Pergunta "tudo bem?" sempre** — abertura obrigatória, nunca entra direto no assunto
- **Emojis moderados e afetivos:** ✨ 🙏🏼 😁 🗓️ 💚 🤗 🛑 ⚠️
- **Mensagens curtas quebradas em várias** — raramente um bloco só
- **Itálico com `_`** para fechamentos: `_Agradecemos a confirmação, até amanhã 🙏🏻🤗_`
- **Negrito com `*`** para data/hora: `*quarta-feira*, dia 29/07/2026, às *11:00hs*`
- **Confirmações secas e calorosas:** "Por nada!!", "Combinado!!", "Agendado", "Aguardo retorno!😁"
- **Trata por "o senhor / a senhora"** com pacientes mais velhos
- **Nunca usa jargão clínico** com o paciente

### Perguntas que a recepção faz (o roteiro humano atual)
| Frequência | Pergunta |
|---|---|
| 24 | *Já nos segue no Instagram?* |
| — | *Poderia me informar seu nome completo por favor?* |
| — | ***De qual cidade a senhora é?*** / *Pode me informar qual seu nome e de qual cidade é?* |
| — | *Poderia me informar seu nome e do seu filho?* (odontopediatria) |
| — | *Você prefere de manhã ou de tarde?* / *Tem alguma restrição de horário?* |
| — | *Em que posso te ajudar?* |

---

## 5. Regras de negócio a codificar no bot

Todas extraídas literalmente das conversas:

1. **Não atende convênio** — só particular.
   > *"A Master Clinic não atende convênios, apenas consultas particulares."*
2. **Não atende Brasil Sorridente** (já está na saudação do anúncio).
3. **Atendimento social como alternativa:**
   > *"O Dr. Wilton realiza atendimento social às quartas-feiras. Nesse dia, a consulta é
   > realizada mediante a doação de 1 kg de alimento não perecível, que será destinado a
   > ações sociais."*
4. **Bot NÃO passa valores.**
   > *"Sobre valores, é apenas com o Dr., no dia da consulta, ele vai te dizer certinho"*
5. **Parcelamento é com o financeiro.**
   > *"Sobre as parcelas não consigo dizer, porque é com o financeiro"*
6. **Endereço:** Av. Brasil, nº 685, Iguaçu, Ipatinga (+ unidade Mesquita).
7. **Horário:** segunda a sexta, 08:00–12:30 e 13:30–18:30.
8. **Coleta obrigatória para agendar:** nome completo, e-mail, cidade.
9. **Equipe clínica:** Dr. Wilton Vargas, Dra. Danielle Carvalho, Dr. Bruno (endodontia),
   Dr. Cristiano. Ortodontia tem dia próprio na agenda.

---

## 6. Procedimentos que os pacientes procuram

**Base inteira** (o que a clínica realmente atende no WhatsApp):

| Procedimento | Conversas |
|---|---|
| Urgência / dor | 32 |
| Prótese | 32 |
| Ortodontia (aparelho) | 28 |
| Limpeza | 28 |
| Implante | 21 |
| Odontopediatria | 16 |
| Canal | 15 |
| Restauração | 8 |

**Só nos leads de tráfego** o volume é baixo (implante 5, odontopediatria 5, prótese 2) —
não porque não haja interesse, mas porque **52% das conversas morrem antes de o lead dizer
o que quer**. É exatamente esse trecho que o chatbot precisa cobrir.

---

## 7. Diagnóstico em uma frase

O anúncio funciona (118 leads chegaram), mas o funil não existe: **17% nunca são respondidos,
31% chegam fora do expediente, 18% são de fora da região e 20% vêm com uma objeção de convênio
que a clínica não atende** — e tudo isso só é descoberto horas depois, por uma recepcionista
respondendo áudio a áudio.

O desenho do fluxo que resolve isso está em
[fluxo-chatbot-trafego-agendamento.md](fluxo-chatbot-trafego-agendamento.md).

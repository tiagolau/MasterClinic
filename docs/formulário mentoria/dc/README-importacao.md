# Importação dos .dc — Chatbot Mentoria Dr. Wilton

4 automações no formato nativo do DataCrazy, geradas por `../gerar_dc.py`.
Todas nascem **desativadas** (`active: false`). Tenant Master Clinic
(`69937b06-43cd-40d2-bd39-d3d3c9223283`), pipeline `Mentoria Dr. Wilton Vargas`.

| # | Arquivo | Status | Gatilho |
|---|---|---|---|
| 1 | `1-reengajamento-10min.dc` | ✅ completo | Lead criado |
| 2 | `2-chatbot-agendamento.dc` | ✅ completo | Mensagem recebida / iniciado pela Auto 1 |
| 3 | `3-calcom-booking-confirmado.dc` | ⚠️ esqueleto | Webhook HTTP (Cal.com) |
| 4 | `4-lembrete-no-show.dc` | ⚠️ esqueleto | Tag REUNIAO-AGENDADA adicionada |

## Ordem de importação

1. Importar **todas as 4** (Configurações → Automações → Importar).
2. Fazer as amarrações abaixo **antes de ativar**.

## Amarrações manuais obrigatórias (o .dc não carrega sozinho)

1. **Instância (canal WhatsApp)** — em **todos** os blocos de mensagem das Automações
   1, 2, 3 e 4, selecionar a instância que a mentoria vai usar. Ficou vazio de propósito
   (canal a definir). Instâncias disponíveis no tenant:
   - Evolution API (msg livre): `Atendimento Mesquita`, `Gerência`
   - Cloud API (template p/ reengajar): `Recepção`, `CRC`, `Oficial Master Clinic`

2. **Amarrar Auto 1 → Auto 2** — na Automação 1, bloco final *"iniciar outra automação"*,
   selecionar **"MENTORIA · Chatbot Agendamento"**. (Deixei `automationId` vazio porque o
   ID real só existe após a importação.)

3. **Link do Cal.com** — trocar `https://cal.com/dr-wilton/diagnostico` pelo link real do
   event type do Dr. Wilton (aparece nas Automações 2, 3 e 4). Já vai pré-preenchido com
   `?name={leadFirstName}&email={leadEmail}`.

4. **Variável de nome** — os textos usam `{leadFirstName}`. Ao abrir cada mensagem no
   editor, confirmar que o DataCrazy resolve a variável; se aparecer literal, reinserir
   pelo **menu de variáveis** do editor.

5. **Automação 3 (Cal.com webhook)** — validar com um teste real (`webhook.site`):
   - path do e-mail no payload: `payload.attendees[0].email` (ajustar se o Cal.com mudar);
   - configurar no Cal.com o webhook `BOOKING_CREATED` apontando para a **URL gerada no
     gatilho** desta automação.

6. **Automação 4 (lembrete/no-show)** — versão simples (lembra ao ganhar a tag
   REUNIAO-AGENDADA). Evoluir para `until-date-delay` com a data do booking + ramo de
   no-show quando a integração Cal.com estiver validada.

## Fonte de leads

A Automação 1 filtra `leadSource == "LP-MENTORIA-WILTON"`. A landing deve criar o lead no
DataCrazy com esse **source**. Se preferir usar **tag** em vez de source, trocar o bloco de
condição da Automação 1 por *"lead tem tag"* usando a tag `LP-MENTORIA-WILTON`.

## Teste ponta a ponta sugerido

1. Ativar Automações 1 e 2.
2. Criar um lead-teste com source `LP-MENTORIA-WILTON` e **não** mandar mensagem →
   em 10 min deve chegar a abertura fria.
3. Mandar mensagem a partir do número-teste → deve rodar saudação → valor → botões.
4. Clicar em *Quero agendar* → deve receber o link e o card ir para *Qualificado*.
5. Não agendar → conferir a cadência de resgate (encurtar os delays para testar).

## Regerar

Editar `../gerar_dc.py` (textos, delays, IDs) e rodar `python3 ../gerar_dc.py`.

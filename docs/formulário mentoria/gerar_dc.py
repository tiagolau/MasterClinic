#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador dos arquivos .dc do chatbot da Mentoria Dr. Wilton Vargas.
Monta o JSON nativo do DataCrazy com UUIDs e conexoes nextBlockId consistentes.
Ver: plano-chatbot-agendamento-datacrazy.md e copy-chatbot-mentoria.md
"""
import json, uuid, os, datetime

TENANT = "69937b06-43cd-40d2-bd39-d3d3c9223283"
PIPELINE = "554040d1-43dc-42a1-9954-f349a0c12c49"
OUT = os.path.join(os.path.dirname(__file__), "dc")
os.makedirs(OUT, exist_ok=True)

# ---- IDs reais (buscados via API/MCP) ----
STAGE = {
    "novo":       "1d50f3f2-c39c-4257-823f-f210a29e62b1",
    "qualificado":"4ad24dd6-ff9f-497f-9a68-e327a48a5fa4",
    "agendada":   "cf5d5a94-781b-46ae-ab1e-41171b6cd65e",
    "realizada":  "27c49502-2ef4-4fd2-8a50-9739355d46c4",
    "fechado":    "013c0b04-301d-43cf-ae76-6108eac10dee",
    "perdido":    "8022c949-47bc-43ef-8f5d-6aa344de58a8",
}
TAG = {
    "FORM-RESPONDIDO":        "47f85b09-938f-40e7-b5fa-ca5461d729c6",
    "CONVERSOU":              "09e51ab5-96ab-4955-bf61-cf13120bd880",
    "REENGAJADO-10MIN":       "1bb16dbe-cf1a-4723-b47b-a55e0067c396",
    "AGUARDANDO-AGENDAMENTO": "7309d983-fefa-4b83-93be-fe1d7b2131c0",
    "REUNIAO-AGENDADA":       "ec2b3f0d-c0a0-4132-a36e-194ea4c60296",
    "LEMBRETE-ENVIADO":       "4c060640-ebb2-4261-bf6d-5b6ad160933c",
    "NO-SHOW":                "a2a03306-259b-4adf-9231-de50c6218acf",
    "EM-RECUPERACAO":         "ebf8df37-e8f9-4f00-a5ec-31c73e547b3e",
    "AGUARDANDO-COMPRA":      "1dd2dee1-6935-40d3-b73f-9ec574fd94a0",
    "MATRICULADO":            "0d70c16d-e76c-4e10-8a52-b921804555c6",
    "PERDIDO-BREAKUP":        "81db8417-cae7-4291-8098-3c44cb272db8",
}

# instanceId vazio de proposito: selecionar o canal no painel ao importar.
INSTANCE = ""
SOURCE = "LP-MENTORIA-WILTON"
CALCOM = "https://cal.com/dr-wilton/diagnostico?name={leadFirstName}&email={leadEmail}"
NOW = "2026-07-14T12:00:00.000Z"

def uid(): return str(uuid.uuid4())

# ---------- helpers de bloco ----------
def trigger(triggers, nxt, x=200, y=0):
    return {"id": uid(), "type": "trigger", "sourceBlockId": None,
            "options": {"triggers": triggers, "nextBlockId": nxt},
            "presentation": {"x": x, "y": y}}

def chat_text(text, nxt="", buttons=None, x=200, y=0):
    msg = {"name": "send-text-message", "group": "messages", "stepId": uid(),
           "options": {"text": text, "buttons": buttons or [],
                       "breakMessages": True, "breakMessagesIntervalInSeconds": 2}}
    return {"id": uid(), "type": "chat", "sourceBlockId": None,
            "options": {"messages": [msg], "platform": "", "provider": "",
                        "timezone": "", "contactId": "", "instanceId": INSTANCE,
                        "nextBlockId": nxt if not buttons else "", "isAnnotation": False,
                        "scheduledDate": "", "errorNextBlockId": ""},
            "presentation": {"x": x, "y": y}}

def button(text, nxt):
    return {"id": uid(), "text": text, "type": "button", "nextBlockId": nxt}

def action(items, nxt, x=200, y=0):
    return {"id": uid(), "type": "action", "sourceBlockId": None,
            "options": {"actions": items, "nextBlockId": nxt},
            "presentation": {"x": x, "y": y}}

def a_add_tag(tag):   return {"name": "add-tag-action", "group": "lead", "options": {"tagIds": [TAG[tag]], "tagName": ""}}
def a_rm_tag(tag):    return {"name": "remove-tag-action", "group": "lead", "options": {"tagIds": [TAG[tag]], "tagName": ""}}
def a_create_biz(st): return {"name": "create-business-action", "group": "business", "options": {"stageId": STAGE[st]}}
def a_move_biz(st):   return {"name": "move-business-action", "group": "business", "options": {"stageId": STAGE[st]}}
def a_lose():         return {"name": "lose-business-action", "group": "business", "options": {"lossReasonId": "", "justification": "Breakup automatico - sem resposta"}}
def a_stop_bot():     return {"name": "stop-chat-automations-action", "group": "messages", "options": {"type": "current-conversation", "instanceId": INSTANCE}}
def a_start_auto():   return {"name": "start-another-automation-action", "group": "system", "options": {"automationId": "", "parameters": []}}
def a_notify(msg):    return {"name": "send-notification-action", "group": "system", "options": {"notification": msg, "url": "", "attendantsIds": []}}

def cond(items, tnext, fnext, x=200, y=0):
    return {"id": uid(), "type": "condition", "sourceBlockId": None,
            "options": {"conditions": items, "trueNextBlockId": tnext, "falseNextBlockId": fnext},
            "presentation": {"x": x, "y": y}}

def c_has_tag(tag):     return {"name": "lead-has-tag-condition", "group": "lead", "options": {"tagIds": [TAG[tag]]}}
def c_source_eq(val):   return {"name": "field-is-equal-condition", "group": "field", "options": {"equalsTo": val, "parameter": "leadSource"}}
def c_email_exists(v):  return {"name": "lead-with-email-exists-condition", "group": "lead", "options": {"email": v}}

def delay(name, opts, nxt, x=200, y=0):
    return {"id": uid(), "type": "delay", "sourceBlockId": None,
            "options": {"delay": {"name": name, "options": opts}, "nextBlockId": nxt},
            "presentation": {"x": x, "y": y}}

def d_min(n, nxt, **kw): return delay("minutes-delay", {"minutes": n}, nxt, **kw)
def d_hours(n, nxt, **kw): return delay("hours-delay", {"hours": n}, nxt, **kw)
def d_days(n, nxt, **kw): return delay("days-delay", {"days": n}, nxt, **kw)

def note(text, x=-760, y=-260, color="#bae6fd", w=560, h=420):
    return {"id": uid(), "options": {"text": text, "color": color, "width": w, "height": h},
            "presentation": {"x": x, "y": y}}

def build(name, blocks, notes):
    # o primeiro bloco da lista deve ser o trigger
    return {"id": uid(), "createdAt": NOW, "name": name, "version": 1,
            "active": False, "notes": notes, "blocks": blocks, "tenantId": TENANT}

def save(doc, fname):
    p = os.path.join(OUT, fname)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("gerado:", os.path.relpath(p))

# =====================================================================
# AUTOMACAO 1 — Reengajamento 10min
# =====================================================================
def auto1():
    b = {}
    b["fim"] = None  # sentinela
    ch1 = chat_text(
        "Oi {leadFirstName}, tudo bem? 😊 Aqui é a equipe do Dr. Wilton Vargas.\n\n"
        "Você preencheu o formulário da nossa mentoria há pouco e queria garantir que seu lugar não se perca.",
        x=200, y=1750)
    ch2 = chat_text(
        "Tenho uma novidade rápida sobre como o Dr. Wilton pode te ajudar a estruturar seu consultório "
        "para faturar com previsibilidade e sair do operacional.\n\n"
        "O primeiro passo é uma conversa de diagnóstico (rápida, 30 minutos) direto com ele.", x=200, y=2100)
    # ch2 chama a Automacao 2 para conduzir o agendamento (amarrar no painel)
    a_call = action([a_add_tag("REENGAJADO-10MIN"), a_start_auto()], "", x=200, y=2450)
    ch1["options"]["nextBlockId"] = ch2["id"]
    ch2["options"]["nextBlockId"] = a_call["id"]

    c_conv = cond([c_has_tag("CONVERSOU")], "", ch1["id"], x=200, y=1400)  # true->FIM, false->ch1
    d10 = d_min(10, c_conv["id"], x=200, y=1050)
    a_biz = action([a_create_biz("novo"), a_add_tag("FORM-RESPONDIDO")], d10["id"], x=200, y=700)
    c_src = cond([c_source_eq(SOURCE)], a_biz["id"], "", x=200, y=350)     # true->a_biz, false->FIM
    trg = trigger([{"name": "lead-created-trigger", "group": "lead", "options": {}}], c_src["id"])

    n = note("📋 MENTORIA · Reengajamento 10min\n\n"
             "1. Lead criado (form da LP)\n"
             "2. Filtra source = LP-MENTORIA-WILTON\n"
             "3. Cria card em 'Novo Lead' + tag FORM-RESPONDIDO\n"
             "4. Espera 10 min\n"
             "5. Se JÁ conversou (tag CONVERSOU) → encerra\n"
             "6. Senão → abertura fria + chama a Automação 2\n\n"
             "⚠️ AMARRAR: no bloco 'iniciar outra automação', selecionar\n"
             "a automação 'MENTORIA · Chatbot Agendamento'.\n"
             "⚠️ Selecionar a INSTÂNCIA (canal) nos blocos de mensagem.")
    return build("MENTORIA · Reengajamento 10min", [trg, c_src, a_biz, d10, c_conv, ch1, ch2, a_call], [n])

# =====================================================================
# AUTOMACAO 2 — Chatbot Agendamento (nucleo completo)
# =====================================================================
def auto2():
    # --- cadencia de resgate (construida de tras pra frente) ---
    ch_brk = chat_text(
        "{leadFirstName}, vou encerrar seu atendimento por aqui pra liberar o horário para outro dentista na fila. 🙏\n\n"
        "Se mudar de ideia, é só me mandar uma mensagem que eu reservo um novo horário com o Dr. Wilton pra você. Sucesso! 😊",
        x=-800, y=2900)
    a_lose_blk = action([a_move_biz("perdido"), a_add_tag("PERDIDO-BREAKUP"), a_lose()], "", x=-800, y=3250)
    ch_brk["options"]["nextBlockId"] = a_lose_blk["id"]

    ch_r3 = chat_text("{leadFirstName}, passando aqui de novo 👀 Seria uma pena deixar seu diagnóstico com o Dr. Wilton pra trás. Bora marcar?", x=-400, y=2900)
    c_r4 = cond([c_has_tag("REUNIAO-AGENDADA")], "", ch_brk["id"], x=200, y=2900)  # true FIM / false breakup
    d_r4 = d_days(1, c_r4["id"], x=200, y=2550)
    ch_r3["options"]["nextBlockId"] = d_r4["id"]

    ch_r2 = chat_text(
        "Oi {leadFirstName}! Não quero que você perca essa chance de conversar direto com o Dr. Wilton.\n\n"
        "As vagas da mentoria são limitadas e os horários de diagnóstico enchem rápido.\n\n"
        "Segue o link de novo, é bem rapidinho: 👉 " + CALCOM, x=-400, y=2200)
    c_r3 = cond([c_has_tag("REUNIAO-AGENDADA")], "", ch_r3["id"], x=200, y=2200)
    d_r3 = d_days(1, c_r3["id"], x=200, y=1850)
    ch_r2["options"]["nextBlockId"] = d_r3["id"]

    ch_r1 = chat_text("{leadFirstName}, conseguiu escolher um horário? 😊 Se tiver qualquer dificuldade com o link, me fala que eu te ajudo por aqui.", x=-400, y=1500)
    c_r2 = cond([c_has_tag("REUNIAO-AGENDADA")], "", ch_r2["id"], x=200, y=1500)
    d_r2 = d_hours(2, c_r2["id"], x=200, y=1150)  # +2h -> reforco +1d cadeia acima
    ch_r1["options"]["nextBlockId"] = d_r2["id"]

    c_r1 = cond([c_has_tag("REUNIAO-AGENDADA")], "", ch_r1["id"], x=200, y=800)
    d_r1 = d_hours(2, c_r1["id"], x=200, y=450)   # primeira espera 2h apos enviar link

    # --- ramo agendar ---
    ch_link = chat_text(
        "Perfeito, {leadFirstName}! 🙌\n\n"
        "É só escolher o melhor dia e horário neste link — já vai preenchido com seus dados:\n\n"
        "👉 " + CALCOM + "\n\n"
        "Assim que você confirmar, eu te mando a confirmação por aqui. Te espero! 😊",
        nxt=d_r1["id"], x=600, y=100)
    a_ag = action([a_move_biz("qualificado"), a_add_tag("AGUARDANDO-AGENDAMENTO")], ch_link["id"], x=600, y=-250)

    # --- ramo duvida ---
    a_transf = action([a_stop_bot(), a_notify("Lead da mentoria com dúvida — assumir atendimento")], "", x=1000, y=100)
    ch_duv = chat_text("Claro, {leadFirstName}! Me conta rapidinho qual é a sua dúvida que a nossa equipe te ajuda. 😊",
                       nxt=a_transf["id"], x=1000, y=-250)

    # --- topo ---
    ch_cta = chat_text("Quer agendar sua conversa de diagnóstico com o Dr. Wilton? 👇",
                       buttons=[button("Quero agendar", a_ag["id"]), button("Tenho uma dúvida", ch_duv["id"])],
                       x=200, y=100)
    ch_val = chat_text(
        "A mentoria do Dr. Wilton é para dentistas que querem estruturar o consultório para faturar com "
        "previsibilidade e sair do operacional — sem depender de sorte ou trabalhar cada vez mais horas.\n\n"
        "Ele é referência em gestão e crescimento de consultórios odontológicos, e agora abriu um número "
        "limitado de vagas para acompanhar dentistas de perto.\n\n"
        "O primeiro passo é uma conversa de diagnóstico (rápida, 30 minutos) direto com ele, pra entender "
        "seu momento e ver se faz sentido pra você.", nxt=ch_cta["id"], x=200, y=-250)
    ch_ola = chat_text(
        "Oi {leadFirstName}! 👋 Aqui é a equipe do Dr. Wilton Vargas.\n\n"
        "Vi que você preencheu o formulário da Mentoria Dr. Wilton Vargas — que bom te ver por aqui!\n\n"
        "Posso te explicar rapidinho como funciona e já deixar sua conversa com o Dr. Wilton agendada?",
        nxt=ch_val["id"], x=200, y=-600)
    a_start = action([a_add_tag("CONVERSOU")], ch_ola["id"], x=200, y=-950)
    trg = trigger([
        {"name": "message-received-trigger", "group": "messages",
         "options": {"type": "contains", "keywords": [], "instanceId": INSTANCE,
                     "listenGroup": False, "receiveJson": False, "initializeSession": "only-if-finished"}},
        {"name": "initiated-by-another-automation-trigger", "group": "system",
         "options": {"datasourceName": "Api-request-2", "datasourceColor": "#6366f1"}},
    ], a_start["id"], x=200, y=-1300)

    blocks = [trg, a_start, ch_ola, ch_val, ch_cta, a_ag, ch_link, ch_duv, a_transf,
              d_r1, c_r1, ch_r1, d_r2, c_r2, ch_r2, d_r3, c_r3, ch_r3, d_r4, c_r4, ch_brk, a_lose_blk]
    n = note("📋 MENTORIA · Chatbot Agendamento\n\n"
             "Gatilho: mensagem recebida OU iniciado pela Automação 1\n"
             "→ tag CONVERSOU → saudação → valor → CTA (botões)\n"
             "  • Quero agendar → move Qualificado + link Cal.com\n"
             "  • Tenho dúvida → transfere p/ humano\n"
             "Cadência resgate: +2h → +2h → +1d → +1d → breakup\n"
             "(cada etapa checa tag REUNIAO-AGENDADA e para se agendou)\n\n"
             "⚠️ Selecionar a INSTÂNCIA (canal) em cada bloco de mensagem.\n"
             "⚠️ Trocar o link Cal.com pelo real do Dr. Wilton.\n"
             "⚠️ Validar a variável {leadFirstName} no editor (menu de variáveis).",
             w=600, h=480)
    return build("MENTORIA · Chatbot Agendamento", blocks, [n])

# =====================================================================
# AUTOMACAO 3 — Cal.com Booking Confirmado (webhook) [ESQUELETO]
# =====================================================================
def auto3():
    ch_ok = chat_text(
        "Prontinho, {leadFirstName}! ✅ Sua conversa de diagnóstico com o Dr. Wilton está confirmada.\n\n"
        "Vou te enviar um lembrete no dia. Qualquer imprevisto, é só me avisar por aqui. Até lá! 😊",
        x=200, y=700)
    a_ok = action([a_move_biz("agendada"), a_add_tag("REUNIAO-AGENDADA"), a_rm_tag("AGUARDANDO-AGENDAMENTO")],
                  ch_ok["id"], x=200, y=350)
    a_orf = action([a_notify("Booking Cal.com sem lead correspondente — verificar manualmente")], "", x=-400, y=350)
    c_lead = cond([c_email_exists("{email|[calcom]payload.attendees[0].email}")], a_ok["id"], a_orf["id"], x=200, y=0)
    trg = trigger([{"name": "json-http-request-trigger", "group": "http",
                    "options": {"datasourceName": "calcom", "datasourceColor": "#3b82f6"}}], c_lead["id"])
    n = note("📋 MENTORIA · Cal.com Booking Confirmado  [ESQUELETO]\n\n"
             "Webhook Cal.com BOOKING_CREATED → confirma agendamento.\n\n"
             "⚠️ VALIDAR com um teste real (webhook.site):\n"
             "  • path do e-mail: payload.attendees[0].email\n"
             "  • mecanismo de associação lead↔webhook no DataCrazy\n"
             "Configurar no Cal.com o webhook apontando p/ a rota HTTP\n"
             "desta automação (copiar a URL gerada no gatilho).",
             color="#fde68a", w=560, h=360)
    return build("MENTORIA · Cal.com Booking Confirmado", [trg, c_lead, a_ok, ch_ok, a_orf], [n])

# =====================================================================
# AUTOMACAO 4 — Lembrete + No-show [ESQUELETO]
# =====================================================================
def auto4():
    ch_rem = chat_text(
        "Bom dia, {leadFirstName}! ☀️ Hoje é o dia da sua conversa com o Dr. Wilton.\n\n"
        "Separa uns minutinhos num lugar tranquilo — vai ser muito produtivo. Te espero! 🙌",
        x=200, y=350)
    a_rem = action([a_add_tag("LEMBRETE-ENVIADO")], "", x=200, y=700)
    ch_rem["options"]["nextBlockId"] = a_rem["id"]
    trg = trigger([{"name": "lead-tag-added-trigger", "group": "lead",
                    "options": {"tagIds": [TAG["REUNIAO-AGENDADA"]]}}], ch_rem["id"])
    n = note("📋 MENTORIA · Lembrete + No-show  [ESQUELETO]\n\n"
             "Dispara ao ganhar a tag REUNIAO-AGENDADA (versão simples:\n"
             "manda o lembrete). \n\n"
             "⚠️ EVOLUIR: usar delay 'até a data' (until-date-delay) com a\n"
             "data do booking vinda do Cal.com para lembrar NO DIA/hora certa,\n"
             "e um ramo de NO-SHOW (webhook cancel/no-show → tag NO-SHOW +\n"
             "trilha de recuperação com novo link Cal.com).",
             color="#fde68a", w=560, h=340)
    return build("MENTORIA · Lembrete + No-show", [trg, ch_rem, a_rem], [n])

save(auto1(), "1-reengajamento-10min.dc")
save(auto2(), "2-chatbot-agendamento.dc")
save(auto3(), "3-calcom-booking-confirmado.dc")
save(auto4(), "4-lembrete-no-show.dc")
print("OK — 4 arquivos .dc gerados em", OUT)

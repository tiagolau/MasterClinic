#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera os .dc do chatbot de tráfego da Master Clinic — um fluxo por unidade.

Cada unidade produz DOIS arquivos, que juntos formam o fluxo:
    <n>-<unidade>-chatbot.dc   trilho de botões até o handoff humano
    <n>-<unidade>-resgate.dc   cadência de reengajamento (roda em paralelo)

Por que dois: um bloco `chat` com botões PAUSA a automação até o clique. Se a
cadência de resgate ficasse em série, nunca dispararia. Ela roda como automação
própria, disparada pela tag CONVERSOU e checando AGUARDANDO-AGENDAMENTO a cada etapa.

Desenho em docs/fluxo-chatbot-trafego-agendamento.md, a partir da análise de
1.687 conversas reais (docs/analise-conversas-trafego.md).

Regras aplicadas:
  - o bot NÃO usa nome próprio — só "assistente da Master Clinic"
  - todo avanço é por botão; o fluxo não anda sem clique (max 3 botões/mensagem)
  - o bot nunca fala valor, nunca manda áudio, nunca agenda — quem agenda é humano
"""
import json
import os
import uuid

TENANT = "69937b06-43cd-40d2-bd39-d3d3c9223283"
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dc-trafego"
)
os.makedirs(OUT, exist_ok=True)
NOW = "2026-07-29T12:00:00.000Z"

STAGE = {
    # pipeline Funil Principal - Ipatinga (ex-Vendas - Ipatinga) — 10cd55a8-b076-4119-b3bc-333b295f5a42
    # ADR 006: etapas antigas (Lead/Consulta) foram substituídas pelas 5 etapas da
    # especificação de CRM. Não existe mais uma etapa "Consulta" distinta — o handoff
    # do bot permanece na própria etapa de entrada.
    "vi_lead": "fa389511-0857-43ca-88cf-58bf2f2c83fa",  # Agendamento (Entrada)
    "vi_consulta": "fa389511-0857-43ca-88cf-58bf2f2c83fa",  # Agendamento (Entrada) — handoff
    # pipeline Funil Principal - Mesquita (ex-Vendas - Mesquita) — 7c922803-5c98-4733-9f72-55189ac97916
    "vm_lead": "ab4a1b39-acfc-4b0e-b2e4-ea9d27379b4f",  # Agendamento (Entrada)
    "vm_consulta": "ab4a1b39-acfc-4b0e-b2e4-ea9d27379b4f",  # Agendamento (Entrada) — handoff
}
TAG = {
    "TRAFEGO": "be3b6d3a-a4dc-43a7-8794-49d81befa3ae",  # Tráfego Pago
    "LEAD": "559cd268-acc4-496c-9b35-dfc0ebd7e6cb",
    "CONVERSOU": "09e51ab5-96ab-4955-bf61-cf13120bd880",
    "AGUARDANDO-AGENDAMENTO": "7309d983-fefa-4b83-93be-fe1d7b2131c0",
    "REQUER-RETORNO": "cc8ae801-9bd3-413a-b0d6-ff47cb990f84",
    "CONVENIO-PENDENTE": "75740cd4-34c7-444a-9679-fa77f0a6bbc0",
    "PERDIDO-BREAKUP": "81db8417-cae7-4291-8098-3c44cb272db8",
    "NOVO-PACIENTE": "e424604f-2966-4722-9339-c8b35d887a7f",
}

HORARIO = "Segunda a sexta, de 08:00 às 12:30 e 13:30 às 18:30"
INSTAGRAM = "@masterclinicipatinga\n@dradaniellecarvalho\n@drwiltonvargas.dentista"
TOQUE = "\n\n👇 *Toque em uma das opções abaixo*"


def uid():
    return str(uuid.uuid4())


# ------------------------------------------------------------------ blocos
def trigger(triggers, nxt, x=200, y=0):
    return {
        "id": uid(),
        "type": "trigger",
        "sourceBlockId": None,
        "options": {"triggers": triggers, "nextBlockId": nxt},
        "presentation": {"x": x, "y": y},
    }


def chat(text, U, nxt="", buttons=None, x=200, y=0):
    msg = {
        "name": "send-text-message",
        "group": "messages",
        "stepId": uid(),
        "options": {
            "text": text,
            "buttons": buttons or [],
            "breakMessages": True,
            "breakMessagesIntervalInSeconds": 2,
        },
    }
    return {
        "id": uid(),
        "type": "chat",
        "sourceBlockId": None,
        "options": {
            "messages": [msg],
            "platform": U["platform"],
            "provider": U["provider"],
            "timezone": "",
            "contactId": "",
            "instanceId": "",  # selecionar o canal no painel ao importar
            # com botões o fluxo pausa até o clique — nextBlockId precisa ficar ""
            "nextBlockId": "" if buttons else nxt,
            "isAnnotation": False,
            "scheduledDate": "",
            "errorNextBlockId": "",
        },
        "presentation": {"x": x, "y": y},
    }


def button(text, nxt):
    return {"id": uid(), "text": text, "type": "button", "nextBlockId": nxt}


def action(items, nxt, x=200, y=0):
    return {
        "id": uid(),
        "type": "action",
        "sourceBlockId": None,
        "options": {"actions": items, "nextBlockId": nxt},
        "presentation": {"x": x, "y": y},
    }


def cond(items, tnext, fnext, x=200, y=0):
    return {
        "id": uid(),
        "type": "condition",
        "sourceBlockId": None,
        "options": {
            "conditions": items,
            "trueNextBlockId": tnext,
            "falseNextBlockId": fnext,
        },
        "presentation": {"x": x, "y": y},
    }


def delay(name, opts, nxt, x=200, y=0):
    return {
        "id": uid(),
        "type": "delay",
        "sourceBlockId": None,
        "options": {"delay": {"name": name, "options": opts}, "nextBlockId": nxt},
        "presentation": {"x": x, "y": y},
    }


def a_add(*tags):
    return {
        "name": "add-tag-action",
        "group": "lead",
        "options": {"tagIds": [TAG[t] for t in tags], "tagName": ""},
    }


def a_move_biz(st):
    return {
        "name": "move-business-action",
        "group": "business",
        "options": {"stageId": STAGE[st]},
    }


def a_lose(motivo):
    return {
        "name": "lose-business-action",
        "group": "business",
        "options": {"lossReasonId": "", "justification": motivo},
    }


def a_stop():
    return {
        "name": "stop-chat-automations-action",
        "group": "messages",
        "options": {"type": "current-conversation", "instanceId": ""},
    }


def a_notify(msg):
    return {
        "name": "send-notification-action",
        "group": "system",
        "options": {"notification": msg, "url": "", "attendantsIds": []},
    }


def c_tag(t):
    return {
        "name": "lead-has-tag-condition",
        "group": "lead",
        "options": {"tagIds": [TAG[t]]},
    }


def note(text, x=-700, y=-200, color="#bae6fd", w=560, h=700):
    return {
        "id": uid(),
        "options": {"text": text, "color": color, "width": w, "height": h},
        "presentation": {"x": x, "y": y},
    }


def build(nome, blocks, notes):
    return {
        "id": uid(),
        "createdAt": NOW,
        "name": nome,
        "version": 1,
        "active": False,
        "notes": notes,
        "blocks": blocks,
        "tenantId": TENANT,
    }


# ------------------------------------------------------------------ chatbot
def montar_chatbot(U):
    """Sequência de CRC: acolher → investigar → dar valor à avaliação → fechar por
    alternativa → confirmar viabilidade → entregar ao humano.

    O que o bot NÃO faz, de propósito:
      - não abre com objeção (convênio/preço). Objeção se trata quando aparece, e quem
        trata é o humano. Antecipar "não atendemos convênio" derruba o lead antes de
        existir qualquer valor na conversa.
      - não vende tratamento nem fala preço. Vende a AVALIAÇÃO — o único objetivo do
        primeiro contato é ocupar uma cadeira na agenda.
      - não pergunta cidade de cara. O filtro geográfico entra junto do agendamento,
        quando o lead já está comprometido com o horário.
    """
    B = []

    def add(b):
        B.append(b)
        return b

    # ---- HANDOFF (destino de todos os caminhos felizes) ----
    ch_insta = add(
        chat(
            "Enquanto isso, já nos segue no Instagram? 😁\n\n" + INSTAGRAM,
            U,
            x=200,
            y=3500,
        )
    )
    ch_fim = add(
        chat(
            "Prontinho! ✨\n\n"
            "Já passei tudo para a nossa recepção — ela vai confirmar o melhor horário "
            "com você aqui mesmo, em instantes.\n\n"
            f"📍 {U['endereco']}\n"
            f"🗓️ {HORARIO}",
            U,
            nxt=ch_insta["id"],
            x=200,
            y=3150,
        )
    )
    a_handoff = add(
        action(
            [
                a_add("AGUARDANDO-AGENDAMENTO", "CONVERSOU", "NOVO-PACIENTE"),
                a_move_biz(U["stage_handoff"]),
                a_notify(
                    f"🟢 LEAD QUALIFICADO — unidade {U['nome']}. "
                    "Quer avaliação, já escolheu turno e confirmou que consegue vir. "
                    "Fechar o horário."
                ),
                a_stop(),
            ],
            ch_fim["id"],
            x=200,
            y=2800,
        )
    )

    # ---- URGÊNCIA: dor não passa por funil, vai direto ----
    ch_urgencia = add(
        chat(
            "Poxa, dor de dente não dá sossego mesmo 🛑\n\n"
            "Já estou avisando a recepção pra te encaixar o quanto antes. "
            "Fica aqui comigo que já te respondem!",
            U,
            x=1100,
            y=1400,
        )
    )
    a_urgencia = add(
        action(
            [
                a_add("REQUER-RETORNO", "CONVERSOU", "AGUARDANDO-AGENDAMENTO"),
                a_move_biz(U["stage_handoff"]),
                a_notify(
                    f"🔴 URGÊNCIA / DOR — unidade {U['nome']}. Encaixar o quanto antes."
                ),
                a_stop(),
            ],
            ch_urgencia["id"],
            x=1100,
            y=1050,
        )
    )

    # ---- 5. VIABILIDADE (filtro geográfico, já com o lead comprometido) ----
    a_perdido_dist = add(
        action(
            [
                a_add("PERDIDO-BREAKUP"),
                a_lose("Fora da região — não consegue se deslocar até a unidade"),
                a_stop(),
            ],
            "",
            x=1500,
            y=2800,
        )
    )
    ch_dist_nao = add(
        chat(
            "Imagino, sem problema! 💚 Agradeço demais o seu contato.\n\n"
            "Se um dia estiver aqui pela região, vai ser um prazer te atender. "
            "Fica com Deus! 🙏🏼",
            U,
            nxt=a_perdido_dist["id"],
            x=1500,
            y=2450,
        )
    )
    a_dist_sim = add(
        action([a_add("REQUER-RETORNO")], a_handoff["id"], x=1100, y=2800)
    )
    ch_dist = add(
        chat(
            "Entendi! Temos pacientes que vêm de outras cidades, principalmente para "
            "implante e prótese — nesses casos a gente organiza o tratamento em menos "
            "visitas, pra compensar a viagem.\n\n"
            f"Você conseguiria vir até {U['cidade']}?" + TOQUE,
            U,
            buttons=[],
            x=1100,
            y=2450,
        )
    )
    ch_dist["options"]["messages"][0]["options"]["buttons"] = [
        button("Sim, consigo ir", a_dist_sim["id"]),
        button("Não, é longe demais", ch_dist_nao["id"]),
    ]

    ch_local = add(
        chat(
            f"Perfeito! Nossa unidade fica em *{U['endereco']}* 📍\n\n"
            "Fica tranquilo pra você chegar até aqui?" + TOQUE,
            U,
            buttons=[],
            x=200,
            y=2450,
        )
    )
    ch_local["options"]["messages"][0]["options"]["buttons"] = [
        button("Sim, tranquilo", a_handoff["id"]),
        button("Sou de outra cidade", ch_dist["id"]),
    ]

    # ---- 4. FECHAMENTO POR ALTERNATIVA ----
    # nunca "quando você quer vir?" — sempre duas opções concretas
    ch_turno = add(
        chat(
            "Você prefere vir de manhã ou à tarde? 🗓️" + TOQUE,
            U,
            buttons=[],
            x=200,
            y=2100,
        )
    )
    ch_turno["options"]["messages"][0]["options"]["buttons"] = [
        button("De manhã", ch_local["id"]),
        button("À tarde", ch_local["id"]),
        button("Tanto faz", ch_local["id"]),
    ]

    # ---- 3. VALOR DA AVALIAÇÃO — o que o bot realmente "vende" ----
    ch_oferta = add(
        chat(
            "O primeiro passo aqui é uma *avaliação* com o nosso especialista 🦷\n\n"
            "Ele examina o seu caso com calma, tira todas as suas dúvidas e monta o "
            "plano ideal pra você — assim você já sai daqui sabendo exatamente o que "
            "precisa ser feito, sem surpresa.\n\n"
            "Vou reservar um horário pra você, tá bom?",
            U,
            nxt=ch_turno["id"],
            x=200,
            y=1750,
        )
    )

    # ---- 2b. INVESTIGAÇÃO: o que quer resolver ----
    ch_trat = add(
        chat(
            "Que bom que você decidiu cuidar disso! 💚\n\n"
            "E o que você gostaria de resolver?" + TOQUE,
            U,
            buttons=[],
            x=600,
            y=1400,
        )
    )
    ch_trat["options"]["messages"][0]["options"]["buttons"] = [
        button("Implante ou prótese", ch_oferta["id"]),
        button("Aparelho / ortodontia", ch_oferta["id"]),
        button("Limpeza e avaliação", ch_oferta["id"]),
    ]

    # ---- 2c. ODONTOPEDIATRIA ----
    ch_filho = add(
        chat(
            "Que bom! Cuidar desde cedo faz toda a diferença no sorriso dele 🧒✨",
            U,
            nxt=ch_oferta["id"],
            x=-300,
            y=1400,
        )
    )

    # ---- 1. ACOLHIDA + PERGUNTA DE NECESSIDADE ----
    ch_ola = add(
        chat(
            "Olá! Tudo bem? 😊\n\n"
            "Aqui é a assistente da *Master Clinic Odontologia Especializada* — "
            f"unidade {U['nome']} ✨\n\n"
            "Que bom ter você por aqui! Me conta como podemos cuidar do seu sorriso 💚"
            + TOQUE,
            U,
            buttons=[],
            x=200,
            y=1050,
        )
    )
    ch_ola["options"]["messages"][0]["options"]["buttons"] = [
        button("Estou com dor", a_urgencia["id"]),
        button("Quero fazer um tratamento", ch_trat["id"]),
        button("Levar meu filho", ch_filho["id"]),
    ]

    # ---- ENTRADA: só a tag de controle. O card já existe — foi ele que disparou
    # este fluxo — e o fluxo anterior já marcou a origem de tráfego. ----
    a_entrada = add(action([a_add("CONVERSOU")], ch_ola["id"], x=200, y=700))

    # ---- não reabordar quem já foi entregue ao humano ----
    c_ja = add(
        cond([c_tag("AGUARDANDO-AGENDAMENTO")], "", a_entrada["id"], x=200, y=350)
    )

    # Gatilho: negócio criado na etapa Lead do funil da unidade. O fluxo que roda antes
    # já identifica a origem, cria o lead e abre o card — se o card nasceu, o lead mandou
    # mensagem. Isso dispensa casar as aberturas do CTWA por palavra-chave.
    trg = trigger(
        [
            {
                "name": "business-created-trigger",
                "group": "business",
                "options": {"stageId": STAGE[U["stage_entrada"]]},
            }
        ],
        c_ja["id"],
        x=200,
        y=0,
    )
    B.insert(0, trg)

    n = note(
        f"🦷 {U['nome'].upper()} · LEAD → AVALIAÇÃO AGENDADA\n\n"
        f"Canal: {U['canal']}\n"
        f"Gatilho: NEGÓCIO CRIADO na etapa Agendamento (Entrada) de '{U['pipeline']}'\n"
        "  (o fluxo anterior já identifica a origem, cria o lead e abre o\n"
        "   card — se o card nasceu, o lead mandou mensagem)\n\n"
        "ESTRATÉGIA: vender a AVALIAÇÃO, não o tratamento.\n"
        "O único objetivo é ocupar uma cadeira na agenda.\n\n"
        "TRILHO — só avança por BOTÃO:\n"
        "  1. Acolhida + 'como podemos cuidar do seu sorriso?'\n"
        "       Dor → handoff imediato 🔴\n"
        "       Tratamento → o que quer resolver\n"
        "       Filho → acolhimento\n"
        "  2. VALOR da avaliação (examina, tira dúvidas, monta o plano)\n"
        "  3. Fechamento por alternativa: manhã / tarde / tanto faz\n"
        "  4. Viabilidade: 'fica tranquilo chegar aqui?'\n"
        "       Outra cidade → 'consegue vir?' → Não = PERDIDO\n"
        "  5. HANDOFF: permanece em Agendamento (Entrada) + notifica + PARA o bot\n\n"
        "⚠️ O BOT NÃO FALA:\n"
        "  • convênio / Brasil Sorridente — é OBJEÇÃO, trata só se o\n"
        "    lead levantar, e quem trata é o humano\n"
        "  • preço, parcelamento — só o doutor, na consulta\n"
        "  • nunca manda áudio, nunca agenda sozinho\n\n"
        "⚠️ AO IMPORTAR:\n"
        f"  • selecionar o canal '{U['canal']}' em TODOS os blocos de mensagem\n"
        f"  • conferir se o gatilho aponta para a etapa Agendamento (Entrada) de '{U['pipeline']}'\n"
        "  • importar também o .dc de RESGATE desta unidade\n"
        "  • ativar só após testar com o próprio número",
    )
    return build(f"{U['nome']} · Lead → Avaliação Agendada", B, [n])


# ------------------------------------------------------------------ resgate
def montar_resgate(U):
    """Cadência paralela: o chatbot pausa no botão, então o resgate é automação própria.

    Dispara quando a tag CONVERSOU é adicionada (entrada no chatbot) e para assim que
    o lead ganha AGUARDANDO-AGENDAMENTO (já entregue ao humano).
    """
    B = []

    def add(b):
        B.append(b)
        return b

    a_breakup = add(
        action(
            [
                a_add("PERDIDO-BREAKUP"),
                a_lose("Breakup automático — lead de tráfego não respondeu"),
                a_stop(),
            ],
            "",
            x=-400,
            y=2800,
        )
    )
    ch_breakup = add(
        chat(
            "Vou encerrar seu atendimento por aqui pra não te incomodar, tá bom? 💚\n\n"
            "Quando precisar, é só me mandar uma mensagem que a gente te atende na hora. "
            "Fica com Deus! 🙏🏼",
            U,
            nxt=a_breakup["id"],
            x=-400,
            y=2450,
        )
    )
    c4 = add(
        cond([c_tag("AGUARDANDO-AGENDAMENTO")], "", ch_breakup["id"], x=200, y=2450)
    )
    d4 = add(delay("days-delay", {"days": 3}, c4["id"], x=200, y=2100))

    ch_r3 = add(
        chat(
            "Oi! A agenda costuma fechar rápido 🗓️\n\n"
            "Quer que eu reserve um horário no seu nome? É só tocar no botão que "
            "eu já organizo tudo com a recepção.",
            U,
            nxt=d4["id"],
            x=-400,
            y=1750,
        )
    )
    c3 = add(cond([c_tag("AGUARDANDO-AGENDAMENTO")], "", ch_r3["id"], x=200, y=1750))
    d3 = add(delay("days-delay", {"days": 1}, c3["id"], x=200, y=1400))

    ch_r2 = add(
        chat(
            "Passando aqui de novo pra não te deixar sem resposta 🙏🏼\n\n"
            "Ainda quer que eu veja um horário pra você?",
            U,
            nxt=d3["id"],
            x=-400,
            y=1050,
        )
    )
    c2 = add(cond([c_tag("AGUARDANDO-AGENDAMENTO")], "", ch_r2["id"], x=200, y=1050))
    d2 = add(delay("hours-delay", {"hours": 4}, c2["id"], x=200, y=700))

    ch_r1 = add(
        chat(
            "Oi! Conseguiu ver minha mensagem? 😊\n\n"
            "É rapidinho — só pra eu organizar seu atendimento com a nossa recepção.",
            U,
            nxt=d2["id"],
            x=-400,
            y=350,
        )
    )
    c1 = add(cond([c_tag("AGUARDANDO-AGENDAMENTO")], "", ch_r1["id"], x=200, y=350))
    d1 = add(delay("minutes-delay", {"minutes": 30}, c1["id"], x=200, y=0))

    trg = trigger(
        [
            {
                "name": "lead-tag-added-trigger",
                "group": "lead",
                "options": {"tagIds": [TAG["CONVERSOU"]]},
            }
        ],
        d1["id"],
        x=200,
        y=-350,
    )
    B.insert(0, trg)

    n = note(
        f"⏱️ TRÁFEGO · {U['nome'].upper()} · RESGATE\n\n"
        "Gatilho: tag CONVERSOU adicionada (lead entrou no chatbot)\n\n"
        "Cadência: +30min → +4h → +1d → +3d breakup\n"
        "Cada etapa checa AGUARDANDO-AGENDAMENTO:\n"
        "  • tem a tag  → já foi entregue ao humano → PARA\n"
        "  • não tem    → manda o próximo cutucão\n\n"
        "Por que é uma automação separada:\n"
        "um bloco de mensagem com BOTÕES pausa o fluxo até o clique.\n"
        "Se a cadência estivesse em série com o chatbot, nunca rodaria.\n\n"
        f"⚠️ selecionar o canal '{U['canal']}' em todos os blocos de mensagem.",
        h=560,
    )
    return build(f"TRÁFEGO · {U['nome']} · Resgate", B, [n])


UNIDADES = [
    {
        "nome": "Ipatinga",
        "prefixo": "1-ipatinga",
        "canal": "Oficial Master Clinic",
        "platform": "WHATSAPP",
        "provider": "WHATSAPP_CLOUD_API",
        "cidade": "Ipatinga (MG)",
        "endereco": "Av. Brasil, nº 685 — Iguaçu, Ipatinga",
        "botao_cidade_1": "Ipatinga",
        "botao_cidade_2": "Região do Vale do Aço",
        "pipeline": "Funil Principal - Ipatinga",
        "stage_entrada": "vi_lead",
        "stage_handoff": "vi_consulta",
    },
    {
        "nome": "Mesquita",
        "prefixo": "2-mesquita",
        "canal": "Mesquita Uazapi",
        "platform": "WHATSAPP",
        "provider": "UAZAPI",
        "cidade": "Mesquita (MG)",
        "endereco": "unidade Mesquita — confirmar endereço com a recepção",
        "botao_cidade_1": "Mesquita",
        "botao_cidade_2": "Ipatinga e região",
        "pipeline": "Funil Principal - Mesquita",
        "stage_entrada": "vm_lead",
        "stage_handoff": "vm_consulta",
    },
]


SPEC = os.path.expanduser(
    "~/.claude/skills/datacrazy-automacoes/references/formato-dc-completo.md"
)


def nomes_validos():
    """Nomes de trigger/action/condition/delay declarados na spec do formato .dc.

    A spec lista cada componente como `nome` em tabela markdown. Comparar contra ela
    evita o erro clássico de acertar por substring (ex.: `tag-added-trigger` "existe"
    dentro de `lead-tag-added-trigger`, mas não é um nome válido).
    """
    import re

    if not os.path.exists(SPEC):
        return None
    return set(re.findall(r"`([a-z0-9-]+(?:-trigger|-action|-condition|-delay|-operation|-ai|-message))`", open(SPEC).read()))


# Assuntos que o bot não toca: são objeções, e objeção se trata quando aparece — pelo
# humano. Antecipar qualquer um destes derruba o lead antes de existir valor na conversa.
PROIBIDOS = [
    "convenio",
    "brasil sorridente",
    "particular",
    "preco",
    "valor",
    "quanto custa",
    "parcel",
    "1 kg",
    "alimento",
    "social",
]


def _sem_acento(t):
    import unicodedata

    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def validar(doc):
    """Confere conexões órfãs, limites do WhatsApp, nomes de componente e o veto de
    assuntos que o bot não pode levantar."""
    ids = {b["id"] for b in doc["blocks"]}
    erros = []

    for b in doc["blocks"]:
        for m in b["options"].get("messages", []):
            texto = _sem_acento(m["options"]["text"])
            for p in PROIBIDOS:
                if p in texto:
                    erros.append(f"mensagem cita assunto vetado: '{p}'")
    validos = nomes_validos()
    if validos:
        for b in doc["blocks"]:
            o = b["options"]
            usados = (
                [t["name"] for t in o.get("triggers", [])]
                + [a["name"] for a in o.get("actions", [])]
                + [c["name"] for c in o.get("conditions", [])]
                + [m["name"] for m in o.get("messages", [])]
            )
            if o.get("delay"):
                usados.append(o["delay"]["name"])
            for nome in usados:
                if nome not in validos:
                    erros.append(f"componente inexistente na spec: {nome}")
    for b in doc["blocks"]:
        o = b["options"]
        alvos = [
            o.get("nextBlockId"),
            o.get("trueNextBlockId"),
            o.get("falseNextBlockId"),
        ]
        for m in o.get("messages", []):
            bts = m["options"].get("buttons", [])
            if len(bts) > 3:
                erros.append(f"{len(bts)} botões (máx 3)")
            if bts and o.get("nextBlockId"):
                erros.append("chat com botões precisa de nextBlockId vazio")
            alvos += [bt.get("nextBlockId") for bt in bts]
        for a in alvos:
            if a and a not in ids:
                erros.append(f"{b['type']} → destino inexistente {a[:8]}")

    # todo bloco precisa ser alcançável a partir do trigger
    idx = {b["id"]: b for b in doc["blocks"]}
    vistos = set()

    def andar(bid):
        if not bid or bid in vistos or bid not in idx:
            return
        vistos.add(bid)
        o = idx[bid]["options"]
        for m in o.get("messages", []):
            for bt in m["options"].get("buttons", []):
                andar(bt["nextBlockId"])
        for k in ("nextBlockId", "trueNextBlockId", "falseNextBlockId"):
            andar(o.get(k))

    andar(doc["blocks"][0]["id"])
    if len(vistos) != len(doc["blocks"]):
        erros.append(f"{len(doc['blocks']) - len(vistos)} bloco(s) órfão(s)")
    return erros


if __name__ == "__main__":
    for u in UNIDADES:
        for sufixo, doc in (
            ("chatbot", montar_chatbot(u)),
            ("resgate", montar_resgate(u)),
        ):
            erros = validar(doc)
            nome = f"{u['prefixo']}-{sufixo}.dc"
            with open(os.path.join(OUT, nome), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            status = "✓ válido" if not erros else f"⚠️ {erros}"
            print(f"{nome:28} {len(doc['blocks']):2} blocos  {status}")

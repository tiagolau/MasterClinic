#!/usr/bin/env python3
"""Gera a automacao DataCrazy que alerta quando uma instancia uazapi desconecta.

Entrada: webhook `connection` da uazapi (adicionado via POST /webhook com action=add,
sem tocar no webhook que ja alimenta o canal do DataCrazy).

Fluxo:
  trigger webhook -> JS (identifica instancia) -> condicao (nao esta conectada?)
  -> espera 3 min -> GET /instance/status (a verdade) -> ainda fora?
  -> materializa o lead do responsavel -> JS (dedup 30 min + monta texto)
  -> envia WhatsApp por uma instancia DIFERENTE da que caiu

Uso:
    set -a; source ~/.claude/.env; set +a
    python3 scripts/gerar_dc_monitor_instancias.py
Saida:
    dc-monitor/monitor-instancias-uazapi.dc
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dc-monitor" / "monitor-instancias-uazapi.dc"

TENANT_ID = "69937b06-43cd-40d2-bd39-d3d3c9223283"
UAZAPI_HOST = "https://masterclinic.uazapi.com"

# ⚠️ TROCAR pelo numero que recebe o alerta (E.164, so digitos).
TELEFONE_ALERTA = "5531000000000"

# Campo adicional (entity lead) usado como memoria do anti-flood.
CAMPO_DEDUP = "uaz_alertas"
JANELA_DEDUP_MIN = 30
DEBOUNCE_MIN = 3



def _token(unidade: str) -> str:
    # Tokens das instancias uazapi ficam fora do git (~/.claude/.env).
    # Tambem aparecem em config.token do instance_list no MCP do DataCrazy.
    nome = f"UAZAPI_TOKEN_MASTERCLINIC_{unidade}"
    valor = os.environ.get(nome)
    if not valor:
        sys.exit(f"ERRO: defina {nome} (set -a; source ~/.claude/.env; set +a)")
    return valor


# token uazapi -> metadados da instancia (levantado via GET /instance/status)
INSTANCIAS = {
    _token("MESQUITA"): {
        "key": "mesquita",
        "nome": "Mesquita Uazapi",
        "numero": "55 33 9136-0115",
        "owner": "553391360115",
        "uaz": "re138e0949006fa",
        "dc": "6a60fb2d9afe657f0c991354",
    },
    _token("GERENCIA"): {
        "key": "gerencia",
        "nome": "Gerência Uazapi",
        "numero": "55 31 8489-1752",
        "owner": "553184891752",
        "uaz": "rf0e4ed5bd204cc",
        "dc": "6a60fa47daf8b7fddb04ee7f",
    },
    _token("FINANCEIRO"): {
        "key": "financeiro",
        "nome": "Financeiro Uazapi",
        "numero": "55 31 9076-1166",
        "owner": "553190761166",
        "uaz": "r5817ab722f438f",
        "dc": "6a60fb7a9afe657f0c999799",
    },
}

INST_DC_MESQUITA = "6a60fb2d9afe657f0c991354"
INST_DC_GERENCIA = "6a60fa47daf8b7fddb04ee7f"

NS = uuid.UUID("2b6a1f4e-9c3d-4c2a-8f11-7d5e6a0b9c44")


def uid(nome: str) -> str:
    """UUID deterministico — regerar o arquivo nao embaralha os ids."""
    return str(uuid.uuid5(NS, nome))


# ---------------------------------------------------------------- JS 1
JS_IDENTIFICA = f"""// Identifica qual instancia uazapi disparou o evento `connection`.
// O payload do webhook varia de formato, entao a leitura e defensiva:
// na duvida seguimos o fluxo e deixamos o GET /instance/status decidir.
const MAP = {json.dumps(INSTANCIAS, ensure_ascii=False, indent=2)};

const ds = session.datasources["uaz-connection"] || {{}};
const d = ds.data || {{}};
const inst = ds.instance || d.instance || {{}};
const ev = ds.event || {{}};

const bruto = [
  ds.token, ds.instance, ds.instanceId, ds.owner, ds.id,
  inst.token, inst.id, inst.owner, inst.name,
  d.token, d.id, d.owner, ev.token
];
const cand = [];
for (let i = 0; i < bruto.length; i++) {{
  const v = bruto[i];
  if (v && typeof v !== "object") cand.push(String(v));
}}

let achado = null;
let tokenUaz = "";
for (const tk in MAP) {{
  const m = MAP[tk];
  const alvos = [tk, m.uaz, m.dc, m.owner, m.key];
  for (let i = 0; i < cand.length; i++) {{
    if (alvos.indexOf(cand[i]) >= 0) {{ achado = m; tokenUaz = tk; break; }}
  }}
  if (achado) break;
}}

// nao reconheceu: se veio algo com cara de token, tenta assim mesmo
if (!tokenUaz) {{
  for (let i = 0; i < cand.length; i++) {{
    if (/^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$/i.test(cand[i])) {{
      tokenUaz = cand[i];
      break;
    }}
  }}
}}

const statusBruto = [
  ds.status, ds.state, ds.connection,
  inst.status, d.status, d.state, ev.state
];
let conectado = false;
let statusTexto = "";
for (let i = 0; i < statusBruto.length; i++) {{
  const v = statusBruto[i];
  if (!v || typeof v === "object") continue;
  const s = String(v).toLowerCase();
  if (!statusTexto) statusTexto = s;
  if (s === "connected" || s === "open" || s === "online") conectado = true;
}}

return {{
  // vazio = o payload afirmou que esta conectada -> nao segue
  eh_desconexao: conectado ? "" : "sim",
  instancia_key: achado ? achado.key : "nao-mapeada",
  instancia_nome: achado ? achado.nome : "Instância não mapeada",
  instancia_numero: achado ? achado.numero : "-",
  instancia_dc: achado ? achado.dc : "",
  token_uaz: tokenUaz,
  status_bruto: statusTexto || "desconhecido",
  telefone_alerta: "{TELEFONE_ALERTA}"
}};
"""

# ---------------------------------------------------------------- JS 2
JS_DEDUP = f"""// Anti-flood + texto do alerta. Roda depois do GET /instance/status.
const ds1 = session.datasources["Javascript-1"] || {{}};
const st = session.datasources["status-uaz"] || {{}};
const inst = st.instance || {{}};

const chave = ds1.instancia_key || "desconhecida";
const JANELA_MS = {JANELA_DEDUP_MIN} * 60 * 1000;
const agora = Date.now();

// memoria do ultimo alerta por instancia, num unico campo adicional (JSON)
let raw = "";
try {{ raw = await session.getAdditionalValue("{CAMPO_DEDUP}"); }} catch (e) {{ raw = ""; }}
let mapa = {{}};
try {{ mapa = JSON.parse(raw || "{{}}"); }} catch (e) {{ mapa = {{}}; }}

const ultimo = Number(mapa[chave] || 0);
const pode = !ultimo || (agora - ultimo) > JANELA_MS;
if (pode) {{
  mapa[chave] = agora;
  try {{ await session.setAdditionalValue("{CAMPO_DEDUP}", JSON.stringify(mapa)); }} catch (e) {{}}
}}

// -03:00 na mao: toLocaleString com timeZone nem sempre existe no runtime
const dt = new Date(agora - 3 * 3600 * 1000);
const p = function (n) {{ return String(n).padStart(2, "0"); }};
const quando = p(dt.getUTCDate()) + "/" + p(dt.getUTCMonth() + 1) + "/" + dt.getUTCFullYear() +
  " às " + p(dt.getUTCHours()) + ":" + p(dt.getUTCMinutes());

const statusAtual = String(inst.status || ds1.status_bruto || "desconhecido");
const motivo = String(inst.lastDisconnectReason || "não informado");

const mensagem =
  "🔴 *INSTÂNCIA DESCONECTADA*\\n\\n" +
  "*Instância:* " + (ds1.instancia_nome || chave) + "\\n" +
  "*Número:* " + (ds1.instancia_numero || inst.owner || "-") + "\\n" +
  "*Status:* " + statusAtual + "\\n" +
  "*Motivo:* " + motivo + "\\n" +
  "*Verificado em:* " + quando + "\\n\\n" +
  "Esse WhatsApp parou de enviar e receber mensagens no CRM.\\n" +
  "Reconecte lendo o QR Code em {UAZAPI_HOST}";

return {{
  pode_alertar: pode ? "sim" : "",
  mensagem_alerta: mensagem,
  status_verificado: statusAtual
}};
"""

TEXTO_ALERTA = "{mensagem|[Javascript-2]mensagem_alerta}"

B = {n: uid(n) for n in [
    "trigger", "js1", "cond-desconexao", "delay", "api-status", "cond-ainda-fora",
    "set-phone", "cond-lead", "create-lead", "js2", "cond-dedup",
    "cond-qual-instancia", "chat-por-gerencia", "chat-por-mesquita",
]}


def bloco(bid, tipo, options, x, y):
    return {
        "id": bid,
        "type": tipo,
        "sourceBlockId": None,
        "options": options,
        "presentation": {"x": x, "y": y},
    }


def chat_alerta(bid, instance_id, x, y):
    return bloco(bid, "chat", {
        "messages": [{
            "name": "send-text-message",
            "group": "messages",
            "stepId": uid(bid + "-step"),
            "options": {
                "text": TEXTO_ALERTA,
                "buttons": [],
                "breakMessages": False,
                "breakMessagesIntervalInSeconds": 2,
            },
        }],
        "platform": "WHATSAPP",
        "provider": "UAZAPI",
        "timezone": "",
        "contactId": "",
        "instanceId": instance_id,
        "nextBlockId": "",
        "isAnnotation": False,
        "scheduledDate": "",
        "errorNextBlockId": "",
    }, x, y)


blocks = [
    bloco(B["trigger"], "trigger", {
        "triggers": [{
            "name": "json-http-request-trigger",
            "group": "http",
            "options": {"datasourceName": "uaz-connection", "datasourceColor": "#3b82f6"},
        }],
        "nextBlockId": B["js1"],
    }, 200, 0),

    bloco(B["js1"], "javascript", {
        "timeout": 30,
        "nextBlockId": B["cond-desconexao"],
        "datasourceName": "Javascript-1",
        "javascriptCode": JS_IDENTIFICA,
        "datasourceColor": "#3b82f6",
    }, 200, 350),

    bloco(B["cond-desconexao"], "condition", {
        "conditions": [{
            "name": "field-has-value-condition",
            "group": "field",
            "options": {"parameter": "[Javascript-1]eh_desconexao"},
        }],
        "trueNextBlockId": B["delay"],
        "falseNextBlockId": "",
    }, 200, 700),

    bloco(B["delay"], "delay", {
        "delay": {"name": "minutes-delay", "group": "time", "options": {"minutes": DEBOUNCE_MIN}},
        "nextBlockId": B["api-status"],
    }, 200, 1050),

    bloco(B["api-status"], "api", {
        "apis": [{
            "name": "json-http-request-api",
            "group": "http",
            "stepId": uid("api-status-step"),
            "options": {
                "url": f"{UAZAPI_HOST}/instance/status",
                "body": "",
                "query": [],
                "method": "GET",
                "headers": [{"key": "token", "value": "{token_uaz|[Javascript-1]token_uaz}"}],
                "datasourceName": "status-uaz",
                "datasourceColor": "#f59e0b",
            },
        }],
        "nextBlockId": B["cond-ainda-fora"],
        # se nem o status responde, algo esta errado -> alerta assim mesmo
        "errorNextBlockId": B["set-phone"],
    }, 200, 1400),

    bloco(B["cond-ainda-fora"], "condition", {
        "conditions": [{
            "name": "field-is-equal-condition",
            "group": "field",
            "options": {"equalsTo": "connected", "parameter": "[status-uaz]instance.status"},
        }],
        "trueNextBlockId": "",              # reconectou sozinha -> silencio
        "falseNextBlockId": B["set-phone"],
    }, 200, 1750),

    bloco(B["set-phone"], "field-operation", {
        "nextBlockId": B["cond-lead"],
        "fieldOperations": [{
            "name": "set-field-operation",
            "group": "field",
            "stepId": uid("set-phone-step"),
            "options": {"value": TELEFONE_ALERTA, "parameter": "leadPhone"},
        }],
    }, 200, 2100),

    bloco(B["cond-lead"], "condition", {
        "conditions": [{
            "name": "lead-with-phone-exists-condition",
            "group": "lead",
            "options": {"phone": TELEFONE_ALERTA},
        }],
        "trueNextBlockId": B["js2"],
        "falseNextBlockId": B["create-lead"],
    }, 200, 2450),

    bloco(B["create-lead"], "action", {
        "actions": [{"name": "create-lead-action", "group": "lead", "options": {}}],
        "nextBlockId": B["js2"],
    }, -400, 2450),

    bloco(B["js2"], "javascript", {
        "timeout": 30,
        "nextBlockId": B["cond-dedup"],
        "datasourceName": "Javascript-2",
        "javascriptCode": JS_DEDUP,
        "datasourceColor": "#22c55e",
    }, 200, 2800),

    bloco(B["cond-dedup"], "condition", {
        "conditions": [{
            "name": "field-has-value-condition",
            "group": "field",
            "options": {"parameter": "[Javascript-2]pode_alertar"},
        }],
        "trueNextBlockId": B["cond-qual-instancia"],
        "falseNextBlockId": "",             # ja avisei ha menos de 30 min
    }, 200, 3150),

    # o alerta nao pode sair pela instancia que caiu
    bloco(B["cond-qual-instancia"], "condition", {
        "conditions": [{
            "name": "field-is-equal-condition",
            "group": "field",
            "options": {"equalsTo": INST_DC_MESQUITA, "parameter": "[Javascript-1]instancia_dc"},
        }],
        "trueNextBlockId": B["chat-por-gerencia"],
        "falseNextBlockId": B["chat-por-mesquita"],
    }, 200, 3500),

    chat_alerta(B["chat-por-gerencia"], INST_DC_GERENCIA, -400, 3850),
    chat_alerta(B["chat-por-mesquita"], INST_DC_MESQUITA, 200, 3850),
]

NOTA = (
    "🔌 MONITOR DE INSTÂNCIAS UAZAPI\n\n"
    "Gatilho: webhook `connection` da uazapi\n"
    "(adicionar com action=add — NÃO sobrescrever o webhook do canal)\n\n"
    f"1. JS identifica a instância pelo token/owner do payload\n"
    f"2. Espera {DEBOUNCE_MIN} min (debounce de reconexão automática)\n"
    "3. GET /instance/status confirma — essa é a fonte da verdade\n"
    "4. Ainda fora → materializa o lead do responsável\n"
    f"5. JS aplica anti-flood de {JANELA_DEDUP_MIN} min por instância\n"
    "6. Envia o alerta por uma instância DIFERENTE da que caiu\n\n"
    f"⚠️ Requer o campo adicional `{CAMPO_DEDUP}` (texto, entity lead).\n"
    "Sem ele o anti-flood não persiste e o alerta pode repetir.\n"
    f"⚠️ Telefone do alerta: {TELEFONE_ALERTA}\n"
    "⚠️ Tokens uazapi ficam embutidos no JS — não versionar em repo público."
)

automacao = {
    "id": uid("automacao"),
    "createdAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    "name": "Monitor — Instância uazapi desconectada",
    "version": 1,
    "active": False,
    "notes": [{
        "id": uid("nota"),
        "options": {"text": NOTA, "color": "#bae6fd", "width": 520, "height": 460},
        "presentation": {"x": -900, "y": -200},
    }],
    "blocks": blocks,
    "tenantId": TENANT_ID,
}

SAIDA.parent.mkdir(parents=True, exist_ok=True)
SAIDA.write_text(json.dumps(automacao, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"gerado: {SAIDA.relative_to(RAIZ)} ({len(blocks)} blocos)")
if TELEFONE_ALERTA.endswith("000000000"):
    print("⚠️  TELEFONE_ALERTA ainda é placeholder — trocar e regerar.")

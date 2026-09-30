"""Diagnóstico diário por IA: lê as conversas do dia + estado dos funis,
gera análise estruturada (JSON) e envia resumo no WhatsApp via uazapi.
"""
import json
import logging
import re
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import config, db, metrics, uazapi

log = logging.getLogger("painel.diagnostico")

PROMPT_SISTEMA = """Você é o analista comercial diário da Master Clinic, uma clínica \
odontológica com unidades em Ipatinga e Mesquita (MG). Todo dia você recebe: as conversas \
de WhatsApp do dia, o estado dos funis de venda, as oportunidades em aberto detectadas por \
regra e o gasto de tráfego pago do dia.

Seu papel: diagnosticar o dia como um gestor comercial experiente faria. Seja específico e \
acionável — cite nomes, telefones e o que fazer. Não invente dados: se algo não está no \
material, não afirme. Escreva em português brasileiro, direto, sem enrolação.

Sobre o faturamento: os valores vêm dos pagamentos recebidos no Clinicorp no dia. Lembre que \
pagamento recebido hoje pode ser parcela de um tratamento vendido meses atrás — não conclua \
que o anúncio de hoje gerou a receita de hoje.

Responda SOMENTE com um JSON válido neste formato:
{
  "resumo_executivo": "parágrafo único com os 2-3 pontos mais importantes do dia",
  "oportunidades": [
    {"nome": "...", "telefone": "...", "conversa_id": "...", "diagnostico": "o que está acontecendo",
     "acao": "o que a recepção deve fazer amanhã cedo", "prioridade": "alta|media|baixa"}
  ],
  "alertas_atendimento": ["problemas de atendimento observados nas conversas (demora, resposta seca, informação errada)"],
  "insight_trafego": "leitura sobre a qualidade dos leads de anúncio do dia, o retorno (faturamento vs gasto) e o que dizer ao gestor de tráfego",
  "temas_do_dia": ["procedimentos/assuntos mais pedidos hoje"],
  "nota_do_dia": 0-10
}"""


def _transcricoes_do_dia(dia: date) -> list[dict]:
    tz = ZoneInfo(config.TZ)
    ini = datetime(dia.year, dia.month, dia.day, tzinfo=tz)
    fim = ini + timedelta(days=1)
    convs = db.q(
        """SELECT DISTINCT c.id, c.nome, c.telefone, c.instancia_nome, c.origem, c.assunto
           FROM conversas c
           JOIN mensagens m ON m.conversa_id = c.id
           WHERE m.criada_em >= %s AND m.criada_em < %s
             AND c.assunto = 'paciente'
           ORDER BY c.id
           LIMIT %s""",
        (ini, fim, config.DIAGNOSTICO_MAX_CONVERSAS),
    )
    out = []
    for c in convs:
        msgs = db.q(
            """SELECT corpo, recebida, interna, criada_em FROM mensagens
               WHERE conversa_id = %s AND corpo IS NOT NULL
               ORDER BY criada_em""",
            (c["id"],),
        )
        linhas = []
        for m in msgs:
            if m["interna"]:
                continue
            autor = "PACIENTE" if m["recebida"] else "CLINICA"
            hora = m["criada_em"].astimezone(ZoneInfo(config.TZ)).strftime("%d/%m %H:%M")
            linhas.append(f"[{hora}] {autor}: {m['corpo']}")
        txt = "\n".join(linhas)[-config.DIAGNOSTICO_MAX_CHARS_CONVERSA :]
        out.append({**c, "transcricao": txt})
    return out


def _montar_material(dia: date) -> str:
    cards = metrics.cards(dias=1)
    oport = metrics.oportunidades(limite=20)
    estag = metrics.negocios_estagnados(limite=15)
    transc = _transcricoes_do_dia(dia)

    def _fmt_oport(o):
        return (
            f"- {o['nome'] or 'sem nome'} ({o['telefone']}) [{o['motivo']}] "
            f"{o['horas_sem_resposta']}h sem resposta | origem={o['origem']} | conversa_id={o['id']}"
        )

    def _fmt_estag(n):
        return (
            f"- {n['nome'] or 'sem nome'} ({n['telefone'] or '?'}) em '{n['etapa']}' "
            f"({n['pipeline']}) há {n['dias_parado']} dias | R$ {n['total'] or 0:.0f}"
        )

    agenda = []
    try:
        agenda = metrics.agenda_clinicorp(dias_futuro=0)
    except Exception:
        pass

    def _fmt_ag(a):
        chegou = f"CHEGOU {a['checkin_em']}" if a["checkin_em"] else "não chegou ainda"
        origem = f" | origem={a['origem_conversa']}" if a.get("origem_conversa") else ""
        return f"- {a['hora_ini']} {a['paciente']} ({a['procedimentos'] or '?'}) [{chegou}]{origem}"

    pagamentos = db.q(
        """SELECT p.paciente, p.valor::float, p.forma
           FROM clinicorp_pagamentos p
           WHERE p.recebido_em = %s AND NOT p.cancelado AND p.recebido
           ORDER BY p.valor DESC LIMIT 25""",
        (dia,),
    )

    partes = [
        f"## DIA ANALISADO: {dia.strftime('%d/%m/%Y')}",
        f"\n## MÉTRICAS DO DIA\n{json.dumps(cards, ensure_ascii=False, default=str)}",
        "\n## FATURAMENTO DO DIA (pagamentos recebidos no Clinicorp)\n"
        + (
            "\n".join(
                f"- {p['paciente']}: R$ {p['valor']:.2f} ({p['forma']})" for p in pagamentos
            )
            or "nenhum pagamento recebido hoje"
        ),
        "\n## AGENDA DE HOJE (Clinicorp)\n"
        + ("\n".join(_fmt_ag(a) for a in agenda) or "sem dados do Clinicorp"),
        "\n## OPORTUNIDADES EM ABERTO (regra: lead esperando resposta)\n"
        + ("\n".join(_fmt_oport(o) for o in oport) or "nenhuma"),
        "\n## NEGÓCIOS ESTAGNADOS NO FUNIL\n"
        + ("\n".join(_fmt_estag(n) for n in estag) or "nenhum"),
        f"\n## CONVERSAS DO DIA ({len(transc)} conversas de pacientes)",
    ]
    for t in transc:
        partes.append(
            f"\n### {t['nome'] or 'sem nome'} ({t['telefone']}) | canal={t['instancia_nome']} "
            f"| origem={t['origem']} | conversa_id={t['id']}\n{t['transcricao']}"
        )
    return "\n".join(partes)


# ---------- provedores de IA ----------

def _chamar_anthropic(material: str) -> tuple[str, str]:
    corpo = {
        "model": config.AI_MODEL_ANTHROPIC,
        "max_tokens": 4000,
        "system": PROMPT_SISTEMA,
        "messages": [{"role": "user", "content": material}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(corpo).encode(),
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode())
    texto = "".join(b.get("text", "") for b in d.get("content", []))
    return texto, config.AI_MODEL_ANTHROPIC


def _chamar_gemini(material: str) -> tuple[str, str]:
    corpo = {
        "system_instruction": {"parts": [{"text": PROMPT_SISTEMA}]},
        "contents": [{"parts": [{"text": material}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    ultimo_erro = None
    for modelo in [m.strip() for m in config.AI_MODEL_GEMINI.split(",") if m.strip()]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{modelo}:generateContent"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(corpo).encode(),
            headers={
                "x-goog-api-key": config.GEMINI_API_KEY,
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read().decode())
            texto = d["candidates"][0]["content"]["parts"][0]["text"]
            return texto, modelo
        except Exception as e:  # 404 (modelo indisponível p/ conta) ou 503 (demanda)
            ultimo_erro = e
            log.warning("gemini %s falhou (%s), tentando próximo", modelo, e)
    raise RuntimeError(f"todos os modelos Gemini falharam: {ultimo_erro}")


def _chamar_ia(material: str) -> tuple[dict, str]:
    provider = config.AI_PROVIDER
    if provider == "auto":
        provider = "anthropic" if config.ANTHROPIC_API_KEY else "gemini"
    if provider == "anthropic" and not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY ausente")
    if provider == "gemini" and not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY ausente")

    texto, modelo = (
        _chamar_anthropic(material) if provider == "anthropic" else _chamar_gemini(material)
    )
    ini = texto.find("{")
    if ini == -1:
        raise RuntimeError(f"IA não devolveu JSON: {texto[:200]}")
    # raw_decode pega o primeiro objeto válido e ignora lixo depois (alguns
    # modelos devolvem o JSON duplicado ou com texto extra ao final)
    obj, _fim = json.JSONDecoder().raw_decode(texto[ini:])
    return obj, modelo


# ---------- digest WhatsApp ----------

def _montar_digest(dia: date, diag: dict) -> str:
    cards = metrics.cards(dias=1)
    linhas = [
        f"🦷 *Master Clinic — Diagnóstico {dia.strftime('%d/%m')}*",
        "",
        f"📊 Leads hoje: {cards['leads_novos']} ({cards['leads_trafego']} de tráfego)"
        + (f" | CPL R$ {cards['cpl_trafego']:.2f}" if cards.get("cpl_trafego") else ""),
        f"💰 Faturamento: R$ {cards['receita_clinicorp']:.2f} "
        f"({cards['pagamentos']} pagamentos)",
        f"📉 Gasto Meta: R$ {cards['gasto_meta']:.2f}"
        + (f" | ROAS {cards['roas']}×" if cards.get("roas") else ""),
        f"⏳ Aguardando resposta: {cards['sem_resposta']}",
        "",
        f"📝 {diag.get('resumo_executivo', '')}",
    ]
    oport = [o for o in diag.get("oportunidades", []) if o.get("prioridade") == "alta"]
    if oport:
        linhas += ["", "🔥 *Prioridades pra amanhã cedo:*"]
        for o in oport[:5]:
            linhas.append(f"• {o.get('nome')} ({o.get('telefone')}): {o.get('acao')}")
    alertas = diag.get("alertas_atendimento") or []
    if alertas:
        linhas += ["", "⚠️ *Atendimento:*"] + [f"• {a}" for a in alertas[:3]]
    if diag.get("insight_trafego"):
        linhas += ["", f"📈 *Tráfego:* {diag['insight_trafego']}"]
    if diag.get("nota_do_dia") is not None:
        linhas += ["", f"Nota do dia: *{diag['nota_do_dia']}/10*"]
    return "\n".join(linhas)


def rodar(dia: date | None = None, enviar: bool = True) -> dict:
    dia = dia or datetime.now(ZoneInfo(config.TZ)).date()
    material = _montar_material(dia)
    diag, modelo = _chamar_ia(material)

    db.ex(
        """INSERT INTO diagnosticos (data, modelo, resumo, json)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (data) DO UPDATE
             SET modelo = EXCLUDED.modelo, resumo = EXCLUDED.resumo,
                 json = EXCLUDED.json, gerado_em = now()""",
        (dia, modelo, diag.get("resumo_executivo"), json.dumps(diag, ensure_ascii=False)),
    )

    if enviar and config.UAZAPI_TOKEN and config.DIGEST_PHONES:
        texto = _montar_digest(dia, diag)
        ok = True
        for numero in config.DIGEST_PHONES:
            try:
                uazapi.enviar_texto(numero, texto)
            except Exception as e:
                ok = False
                log.error("digest p/ %s falhou: %s", numero, e)
        if ok:
            db.ex("UPDATE diagnosticos SET enviado_whatsapp = true WHERE data = %s", (dia,))
    log.info("diagnóstico %s gerado (%s)", dia, modelo)
    return diag

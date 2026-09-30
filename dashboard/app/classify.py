"""Classificação de conversas — portada de scripts/analisar_conversas.py.

Sinais validados na raspagem completa do tenant (ADR 004): a assinatura confiável
de tráfego pago é a mensagem pré-preenchida do Click-to-WhatsApp na 1ª mensagem
do lead; lead.source está vazio em 100% dos leads.
"""
import json
import re
import unicodedata
from datetime import datetime

PROCEDIMENTOS = {
    "implante": ["implante", "implantes", "implantodontia", "pino no dente"],
    "protese": ["protese", "protese total", "dentadura", "ponte fixa", "protocolo"],
    "lente_faceta": ["lente de contato", "lentes", "faceta", "facetas"],
    "clareamento": ["clareamento", "clarear", "branqueamento", "dente branco"],
    "ortodontia": ["aparelho", "ortodontia", "alinhador", "invisalign"],
    "canal": ["canal", "endodontia", "tratamento de canal"],
    "extracao": ["extracao", "extrair", "arrancar", "siso", "sisos"],
    "restauracao": ["restauracao", "resina", "obturacao", "carie", "caries"],
    "limpeza": ["limpeza", "profilaxia", "tartaro", "raspagem"],
    "periodontia": ["gengiva", "periodontia", "gengivite", "sangramento"],
    "hof": ["harmonizacao", "botox", "preenchimento", "toxina", "hof"],
    "dtm_bruxismo": ["bruxismo", "dtm", "atm", "placa de mordida", "ranger"],
    "odontopediatria": ["odontopediatria", "dentista infantil", "meu filho", "crianca"],
    "urgencia": ["dor", "doendo", "urgencia", "emergencia", "inchado", "abscesso"],
}

ABERTURAS_CTWA = [
    "posso ter mais informacoes sobre isso",
    "posso saber mais informacoes sobre isto",
    "tenho interesse. gostaria de informacoes",
    "tenho interesse e queria mais informacoes",
    "tenho interesse em levar meu filho",
    "diga como podemos ajudar voce",
    "gostaria de saber mais informacoes",
    "quero saber mais sobre",
]

SINAIS_TRAFEGO = [
    "vim pelo anuncio", "vi o anuncio", "vi no instagram", "vi no facebook",
    "vi a publicacao", "vi um post", "vi o post", "vim pelo instagram",
    "vi no google", "clicando no anuncio", "vi a propaganda", "pela propaganda",
    "vim pelo site", "vi o video",
]

SINAIS_VAGA = [
    "curriculo", "curriculum", "vaga", "oportunidade na equipe", "processo seletivo",
    "estou me candidatando", "setor responsavel", "entrevista",
]
SINAIS_FORNECEDOR = [
    "sou consultora", "sou consultor", "represento a", "sou representante",
    "nossa empresa", "parceria comercial", "apresentar uma oportunidade",
    "trabalhamos com", "essa broca", "nossos produtos",
]

SINAIS_AGENDAMENTO = [
    "agendar", "agendado", "agendamento", "marcar", "marcado", "horario",
    "consulta", "avaliacao", "que dia", "que horas", "disponibilidade",
    "confirmado", "te espero", "sua consulta",
]

SINAIS_PRECO = [
    "valor", "valores", "preco", "precos", "quanto custa", "quanto fica",
    "quanto sai", "orcamento", "parcelar", "parcela", "cartao", "pix",
    "convenio", "plano odontologico", "financiamento",
]

# anotação interna gravada pelo fluxo X1 (CAPI) — contém o ad_id do criativo
_RE_AD_ID = re.compile(r"ad_id\s*[:=]\s*(\d{6,})")
_RE_CTWA_CLID = re.compile(r"ctwa_clid\s*[:=]\s*([\w-]{10,})")


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def tempo_1a_resposta(msgs):
    """Minutos entre a 1ª mensagem do lead e a 1ª resposta (não interna) da clínica."""
    primeira_lead = next((m for m in msgs if m.get("received")), None)
    if not primeira_lead:
        return None
    t0 = _dt(primeira_lead.get("createdAt"))
    for m in msgs:
        if not m.get("received") and not m.get("isInternal"):
            d = _dt(m.get("createdAt"))
            if d and t0 and d > t0:
                return round((d - t0).total_seconds() / 60, 1)
    return None


def classificar(msgs: list[dict], lead: dict | None = None) -> dict:
    """Classifica uma conversa a partir das mensagens ordenadas por data."""
    msgs = sorted(msgs, key=lambda m: m.get("createdAt") or "")
    externas = [m for m in msgs if not m.get("isInternal")]
    inbound = [m for m in externas if m.get("received")]
    outbound = [m for m in externas if not m.get("received")]

    texto_in = " ".join(norm(m.get("body")) for m in inbound)
    texto_all = " ".join(norm(m.get("body")) for m in externas)
    primeira_lead = norm(inbound[0].get("body")) if inbound else ""

    origem, evidencia = "desconhecida", None
    for a in ABERTURAS_CTWA:
        if a in primeira_lead:
            origem, evidencia = "trafego", f"CTWA: {a}"
            break

    tem_tag_trafego = False
    if lead:
        for t in lead.get("tags") or []:
            nt = norm(t.get("name") if isinstance(t, dict) else str(t))
            if "trafego" in nt or "ads" in nt or "anuncio" in nt:
                tem_tag_trafego = True
                break
    if origem == "desconhecida" and tem_tag_trafego:
        origem, evidencia = "tag_trafego", "tag: Tráfego Pago (sinal fraco)"

    if origem != "trafego":
        for s in SINAIS_TRAFEGO:
            if s in texto_in:
                origem, evidencia = "trafego", f"frase: {s}"
                break

    # atribuição por anúncio: anotação interna do fluxo X1
    ad_id = ctwa_clid = None
    for m in msgs:
        if m.get("isInternal") and m.get("body"):
            am = _RE_AD_ID.search(m["body"])
            cm = _RE_CTWA_CLID.search(m["body"])
            if am:
                ad_id = am.group(1)
                origem, evidencia = "trafego", "anotação X1 (ad_id)"
            if cm:
                ctwa_clid = cm.group(1)

    assunto = (
        "vaga"
        if any(s in texto_all for s in SINAIS_VAGA)
        else "fornecedor"
        if any(s in texto_in for s in SINAIS_FORNECEDOR)
        else "paciente"
    )

    procs = [n for n, kws in PROCEDIMENTOS.items() if any(k in texto_in for k in kws)]
    ultima_externa = externas[-1] if externas else None

    return {
        "origem": origem,
        "evidencia_origem": evidencia,
        "assunto": assunto,
        "procedimentos": procs,
        "pediu_preco": any(s in texto_in for s in SINAIS_PRECO),
        "chegou_agendamento": any(s in texto_all for s in SINAIS_AGENDAMENTO),
        "primeira_msg_lead": (inbound[0].get("body") or "")[:300] if inbound else None,
        "n_msgs": len(externas),
        "n_lead": len(inbound),
        "n_clinica": len(outbound),
        "resposta_min": tempo_1a_resposta(externas),
        "ultima_msg_de_lead": bool(ultima_externa and ultima_externa.get("received")),
        "ad_id": ad_id,
        "ctwa_clid": ctwa_clid,
    }

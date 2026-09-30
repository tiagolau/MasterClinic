#!/usr/bin/env python3
"""Analisa as conversas raspadas do DataCrazy (Master Clinic).

Classifica cada conversa em:
  - origem: trafego (CTWA/anúncio/LP) | organico | desconhecida
  - intencao: procedimento (cita tratamento odonto) | outro

E extrai insumos para desenhar o chatbot:
  - perguntas feitas pelo lead (frases interrogativas inbound)
  - perguntas feitas pelo atendente (para virar o roteiro do bot)
  - vocabulário/tom da clínica (aberturas, fechamentos, emojis, tamanho médio)
  - procedimentos mais citados
  - funil observado (quantas conversas chegam a agendamento)

Uso:
    python3 scripts/analisar_conversas.py            # relatório no stdout
    python3 scripts/analisar_conversas.py --json     # dump estruturado em data/analise.json
"""
import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
MSGS = DATA / "messages"

PROCEDIMENTOS = {
    "implante": ["implante", "implantes", "implantodontia", "pino no dente"],
    "protese": ["protese", "protese total", "dentadura", "ponte fixa", "protocolo"],
    "lente_faceta": ["lente de contato", "lentes", "faceta", "facetas"],
    "clareamento": ["clareamento", "clarear", "branqueamento", "dente branco"],
    "ortodontia": [
        "aparelho", "ortodontia", "alinhador", "invisalign", "manutencao do aparelho",
    ],
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

# Mensagens pré-preenchidas do Click-to-WhatsApp (Meta) — assinatura mais confiável de
# tráfego pago neste tenant. Levantadas por frequência nas primeiras mensagens do lead.
ABERTURAS_CTWA = [
    "posso ter mais informacoes sobre isso",
    "posso saber mais informacoes sobre isto",
    "tenho interesse. gostaria de informacoes",
    "tenho interesse e queria mais informacoes",
    "tenho interesse em levar meu filho",
    "diga como podemos ajudar voce",
    "gostaria de saber mais informacoes",
    "quero saber mais sobre",
    # NÃO incluir "campaign_event_trigger": é clique em botão de lembrete de consulta
    # (paciente já da casa), não clique em anúncio.
]

SINAIS_TRAFEGO = [
    "vim pelo anuncio", "vi o anuncio", "vi no instagram", "vi no facebook",
    "vi a publicacao", "vi um post", "vi o post", "vim pelo instagram",
    "vi no google", "clicando no anuncio", "vi a propaganda", "pela propaganda",
    "vim pelo site", "vi o video",
]

# ruído: gente oferecendo serviço/currículo, não paciente. O anúncio de VAGA cai no
# canal "Gerência Uazapi" com a mesma abertura CTWA das campanhas de paciente.
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


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def carregar():
    convs = json.loads((DATA / "conversations.json").read_text())["data"]
    # indexa leads por id (contact.externalId da conversa é o leadId) e por telefone
    leads = {}
    p_leads = DATA / "leads.json"
    if p_leads.exists():
        for l in json.loads(p_leads.read_text()).get("data", []):
            leads[l["id"]] = l
            for chave in filter(None, [l.get("rawPhone"), l.get("phone")]):
                leads.setdefault(re.sub(r"\D", "", chave), l)
    inst = {}
    p_inst = DATA / "instances.json"
    if p_inst.exists():
        for i in json.loads(p_inst.read_text()).get("data", []):
            inst[i["id"]] = i
    return convs, leads, inst


def mensagens(conv_id):
    p = MSGS / f"{conv_id}.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    msgs = d.get("messages", []) if isinstance(d, dict) else d
    return sorted(msgs, key=lambda m: m.get("createdAt") or "")


def dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def classificar(conv, msgs, lead):
    texto_in = " ".join(norm(m.get("body")) for m in msgs if m.get("received"))
    texto_all = " ".join(norm(m.get("body")) for m in msgs)

    inbound = [m for m in msgs if m.get("received")]
    primeira_lead = norm(inbound[0].get("body")) if inbound else ""
    origem, evidencia = "desconhecida", None

    # sinal 1 (mais forte): abertura padrão de Click-to-WhatsApp
    for a in ABERTURAS_CTWA:
        if a in primeira_lead:
            origem, evidencia = "trafego", f"CTWA: {a}"
            break

    # sinal 2 (fraco): tag "Tráfego Pago" — está poluída no tenant (aparece até em
    # conversas internas e de financeiro), então só classifica como "tag_trafego"
    tem_tag_trafego = False
    if lead:
        for t in lead.get("tags") or []:
            nt = norm(t.get("name") if isinstance(t, dict) else str(t))
            if "trafego" in nt or "ads" in nt or "anuncio" in nt:
                tem_tag_trafego = True
                break
    if origem == "desconhecida" and tem_tag_trafego:
        origem, evidencia = "tag_trafego", "tag: Tráfego Pago (sinal fraco)"

    if origem != "trafego" and lead:
        ref = lead.get("sourceReferral")
        src = lead.get("source")
        if ref:
            origem, evidencia = "trafego", f"sourceReferral={json.dumps(ref, ensure_ascii=False)[:120]}"
        elif src and any(
            k in norm(str(src)) for k in ["ads", "anuncio", "meta", "face", "insta", "lp", "trafego", "google"]
        ):
            origem, evidencia = "trafego", f"source={src}"
        elif src:
            origem, evidencia = "organico", f"source={src}"
    if origem != "trafego":
        for s in SINAIS_TRAFEGO:
            if s in texto_in:
                origem, evidencia = "trafego", f"frase: {s}"
                break
    # CTWA da Cloud API costuma vir com contexto de anúncio na 1ª mensagem
    primeira = msgs[0] if msgs else {}
    if primeira.get("received") and isinstance(primeira.get("buttons"), list):
        for b in primeira.get("buttons") or []:
            if "ctwa" in norm(json.dumps(b)) or "ad" == norm(str(b.get("type", ""))):
                origem, evidencia = "trafego", "botão CTWA na 1ª mensagem"

    procs = [
        nome for nome, kws in PROCEDIMENTOS.items() if any(k in texto_all for k in kws)
    ]
    procs_lead = [
        nome for nome, kws in PROCEDIMENTOS.items() if any(k in texto_in for k in kws)
    ]
    return {
        "origem": origem,
        "evidencia_origem": evidencia,
        "tem_tag_trafego": tem_tag_trafego,
        "assunto": (
            "vaga"
            if any(s in texto_all for s in SINAIS_VAGA)
            else "fornecedor"
            if any(s in texto_in for s in SINAIS_FORNECEDOR)
            else "paciente"
        ),
        "procedimentos": procs,
        "procedimentos_citados_pelo_lead": procs_lead,
        "pediu_preco": any(s in texto_in for s in SINAIS_PRECO),
        "chegou_agendamento": any(s in texto_all for s in SINAIS_AGENDAMENTO),
    }


def perguntas(msgs, received: bool):
    out = []
    for m in msgs:
        if bool(m.get("received")) != received:
            continue
        corpo = (m.get("body") or "").strip()
        for frase in re.split(r"(?<=[?!.])\s+|\n+", corpo):
            frase = frase.strip()
            if frase.endswith("?") and 6 <= len(frase) <= 200:
                out.append(frase)
    return out


def tempo_1a_resposta(msgs):
    """Minutos entre a 1ª mensagem do lead e a 1ª resposta da clínica."""
    primeira_lead = next((m for m in msgs if m.get("received")), None)
    if not primeira_lead:
        return None
    t0 = dt(primeira_lead.get("createdAt"))
    for m in msgs:
        if not m.get("received") and dt(m.get("createdAt")) and t0:
            d = dt(m["createdAt"])
            if d > t0:
                return round((d - t0).total_seconds() / 60, 1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    convs, leads, inst = carregar()
    registros = []
    for c in convs:
        msgs = mensagens(c["id"])
        if not msgs:
            continue
        contato = c.get("contact") or {}
        fone = re.sub(
            r"\D", "", contato.get("phoneNumber") or contato.get("contactId") or ""
        )
        lead = (
            leads.get(contato.get("externalId"))
            or leads.get(fone)
            or leads.get(fone[2:])
            or leads.get("55" + fone)
        )
        cls = classificar(c, msgs, lead)
        inbound = [m for m in msgs if m.get("received")]
        outbound = [m for m in msgs if not m.get("received")]
        registros.append(
            {
                "id": c["id"],
                "nome": c.get("name") or contato.get("name"),
                "telefone": fone,
                "instancia": (c.get("instance") or {}).get("name"),
                "inicio": c.get("createdAt"),
                "ultima": c.get("lastMessageDate"),
                "n_msgs": len(msgs),
                "n_lead": len(inbound),
                "n_clinica": len(outbound),
                "iniciada_pelo_lead": bool(msgs[0].get("received")),
                "resposta_min": tempo_1a_resposta(msgs),
                "audios_clinica": sum(
                    1
                    for m in outbound
                    for a in (m.get("attachments") or [])
                    if str(a.get("type")).upper() == "AUDIO"
                ),
                "perguntas_lead": perguntas(msgs, True),
                "perguntas_clinica": perguntas(msgs, False),
                "primeira_msg_lead": (inbound[0].get("body") or "")[:300] if inbound else None,
                **cls,
            }
        )

    trafego = [r for r in registros if r["origem"] == "trafego"]
    pacientes = [r for r in trafego if r["assunto"] == "paciente"]
    proc = [r for r in registros if r["procedimentos_citados_pelo_lead"]]

    print(f"CONVERSAS ANALISADAS: {len(registros)}")
    print(f"  tráfego confirmado (CTWA/frase): {len(trafego)}")
    print(f"     └ assunto paciente:           {len(pacientes)}")
    print(f"     └ assunto vaga de emprego:    {sum(1 for r in trafego if r['assunto']=='vaga')}")
    print(f"     └ assunto fornecedor:         {sum(1 for r in trafego if r['assunto']=='fornecedor')}")
    print(f"  só tag 'Tráfego Pago' (fraco):   {sum(1 for r in registros if r['origem']=='tag_trafego')}")
    print(f"  citou procedimento (qualquer origem): {len(proc)}")
    print()

    print("TRÁFEGO POR CANAL (todas as origens de tráfego):")
    for nome, n in Counter(r["instancia"] for r in trafego).most_common():
        pac = sum(1 for r in trafego if r["instancia"] == nome and r["assunto"] == "paciente")
        print(f"  {nome}: {n} (paciente: {pac})")
    print()

    print("ABERTURAS DE TRÁFEGO (mensagem que o anúncio pré-preenche):")
    for t, n in Counter(norm(r["primeira_msg_lead"])[:80] for r in trafego).most_common(12):
        print(f"  [{n}] {t}")
    print()

    print("PROCEDIMENTOS CITADOS PELO LEAD (tráfego/paciente):")
    for p, n in Counter(
        p for r in pacientes for p in r["procedimentos_citados_pelo_lead"]
    ).most_common():
        print(f"  {p}: {n}")
    print("  — em toda a base:")
    for p, n in Counter(
        p for r in registros for p in r["procedimentos_citados_pelo_lead"]
    ).most_common(8):
        print(f"    {p}: {n}")
    print()

    print(f"PERGUNTAS DO LEAD (tráfego/paciente) — top {args.top}:")
    for q, n in Counter(
        norm(q) for r in pacientes for q in r["perguntas_lead"]
    ).most_common(args.top):
        print(f"  [{n}] {q}")
    print()

    print(f"PERGUNTAS DA CLÍNICA (roteiro humano de qualificação) — top {args.top}:")
    for q, n in Counter(
        norm(q) for r in pacientes for q in r["perguntas_clinica"]
    ).most_common(args.top):
        print(f"  [{n}] {q}")
    print()

    tempos = sorted(r["resposta_min"] for r in pacientes if r["resposta_min"] is not None)
    print("FUNIL / SLA (tráfego + paciente):")
    if tempos:
        mediana = tempos[len(tempos) // 2]
        print(f"  1ª resposta — mediana: {mediana:.0f} min | pior: {tempos[-1]:.0f} min")
        print(f"     respondidos em até 5 min:  {sum(1 for t in tempos if t <= 5)}/{len(tempos)}")
        print(f"     demoraram mais de 1 hora:  {sum(1 for t in tempos if t > 60)}/{len(tempos)}")
        print(f"     demoraram mais de 6 horas: {sum(1 for t in tempos if t > 360)}/{len(tempos)}")
    sem_resposta = [r for r in pacientes if r["resposta_min"] is None]
    print(f"  nunca responderam:      {len(sem_resposta)}/{len(pacientes)}")
    print(f"  pediram preço:          {sum(1 for r in pacientes if r['pediu_preco'])}")
    print(f"  falaram de agenda:      {sum(1 for r in pacientes if r['chegou_agendamento'])}")
    print(f"  lead mandou 1 msg só:   {sum(1 for r in pacientes if r['n_lead'] <= 1)}")
    print(f"  clínica respondeu com áudio: {sum(1 for r in pacientes if r['audios_clinica'])}")

    if args.json:
        saida = DATA / "analise.json"
        saida.write_text(
            json.dumps(
                {
                    "registros": registros,
                    "trafego_paciente_ids": [r["id"] for r in pacientes],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"\n→ {saida}")


if __name__ == "__main__":
    main()

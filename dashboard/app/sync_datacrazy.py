"""Sync DataCrazy → Postgres.

Duas modalidades:
- incremental (a cada SYNC_INTERVAL_MIN): pagina conversas/negócios/leads ordenados
  desc até o watermark e baixa mensagens só das conversas com atividade nova
- completo (a cada FULL_SYNC_INTERVAL_MIN): sweep integral de leads/negócios/conversas
  (pega updates que não sobem no topo da ordenação) + pipelines/etapas/instâncias

Orçamento de requisições: incremental típico ≈ 5–25 req; completo ≈ 15–20 req +
mensagens pendentes. Throttle global de 2.2s no cliente garante < 30 req/min.
"""
import logging
from datetime import datetime, timedelta, timezone

from . import classify, datacrazy, db

log = logging.getLogger("painel.sync.dc")

MARGEM = timedelta(minutes=45)  # folga do watermark contra atrasos de ordenação


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _telefone(conv):
    contato = conv.get("contact") or {}
    import re

    return re.sub(r"\D", "", contato.get("phoneNumber") or contato.get("contactId") or "")


# ---------- upserts de cada recurso ----------

def _upsert_instancias(itens):
    linhas = []
    for i in itens:
        cfg = i.get("config") or {}
        linhas.append(
            {
                "id": i["id"],
                "nome": i.get("name"),
                "plataforma": i.get("platform"),
                "provider": i.get("provider"),
                "numero": cfg.get("phone") or cfg.get("number") or cfg.get("phoneNumber"),
                "dados": {k: v for k, v in i.items() if k != "config"},
            }
        )
    db.upsert("instancias", linhas)


def _upsert_pipelines():
    pipes = datacrazy.get("pipelines").get("data", [])
    db.upsert(
        "pipelines",
        [
            {
                "id": p["id"],
                "nome": p.get("name"),
                "grupo": (p.get("group") or {}).get("name")
                if isinstance(p.get("group"), dict)
                else p.get("group"),
                "dados": p,
            }
            for p in pipes
        ],
    )
    for p in pipes:
        etapas = datacrazy.get(f"pipelines/{p['id']}/stages").get("data", [])
        db.upsert(
            "etapas",
            [
                {
                    "id": e["id"],
                    "pipeline_id": p["id"],
                    "nome": e.get("name"),
                    "ordem": e.get("order") or e.get("position") or idx,
                    "dados": e,
                }
                for idx, e in enumerate(etapas)
            ],
        )
    log.info("pipelines: %d", len(pipes))


def _linha_lead(l):
    return {
        "id": l["id"],
        "nome": l.get("name"),
        "telefone": l.get("rawPhone") or l.get("phone"),
        "email": l.get("email"),
        "criado_em": _dt(l.get("createdAt")),
        "atualizado_em": _dt(l.get("updatedAt")),
        "fonte": l.get("source"),
        "tags": l.get("tags") or [],
        "dados": {k: v for k, v in l.items() if k not in ("tags",)},
    }


def _linha_negocio(b):
    return {
        "id": b["id"],
        "lead_id": b.get("leadId"),
        "etapa_id": b.get("stageId"),
        "status": b.get("status"),
        "total": b.get("total") or 0,
        "criado_em": _dt(b.get("createdAt")),
        "atualizado_em": _dt(b.get("updatedAt")),
        "movido_em": _dt(b.get("lastMovedAt")),
        "status_alterado_em": _dt(b.get("statusChangedAt")),
        "motivo_perda_id": b.get("lossReasonId"),
        "dados": {k: v for k, v in b.items() if k not in ("lead",)},
    }


def _linha_conversa(c):
    contato = c.get("contact") or {}
    inst = c.get("instance") or {}
    return {
        "id": c["id"],
        "nome": c.get("name") or contato.get("name"),
        "telefone": _telefone(c),
        "lead_id": contato.get("externalId"),
        "instancia_id": inst.get("id"),
        "instancia_nome": inst.get("name"),
        "criada_em": _dt(c.get("createdAt")),
        "ultima_msg_em": _dt(c.get("lastMessageDate")),
        "ultima_msg_recebida_em": _dt(c.get("lastReceivedMessageDate")),
        "finalizada": bool(c.get("finished")),
        "dados": {k: v for k, v in c.items() if k not in ("lastMessage",)},
    }


# ---------- mensagens + classificação ----------

def _sync_mensagens(conversa_id: str):
    d = datacrazy.get(f"conversations/{conversa_id}/messages")
    msgs = d.get("messages", []) if isinstance(d, dict) else []
    return _sync_mensagens_local(conversa_id, msgs)


def _sync_mensagens_local(conversa_id: str, msgs: list[dict]):
    """Persiste mensagens já baixadas e reclassifica a conversa."""
    linhas = [
        {
            "id": m["id"],
            "conversa_id": conversa_id,
            "corpo": m.get("body"),
            "recebida": bool(m.get("received")),
            "interna": bool(m.get("isInternal")),
            "criada_em": _dt(m.get("createdAt")),
            "dados": {
                k: v
                for k, v in m.items()
                if k in ("attachments", "buttons", "status", "attendant", "erroCode")
                and v
            },
        }
        for m in msgs
        if m.get("id")
    ]
    db.upsert("mensagens", linhas)

    conv = db.q1("SELECT lead_id FROM conversas WHERE id = %s", (conversa_id,))
    lead = None
    if conv and conv["lead_id"]:
        lr = db.q1("SELECT tags FROM leads WHERE id = %s", (conv["lead_id"],))
        if lr:
            lead = {"tags": lr["tags"]}
    cls = classify.classificar(msgs, lead)
    db.ex(
        """UPDATE conversas SET origem=%s, evidencia_origem=%s, assunto=%s,
             procedimentos=%s, pediu_preco=%s, chegou_agendamento=%s,
             primeira_msg_lead=%s, n_msgs=%s, n_lead=%s, n_clinica=%s,
             resposta_min=%s, ultima_msg_de_lead=%s,
             ad_id=COALESCE(%s, ad_id), ctwa_clid=COALESCE(%s, ctwa_clid),
             msgs_sync_em=now()
           WHERE id=%s""",
        (
            cls["origem"], cls["evidencia_origem"], cls["assunto"],
            db_jsonb(cls["procedimentos"]), cls["pediu_preco"], cls["chegou_agendamento"],
            cls["primeira_msg_lead"], cls["n_msgs"], cls["n_lead"], cls["n_clinica"],
            cls["resposta_min"], cls["ultima_msg_de_lead"],
            cls["ad_id"], cls["ctwa_clid"], conversa_id,
        ),
    )
    return len(msgs)


def db_jsonb(v):
    from psycopg.types.json import Jsonb

    return Jsonb(v)


def _mensagens_pendentes(max_conversas: int = 60):
    """Conversas cuja última mensagem na API é mais nova que o último sync local."""
    return db.q(
        """SELECT id FROM conversas
           WHERE ultima_msg_em IS NOT NULL
             AND (msgs_sync_em IS NULL OR ultima_msg_em > msgs_sync_em)
           ORDER BY ultima_msg_em DESC
           LIMIT %s""",
        (max_conversas,),
    )


def _aplicar_atribuicao_ctwa():
    """Casa eventos do collector (fluxo X1 → POST /ingest/ctwa) com conversas por telefone."""
    db.ex(
        """UPDATE conversas c SET
             ad_id = COALESCE(c.ad_id, e.ad_id),
             ctwa_clid = COALESCE(c.ctwa_clid, e.ctwa_clid),
             origem = CASE WHEN c.origem IN ('trafego') THEN c.origem ELSE 'trafego' END,
             evidencia_origem = COALESCE(c.evidencia_origem, 'collector CTWA')
           FROM (
             SELECT DISTINCT ON (telefone) telefone, ad_id, ctwa_clid, msg_ts
             FROM ctwa_eventos WHERE telefone IS NOT NULL AND ad_id IS NOT NULL
             ORDER BY telefone, recebido_em DESC
           ) e
           WHERE c.telefone = e.telefone
             AND c.ad_id IS NULL
             AND abs(extract(epoch FROM (c.criada_em - COALESCE(e.msg_ts, c.criada_em)))) < 172800"""
    )


# ---------- entrypoints ----------

def sync_incremental():
    inicio = datetime.now(timezone.utc)
    wm = db.estado_get("watermark_incremental", {})
    corte = _dt(wm.get("ate")) or (inicio - timedelta(days=2))
    corte = corte - MARGEM

    convs = datacrazy.paginar_ate(
        "conversations",
        lambda c: (_dt(c.get("lastMessageDate")) or _dt(c.get("createdAt")) or corte) < corte,
    )
    db.upsert("conversas", [_linha_conversa(c) for c in convs])

    negocios = datacrazy.paginar_ate(
        "businesses", lambda b: (_dt(b.get("updatedAt")) or corte) < corte, take=500
    )
    db.upsert("negocios", [_linha_negocio(b) for b in negocios])

    leads = datacrazy.paginar_ate(
        "leads", lambda l: (_dt(l.get("updatedAt")) or corte) < corte, take=500
    )
    db.upsert("leads", [_linha_lead(l) for l in leads])

    pendentes = _mensagens_pendentes()
    for row in pendentes:
        try:
            _sync_mensagens(row["id"])
        except Exception as e:  # uma conversa com erro não derruba o ciclo
            log.warning("mensagens %s: %s", row["id"], e)

    _aplicar_atribuicao_ctwa()
    db.estado_set("watermark_incremental", {"ate": inicio.isoformat()})
    log.info(
        "incremental: %d convs, %d negócios, %d leads, %d msgs-sync",
        len(convs), len(negocios), len(leads), len(pendentes),
    )


def sync_completo():
    inicio = datetime.now(timezone.utc)
    inst = datacrazy.get("instances").get("data", [])
    _upsert_instancias(inst)
    _upsert_pipelines()

    leads = datacrazy.paginar("leads")
    db.upsert("leads", [_linha_lead(l) for l in leads])

    negocios = datacrazy.paginar("businesses")
    db.upsert("negocios", [_linha_negocio(b) for b in negocios])

    convs = datacrazy.paginar("conversations")
    db.upsert("conversas", [_linha_conversa(c) for c in convs])

    pendentes = _mensagens_pendentes(max_conversas=200)
    for row in pendentes:
        try:
            _sync_mensagens(row["id"])
        except Exception as e:
            log.warning("mensagens %s: %s", row["id"], e)

    _aplicar_atribuicao_ctwa()
    db.estado_set("watermark_incremental", {"ate": inicio.isoformat()})
    db.estado_set("ultimo_sync_completo", {"em": inicio.isoformat()})
    log.info(
        "completo: %d leads, %d negócios, %d convs, %d msgs-sync",
        len(leads), len(negocios), len(convs), len(pendentes),
    )

"""Painel Master Clinic — FastAPI: API do dashboard + collector CTWA + estáticos."""
import logging
import threading
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg.types.json import Jsonb

from . import auth, config, db, diagnostico, metrics, scheduler, sync_datacrazy, sync_meta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("painel")

app = FastAPI(title="Painel Master Clinic", docs_url=None, redoc_url=None)
STATIC = Path(__file__).parent.parent / "static"


@app.on_event("startup")
def _startup():
    faltando = config.validar()
    if faltando:
        raise RuntimeError(f"variáveis de ambiente obrigatórias ausentes: {faltando}")
    db.iniciar()
    scheduler.iniciar()


def _exigir_sessao(request: Request):
    if not auth.validar_token(request.cookies.get(auth.COOKIE)):
        raise HTTPException(401, "não autenticado")


# ---------- auth ----------

@app.post("/api/login")
def login(request: Request, response: Response, corpo: dict = Body(...)):
    if not corpo.get("senha") or corpo["senha"] != config.DASHBOARD_PASSWORD:
        raise HTTPException(401, "senha incorreta")
    # atrás do Traefik vem X-Forwarded-Proto; acesso direto por IP/porta é http
    https = (
        request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    )
    response.set_cookie(
        auth.COOKIE,
        auth.emitir_token(),
        max_age=auth.VALIDADE_S,
        httponly=True,
        samesite="lax",
        secure=https,
    )
    return {"ok": True}


@app.get("/api/health")
def health():
    try:
        db.q1("SELECT 1 AS ok")
        banco = True
    except Exception:
        banco = False
    return {
        "ok": banco,
        "sync": {
            "incremental": db.estado_get("watermark_incremental"),
            "completo": db.estado_get("ultimo_sync_completo"),
            "meta": db.estado_get("ultimo_sync_meta"),
            "clinicorp": db.estado_get("ultimo_sync_clinicorp"),
        },
    }


# ---------- dados do dashboard ----------

@app.get("/api/resumo")
def resumo(request: Request, dias: int = 30):
    _exigir_sessao(request)
    dias = max(1, min(dias, 365))
    return {
        "hoje": metrics.cards(dias=1),
        "periodo": metrics.cards(dias=dias),
        "serie": metrics.serie_diaria(dias=dias),
        "funis": metrics.funis(),
        "campanhas": metrics.campanhas(dias=dias),
        "oportunidades": metrics.oportunidades(),
        "estagnados": metrics.negocios_estagnados(),
        "agenda": metrics.agenda_clinicorp(),
        "clinicorp_hoje": metrics.cards_clinicorp(dias=1),
        "clinicorp_periodo": metrics.cards_clinicorp(dias=dias),
        "gerado_em": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/api/diagnosticos")
def diagnosticos(request: Request, n: int = 7):
    _exigir_sessao(request)
    return db.q(
        """SELECT data::text, gerado_em, modelo, resumo, json, enviado_whatsapp
           FROM diagnosticos ORDER BY data DESC LIMIT %s""",
        (min(n, 60),),
    )


@app.post("/api/diagnostico/rodar")
def rodar_diagnostico(request: Request):
    _exigir_sessao(request)

    def _job():
        try:
            diagnostico.rodar()
        except Exception:
            log.exception("diagnóstico manual falhou")

    threading.Thread(target=_job, daemon=True).start()
    return {"ok": True, "msg": "diagnóstico disparado em background"}


@app.get("/api/conversa/{conversa_id}")
def conversa(request: Request, conversa_id: str):
    _exigir_sessao(request)
    conv = db.q1("SELECT * FROM conversas WHERE id = %s", (conversa_id,))
    if not conv:
        raise HTTPException(404)
    msgs = db.q(
        """SELECT corpo, recebida, interna, criada_em FROM mensagens
           WHERE conversa_id = %s ORDER BY criada_em""",
        (conversa_id,),
    )
    return {"conversa": conv, "mensagens": msgs}


@app.post("/api/sync/rodar")
def rodar_sync(request: Request, corpo: dict = Body(default={})):
    _exigir_sessao(request)
    tipo = corpo.get("tipo", "incremental")
    from . import sync_clinicorp

    alvo = {
        "incremental": sync_datacrazy.sync_incremental,
        "completo": sync_datacrazy.sync_completo,
        "meta": sync_meta.sync_meta,
        "clinicorp": sync_clinicorp.sync_clinicorp,
    }.get(tipo)
    if not alvo:
        raise HTTPException(400, "tipo inválido")

    def _job():
        try:
            alvo()
        except Exception:
            log.exception("sync manual (%s) falhou", tipo)

    threading.Thread(target=_job, daemon=True).start()
    return {"ok": True, "msg": f"sync {tipo} disparado"}


# ---------- collector CTWA (chamado pelo fluxo X1 do DataCrazy) ----------

@app.post("/ingest/ctwa")
def ingest_ctwa(request: Request, corpo: dict = Body(...)):
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    if not config.INGEST_TOKEN or token != config.INGEST_TOKEN:
        raise HTTPException(401)
    import re

    telefone = re.sub(r"\D", "", str(corpo.get("telefone") or corpo.get("phone") or ""))
    msg_ts = None
    ts = corpo.get("msg_ts") or corpo.get("messageTimestamp")
    if ts:
        try:
            ts = float(ts)
            msg_ts = datetime.utcfromtimestamp(ts / 1000 if ts > 1e12 else ts)
        except (ValueError, TypeError):
            pass
    db.ex(
        """INSERT INTO ctwa_eventos (telefone, instancia_id, ctwa_clid, ad_id, msg_ts, dados)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            telefone or None,
            corpo.get("instancia_id") or corpo.get("instanceId"),
            corpo.get("ctwa_clid") or corpo.get("ctwaClid"),
            str(corpo.get("ad_id") or corpo.get("adId") or "") or None,
            msg_ts,
            Jsonb(corpo),
        ),
    )
    return {"ok": True}


# ---------- estáticos ----------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")

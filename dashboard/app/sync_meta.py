"""Sync de insights do Meta Ads → meta_insights (nível ad, diário)."""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from . import config, db

log = logging.getLogger("painel.sync.meta")

_CAMPOS = (
    "campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,"
    "spend,impressions,clicks,actions"
)


def _get(url: str, tentativas: int = 4):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (500, 502, 503, 429, 400) and i < tentativas - 1:
                time.sleep(5 * (i + 1))
                continue
            raise



def _acao(actions, tipo):
    for a in actions or []:
        if a.get("action_type") == tipo:
            try:
                return int(float(a.get("value") or 0))
            except ValueError:
                return 0
    return 0


def _insights_dia(conta: str, dia: date) -> list[dict]:
    """Insights nível ad de um único dia (janelas grandes dão 500 no Graph)."""
    params = {
        "level": "ad",
        "fields": _CAMPOS,
        "time_range": json.dumps({"since": dia.isoformat(), "until": dia.isoformat()}),
        "limit": 500,
        "access_token": config.FB_ACCESS_TOKEN,
    }
    url = (
        f"https://graph.facebook.com/{config.META_API_VERSION}/"
        f"{conta}/insights?{urllib.parse.urlencode(params)}"
    )
    linhas = []
    while url:
        d = _get(url)
        for r in d.get("data", []):
            acts = r.get("actions")
            linhas.append(
                {
                    "data": dia.isoformat(),
                    "conta": conta,
                    "campanha_id": r.get("campaign_id"),
                    "campanha": r.get("campaign_name"),
                    "adset_id": r.get("adset_id"),
                    "adset": r.get("adset_name"),
                    "ad_id": r["ad_id"],
                    "ad": r.get("ad_name"),
                    "gasto": float(r.get("spend") or 0),
                    "impressoes": int(r.get("impressions") or 0),
                    "cliques": int(r.get("clicks") or 0),
                    "conversas_iniciadas": _acao(
                        acts, "onsite_conversion.messaging_conversation_started_7d"
                    ),
                    "leads_meta": _acao(acts, "lead"),
                    "dados": {"actions": acts} if acts else {},
                }
            )
        url = (d.get("paging") or {}).get("next")
    return linhas


def sync_meta(dias: int | None = None):
    if not config.FB_ACCESS_TOKEN:
        log.warning("FB_ACCESS_TOKEN ausente — sync Meta pulado")
        return
    dias = dias or config.META_SYNC_DIAS
    ate = date.today()
    total = 0
    for delta in range(dias):
        dia = ate - timedelta(days=delta)
        for conta in config.META_AD_ACCOUNTS:
            try:
                linhas = _insights_dia(conta, dia)
            except Exception as e:
                log.warning("insights %s %s: %s", conta, dia, e)
                continue
            total += db.upsert("meta_insights", linhas, conflito=("data", "ad_id"))
    db.estado_set("ultimo_sync_meta", {"em": date.today().isoformat(), "linhas": total})
    log.info("meta: %d linhas (%d dias)", total, dias)


def sync_meta_historico(dias: int = 90):
    """Backfill inicial — roda uma vez no primeiro boot."""
    sync_meta(dias=dias)

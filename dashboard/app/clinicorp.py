"""Cliente da API Clinicorp (Basic auth: usuário API + token).

Base: https://api.clinicorp.com/rest/v1 — validado 2026-08-04.
Endpoints que existem (o resto responde "Cannot GET", inclusive budget/treatment):
- GET /business/list  → clínicas da assinatura
- GET /appointment/list?from=YYYY-MM-DD&to=YYYY-MM-DD
  → agendamentos com PatientName, MobilePhone, CheckinTime, StatusId etc.
- GET /payment/list?from=&to=  → pagamentos, filtrados por **ReceivedDate**
  (não por PaymentDate). Sem paginação: devolve o range inteiro.
- GET /patient/get?PatientId=N → cadastro com `Phone` (o parâmetro é
  exatamente `PatientId`; `id`/`patient_id` devolvem 400).
"""
import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

log = logging.getLogger("painel.clinicorp")

BASE = "https://api.clinicorp.com/rest/v1"


def _auth() -> str:
    cred = f"{config.CLINICORP_USER}:{config.CLINICORP_TOKEN}"
    return "Basic " + base64.b64encode(cred.encode()).decode()


def get(caminho: str, params: dict | None = None, tentativas: int = 4):
    params = {"subscriber_id": config.CLINICORP_USER, **(params or {})}
    url = f"{BASE}/{caminho.lstrip('/')}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url, headers={"Authorization": _auth(), "Accept": "application/json"}
    )
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tentativas - 1:
                time.sleep(5 * (i + 1))
                continue
            raise RuntimeError(f"Clinicorp HTTP {e.code} em {caminho}: {e.read().decode()[:200]}")
        except Exception:
            if i < tentativas - 1:
                time.sleep(5 * (i + 1))
                continue
            raise


def agendamentos(dia_iso: str) -> list[dict]:
    d = get("appointment/list", {"from": dia_iso, "to": dia_iso})
    return d if isinstance(d, list) else []


def pagamentos(desde_iso: str, ate_iso: str) -> list[dict]:
    """Pagamentos recebidos no intervalo (filtro por ReceivedDate)."""
    d = get("payment/list", {"from": desde_iso, "to": ate_iso})
    return d if isinstance(d, list) else []


def paciente(paciente_id: int) -> dict | None:
    d = get("patient/get", {"PatientId": paciente_id})
    if isinstance(d, list):
        d = d[0] if d else None
    if isinstance(d, dict) and d.get("Error"):
        return None
    return d

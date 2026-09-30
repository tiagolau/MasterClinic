#!/usr/bin/env python3
"""Replica templates de uma WABA de origem para outras WABAs da mesma BM.

Headers de mídia (IMAGE/VIDEO/DOCUMENT) não podem ser copiados pela URL
`scontent` que o GET devolve: a criação de template exige um *handle* da
Resumable Upload API. O script baixa a mídia da origem, sobe uma vez pelo app
(o handle é app-scoped, serve para todas as WABAs) e reaproveita.

Uso:
    source ~/.claude/.env
    python3 scripts/replicar_templates_waba.py --dry-run
    python3 scripts/replicar_templates_waba.py
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

GRAPH = "https://graph.facebook.com/v25.0"
RAIZ = Path(__file__).resolve().parent.parent
CACHE_MIDIA = RAIZ / "media" / "handles"
LOGS = RAIZ / "logs"

ORIGEM = "306417967823808"
DESTINOS = {
    "1350953883747065": "Master Clinic (Financeiro uazapi)",
    "695879211426557": "Master clinic (Mesquita uazapi)",
    "105152822451126": "Danielle Carvalho Master Clinic",
    "616632296165144": "Financeiro - Recepção",
    "108400492289717": "Master Clinic Odontologia Especializada",
}

# O template masterclinic_confirmar está cadastrado como `en` na origem, mas o
# corpo é português (e a cópia que já existe na 105152822451126 é pt_BR).
# Replicar como `en` propagaria o erro.
CORRIGE_IDIOMA = {"masterclinic_confirmar": "pt_BR"}

# Componentes que a Graph devolve no GET mas recusa no POST.
CAMPOS_IGNORADOS = {"id", "status", "quality_score", "rejected_reason", "previous_category"}


def http(url: str, *, data=None, headers=None, method=None, raw=False):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            corpo = r.read()
    except urllib.error.HTTPError as e:
        corpo = e.read()
        if raw:
            raise
        try:
            return json.loads(corpo)
        except json.JSONDecodeError:
            return {"error": {"message": corpo.decode("utf-8", "replace")}}
    return corpo if raw else json.loads(corpo)


def listar_templates(waba: str, token: str) -> list[dict]:
    campos = "name,language,status,category,parameter_format,components"
    url = f"{GRAPH}/{waba}/message_templates?fields={campos}&limit=200&access_token={token}"
    out, pagina = [], url
    while pagina:
        d = http(pagina)
        if "error" in d:
            raise RuntimeError(f"WABA {waba}: {d['error'].get('message')}")
        out.extend(d.get("data", []))
        pagina = d.get("paging", {}).get("next")
    return out


def baixar(url: str, destino: Path) -> Path:
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(http(url, raw=True))
    return destino


def subir_handle(caminho: Path, app_id: str, token: str) -> str:
    """Resumable Upload API → handle reutilizável em qualquer WABA do app."""
    tipo = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
    tamanho = caminho.stat().st_size
    q = urllib.parse.urlencode(
        {"file_length": tamanho, "file_type": tipo, "access_token": token}
    )
    sessao = http(f"{GRAPH}/{app_id}/uploads?{q}", method="POST")
    if "id" not in sessao:
        raise RuntimeError(f"sessão de upload falhou: {sessao}")

    r = http(
        f"{GRAPH}/{sessao['id']}",
        data=caminho.read_bytes(),
        headers={
            "Authorization": f"OAuth {token}",
            "file_offset": "0",
            "Content-Type": "application/octet-stream",
        },
        method="POST",
    )
    if "h" not in r:
        raise RuntimeError(f"upload falhou: {r}")
    return r["h"]


def resolver_handles(templates: list[dict], app_id: str, token: str) -> dict[str, str]:
    """Baixa e sobe cada mídia de header uma única vez. url → handle."""
    handles: dict[str, str] = {}
    for t in templates:
        for c in t.get("components", []):
            if c.get("type") != "HEADER" or c.get("format") in (None, "TEXT"):
                continue
            urls = c.get("example", {}).get("header_handle") or []
            if not urls or urls[0] in handles:
                continue
            url = urls[0]
            ext = {"IMAGE": ".jpg", "VIDEO": ".mp4", "DOCUMENT": ".pdf"}.get(
                c["format"], ".bin"
            )
            arq = CACHE_MIDIA / f"{t['name']}_{t['language']}{ext}"
            print(f"  ↓ mídia {c['format']} de {t['name']} → {arq.name}")
            baixar(url, arq)
            handles[url] = subir_handle(arq, app_id, token)
            print(f"  ↑ handle {handles[url][:40]}…")
    return handles


def montar_payload(t: dict, handles: dict[str, str]) -> dict:
    componentes = []
    for c in t.get("components", []):
        c = {k: v for k, v in c.items() if k not in CAMPOS_IGNORADOS}
        if c.get("type") == "HEADER" and c.get("format") not in (None, "TEXT"):
            urls = c.get("example", {}).get("header_handle") or []
            if urls:
                c["example"] = {"header_handle": [handles[urls[0]]]}
        componentes.append(c)

    payload = {
        "name": t["name"],
        "language": CORRIGE_IDIOMA.get(t["name"], t["language"]),
        "category": t["category"],
        "components": componentes,
    }
    if t.get("parameter_format"):
        payload["parameter_format"] = t["parameter_format"]
    return payload


def criar(waba: str, payload: dict, token: str) -> dict:
    return http(
        f"{GRAPH}/{waba}/message_templates",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="não cria nada")
    ap.add_argument("--origem", default=ORIGEM)
    ap.add_argument("--destino", action="append", help="WABA de destino (repetível)")
    ap.add_argument("--template", action="append", help="filtra por nome (repetível)")
    args = ap.parse_args()

    token = os.environ.get("FB_ACCESS_TOKEN")
    app_id = os.environ.get("FB_APP_ID")
    if not token or not app_id:
        print("FB_ACCESS_TOKEN / FB_APP_ID ausentes. `source ~/.claude/.env`")
        return 1

    destinos = {w: DESTINOS.get(w, w) for w in (args.destino or DESTINOS)}

    print(f"Origem: {args.origem}")
    origem = [t for t in listar_templates(args.origem, token) if t["status"] == "APPROVED"]
    if args.template:
        origem = [t for t in origem if t["name"] in args.template]
    print(f"  {len(origem)} templates APPROVED a replicar\n")

    handles: dict[str, str] = {}
    if not args.dry_run:
        print("Reenviando mídias de header:")
        handles = resolver_handles(origem, app_id, token)
        print()

    relatorio = []
    for waba, nome in destinos.items():
        print(f"── {waba}  {nome}")
        try:
            existentes = {(t["name"], t["language"]) for t in listar_templates(waba, token)}
        except RuntimeError as e:
            print(f"   ERRO ao listar: {e}\n")
            relatorio.append({"waba": waba, "erro": str(e)})
            continue

        for t in origem:
            payload = montar_payload(t, handles) if not args.dry_run else montar_payload(
                t, {u: "DRY_RUN_HANDLE" for u in [
                    (c.get("example", {}).get("header_handle") or [None])[0]
                    for c in t.get("components", []) if c.get("type") == "HEADER"
                ] if u}
            )
            chave = (payload["name"], payload["language"])
            if chave in existentes:
                print(f"   = {payload['name']} ({payload['language']}) já existe")
                relatorio.append({"waba": waba, "template": payload["name"], "resultado": "ja_existe"})
                continue
            if args.dry_run:
                print(f"   + {payload['name']} ({payload['language']}) [{payload['category']}]")
                relatorio.append({"waba": waba, "template": payload["name"], "resultado": "dry_run"})
                continue

            r = criar(waba, payload, token)
            if "error" in r:
                msg = r["error"].get("error_user_msg") or r["error"].get("message")
                print(f"   ! {payload['name']}: {msg}")
                relatorio.append({"waba": waba, "template": payload["name"],
                                  "resultado": "erro", "detalhe": msg})
            else:
                print(f"   + {payload['name']} ({payload['language']}) → {r.get('status')} id={r.get('id')}")
                relatorio.append({"waba": waba, "template": payload["name"],
                                  "resultado": "criado", "id": r.get("id"),
                                  "status": r.get("status")})
            time.sleep(1)
        print()

    if not args.dry_run:
        LOGS.mkdir(exist_ok=True)
        alvo = LOGS / f"replicacao_{datetime.now():%Y%m%d_%H%M%S}.json"
        alvo.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2))
        print(f"Log: {alvo.relative_to(RAIZ)}")

    ok = sum(1 for r in relatorio if r.get("resultado") == "criado")
    erros = sum(1 for r in relatorio if r.get("resultado") == "erro")
    print(f"\nCriados: {ok} | Já existiam: "
          f"{sum(1 for r in relatorio if r.get('resultado') == 'ja_existe')} | Erros: {erros}")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())

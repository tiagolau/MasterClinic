#!/usr/bin/env python3
"""Submete templates WABA Master Clinic via Graph API.

Uso:
    python submeter_templates.py [--apenas-sem-video] [--apenas-com-video]

Le templates.json, remove campos _internos, substitui placeholders de video
quando aplicavel, e envia para a Graph API. Resultado vai pra logs/submit_TIMESTAMP.json.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEMPLATES_FILE = ROOT / "templates" / "templates.json"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

WABA_ID = "105152822451126"
GRAPH_VERSION = "v21.0"
ACCESS_TOKEN = os.environ["FB_ACCESS_TOKEN"]

# Handles dos videos depois do upload (preenchidos via env)
HANDLE_VIDEO_RECEPCAO = os.environ.get("HANDLE_VIDEO_RECEPCAO", "")
HANDLE_VIDEO_DR_WILTON = os.environ.get("HANDLE_VIDEO_DR_WILTON", "")


def limpar_template(t: dict) -> dict:
    """Remove campos internos (_id_interno, _esqueleto, etc) e injeta handles."""
    out = {k: v for k, v in t.items() if not k.startswith("_")}
    # substitui placeholders nos handles de video
    for comp in out.get("components", []):
        if comp.get("type") == "HEADER" and comp.get("format") == "VIDEO":
            handles = comp.get("example", {}).get("header_handle", [])
            new_handles = []
            for h in handles:
                if h == "__HANDLE_VIDEO_RECEPCAO__":
                    new_handles.append(HANDLE_VIDEO_RECEPCAO)
                elif h == "__HANDLE_VIDEO_DR_WILTON__":
                    new_handles.append(HANDLE_VIDEO_DR_WILTON)
                else:
                    new_handles.append(h)
            comp["example"]["header_handle"] = new_handles
    return out


def precisa_video(t: dict) -> bool:
    return t.get("_precisa_video", False)


def submeter(template: dict) -> dict:
    """Envia um template para WABA, retorna dict com {ok, status, body}."""
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{WABA_ID}/message_templates"
    payload = limpar_template(template)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return {
                "ok": True,
                "status": resp.status,
                "body": json.loads(body),
                "payload_enviado": payload,
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass
        return {
            "ok": False,
            "status": e.code,
            "body": body,
            "payload_enviado": payload,
        }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "body": {"error": str(e)},
            "payload_enviado": payload,
        }


def main():
    args = sys.argv[1:]
    apenas_sem_video = "--apenas-sem-video" in args
    apenas_com_video = "--apenas-com-video" in args

    with open(TEMPLATES_FILE) as f:
        data = json.load(f)

    resultados = []
    for t in data["templates"]:
        pv = precisa_video(t)
        if apenas_sem_video and pv:
            continue
        if apenas_com_video and not pv:
            continue

        # se precisa video mas nao tem handle, pula
        if pv and not (HANDLE_VIDEO_RECEPCAO and HANDLE_VIDEO_DR_WILTON):
            print(f"[SKIP] {t['name']} — precisa video, handles ausentes")
            continue

        print(f"[ENVIANDO] {t['name']} ({t.get('_esqueleto', '')})")
        r = submeter(t)
        r["template_nome"] = t["name"]
        r["id_interno"] = t.get("_id_interno", "")
        r["esqueleto"] = t.get("_esqueleto", "")
        r["risco"] = t.get("_risco", "")
        resultados.append(r)
        marker = "OK" if r["ok"] else "FAIL"
        print(f"  -> [{marker}] HTTP {r['status']}")
        if not r["ok"]:
            print(f"     body: {json.dumps(r['body'])[:300]}")
        time.sleep(1.5)  # rate limit gentil

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"submit_{ts}.json"
    with open(log_file, "w") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\nResultado salvo em: {log_file}")

    ok = sum(1 for r in resultados if r["ok"])
    fail = sum(1 for r in resultados if not r["ok"])
    print(f"Total: {len(resultados)} | OK: {ok} | FAIL: {fail}")


if __name__ == "__main__":
    main()

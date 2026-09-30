#!/usr/bin/env python3
"""Corrige a tag "Tráfego Pago" no DataCrazy: mantém só nos leads identificados como
Click-to-WhatsApp pela análise das conversas, remove dos demais.

O plano (e o backup do estado anterior) fica em data/limpeza_tag_trafego.json, gerado
pela análise. Este script apenas executa esse plano via MCP Server do DataCrazy.

Uso:
    source ~/.claude/.env
    python3 scripts/limpar_tag_trafego.py --dry-run   # mostra o que faria
    python3 scripts/limpar_tag_trafego.py             # executa

Para reverter: os IDs que tinham a tag antes estão em `com_tag_antes` do mesmo JSON.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib import error, request

MCP = "https://mcp.g1.datacrazy.io/api/mcp"
RAIZ = Path(__file__).resolve().parent.parent
PLANO = RAIZ / "data" / "limpeza_tag_trafego.json"
TOKEN = os.environ.get("DATACRAZY_API_KEY_MASTERCLINIC")
INTERVALO = 2.2  # a API corta em 30 req/min

_seq = [0]


def chamar(tool: str, argumentos: dict, tentativas: int = 5):
    _seq[0] += 1
    corpo = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": _seq[0],
            "method": "tools/call",
            "params": {"name": tool, "arguments": argumentos},
        }
    ).encode()
    req = request.Request(
        MCP,
        data=corpo,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
        },
    )
    for i in range(tentativas):
        try:
            time.sleep(INTERVALO)
            with request.urlopen(req, timeout=60) as r:
                bruto = r.read().decode()
            # transport pode responder em SSE: extrai o objeto JSON
            m = re.search(r"\{.*\}", bruto, re.S)
            d = json.loads(m.group(0)) if m else {}
            if d.get("error"):
                return False, str(d["error"])[:160]
            return True, ""
        except error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and i < tentativas - 1:
                time.sleep(65 if e.code == 429 else 10)
                continue
            return False, f"HTTP {e.code}: {e.read().decode()[:120]}"
        except Exception as e:  # timeout, conexão
            if i < tentativas - 1:
                time.sleep(10)
                continue
            return False, str(e)[:120]
    return False, "esgotou tentativas"


def ler_lead(lead_id: str):
    """GET REST do lead, para conferir se a escrita via MCP pegou de fato."""
    req = request.Request(
        f"https://api.g1.datacrazy.io/api/v1/leads/{lead_id}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
        },
    )
    try:
        time.sleep(INTERVALO)
        with request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
        return d.get("data", d)
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not TOKEN:
        sys.exit("Defina DATACRAZY_API_KEY_MASTERCLINIC")
    if not PLANO.exists():
        sys.exit(f"Rode a análise primeiro — {PLANO} não existe")

    plano = json.loads(PLANO.read_text())
    tag = plano["tag"]
    adicionar, remover = plano["adicionar"], plano["remover"]

    print(f"tag Tráfego Pago: {tag}")
    print(f"  adicionar em {len(adicionar)} leads (CTWA sem a tag)")
    print(f"  remover de  {len(remover)} leads (tag indevida)")
    print(f"  backup do estado anterior: {PLANO}")
    if args.dry_run:
        print("\n[dry-run] nada foi alterado")
        return

    total = len(adicionar) + len(remover)
    minutos = total * INTERVALO / 60
    print(f"\nexecutando {total} operações (~{minutos:.0f} min pelo rate limit)…\n")

    falhas = []
    # ⚠️ o schema das tools é {id, tagIds} com tagIds em STRING separada por vírgula.
    # Passar {leadId, tagIds: [...]} retorna sucesso e não faz nada — falha silenciosa.
    for n, lid in enumerate(adicionar, 1):
        ok, err = chamar("lead_add_tag", {"id": lid, "tagIds": tag})
        if not ok:
            falhas.append(("add", lid, err))
        print(f"  add {n}/{len(adicionar)}", end="\r")
    print(f"  add: {len(adicionar)} processados" + " " * 20)

    for n, lid in enumerate(remover, 1):
        ok, err = chamar("lead_remove_tag", {"id": lid, "tagIds": tag})
        if not ok:
            falhas.append(("rem", lid, err))
        if n % 25 == 0:
            print(f"  remove {n}/{len(remover)}…")
    print(f"  remove: {len(remover)} processados")

    # confere na API se a escrita realmente pegou — o MCP já respondeu sucesso sem
    # aplicar nada quando o schema estava errado
    print("\nverificando uma amostra…")
    amostra = (remover[:3] + adicionar[:2]) or remover[:5]
    for lid in amostra:
        d = ler_lead(lid)
        tem = any(t.get("id") == tag for t in (d.get("tags") or []))
        esperado = lid in adicionar
        marca = "✓" if tem == esperado else "✗ NÃO APLICOU"
        print(f"  {lid[:8]} tem_tag={tem} esperado={esperado} {marca}")

    if falhas:
        print(f"\n⚠️  {len(falhas)} falhas:")
        for op, lid, err in falhas[:10]:
            print(f"   {op} {lid}: {err}")
        (RAIZ / "data" / "limpeza_falhas.json").write_text(
            json.dumps(falhas, ensure_ascii=False, indent=2)
        )
    else:
        print("\n✓ concluído sem falhas")


if __name__ == "__main__":
    main()

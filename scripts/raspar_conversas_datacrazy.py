#!/usr/bin/env python3
"""Raspa conversas, mensagens e leads do DataCrazy (tenant Master Clinic).

Uso:
    source ~/.claude/.env
    python3 scripts/raspar_conversas_datacrazy.py            # tudo
    python3 scripts/raspar_conversas_datacrazy.py --limite 200

Saída (diretório data/):
    instances.json          números/canais conectados
    conversations.json      lista de conversas (metadados)
    leads.json              leads com source / sourceReferral (origem de tráfego)
    messages/<conv_id>.json mensagens de cada conversa
"""
import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import error, request

BASE = "https://api.g1.datacrazy.io/api/v1"
RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
MSGS = DATA / "messages"

TOKEN = os.environ.get("DATACRAZY_API_KEY_MASTERCLINIC") or os.environ.get(
    "DATACRAZY_TOKEN"
)


# a API corta em 30 requisições/minuto (429); o throttle abaixo mantém abaixo disso
INTERVALO = 2.2
_trava = threading.Lock()
_ultima = [0.0]


def _aguardar_vez():
    with _trava:
        espera = INTERVALO - (time.monotonic() - _ultima[0])
        if espera > 0:
            time.sleep(espera)
        _ultima[0] = time.monotonic()


def get(caminho: str, tentativas: int = 6):
    url = f"{BASE}/{caminho.lstrip('/')}"
    req = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            # sem User-Agent de browser o Cloudflare do DataCrazy devolve 403/1010
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Accept": "application/json",
        },
    )
    for i in range(tentativas):
        try:
            _aguardar_vez()
            with request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except error.HTTPError as e:
            corpo = e.read().decode()[:200]
            if e.code in (429, 502, 503, 504) and i < tentativas - 1:
                # 429: a janela é de 1 min, então espera a janela inteira
                time.sleep(65 if e.code == 429 else min(30, 3 * 2**i))
                continue
            raise RuntimeError(f"HTTP {e.code} em {url}: {corpo}")
        except Exception:
            if i < tentativas - 1:
                time.sleep(min(60, 3 * 2**i))
                continue
            raise
    return None


def paginar(recurso: str, take: int = 1000):
    """A API ignora limit/page/offset; pagina com take (máx 1000) + skip."""
    itens, skip = [], 0
    while True:
        sep = "&" if "?" in recurso else "?"
        d = get(f"{recurso}{sep}take={take}&skip={skip}")
        lote = d.get("data", [])
        itens.extend(lote)
        if len(lote) < take:
            break
        skip += take
    return {"count": len(itens), "data": itens}


def salvar(nome: str, obj):
    caminho = DATA / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return caminho


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0, help="máx. de conversas a baixar")
    ap.add_argument("--workers", type=int, default=2, help="o throttle global manda; 2 basta")
    ap.add_argument("--forcar", action="store_true", help="rebaixa mensagens já salvas")
    args = ap.parse_args()

    if not TOKEN:
        sys.exit(
            "Defina DATACRAZY_API_KEY_MASTERCLINIC (token do tenant Master Clinic).\n"
            "Obtenha em crm.datacrazy.io/config/api logado na conta da Master Clinic."
        )

    MSGS.mkdir(parents=True, exist_ok=True)

    print("→ instâncias (números conectados)…")
    inst = get("instances")
    salvar("instances.json", inst)
    for i in inst.get("data", []):
        cfg = i.get("config") or {}
        numero = cfg.get("phone") or cfg.get("number") or cfg.get("phoneNumber") or "?"
        print(f"   [{i.get('platform')}/{i.get('provider')}] {i.get('name')} — {numero}")

    print("→ leads (source / sourceReferral)…")
    # a API ignora limit/page/offset; só `take` funciona (default 100)
    leads = paginar("leads")
    salvar("leads.json", leads)
    print(f"   {len(leads.get('data', []))} leads")

    print("→ conversas…")
    convs = paginar("conversations")
    salvar("conversations.json", convs)
    lista = convs.get("data", [])
    if args.limite:
        lista = lista[: args.limite]
    print(f"   {len(lista)} conversas a processar")

    pendentes = [
        c for c in lista if args.forcar or not (MSGS / f"{c['id']}.json").exists()
    ]
    print(f"   {len(pendentes)} sem mensagens baixadas")

    def baixar(conv):
        d = get(f"conversations/{conv['id']}/messages")
        (MSGS / f"{conv['id']}.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2)
        )
        return conv["id"], len(d.get("messages", []))

    ok = falhas = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(baixar, c): c for c in pendentes}
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                fut.result()
                ok += 1
            except Exception as e:
                falhas += 1
                print(f"   falha em {futs[fut]['id']}: {e}")
            if n % 25 == 0:
                print(f"   {n}/{len(pendentes)}…")

    print(f"✓ {ok} conversas baixadas, {falhas} falhas → {MSGS}")


if __name__ == "__main__":
    main()

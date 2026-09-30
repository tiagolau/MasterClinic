#!/usr/bin/env python3
"""Sincroniza pacientes do Clinicorp ausentes no DataCrazy.

Cria os leads no DataCrazy via MCP (lead_create) com tags 'Clinicorp' e 'Paciente Ativo'.
Possui throttle de 2.2s para respeitar o limite de 30 req/min e persistência de progresso
para ser totalmente idempotente e retomável.

Uso:
    python3 scripts/sincronizar_clinicorp_datacrazy.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INPUT_FILE = RAIZ / "data" / "pacientes_para_sincronizar.json"
PROGRESS_FILE = RAIZ / "logs" / "sincronizacao_clinicorp_datacrazy.json"

# Tags: Clinicorp (ffbd0c5a-f63b-4c66-855a-99181c529a5f) e Paciente Ativo (db602517-ba04-49fc-be48-30b1100aa7ba)
TAGS = "ffbd0c5a-f63b-4c66-855a-99181c529a5f,db602517-ba04-49fc-be48-30b1100aa7ba"
MCP_URL = "https://mcp.g1.datacrazy.io/api/mcp"
INTERVALO = 2.2  # segundos entre chamadas (mantém ~27 req/min)

# Carrega token do ambiente
env_path = Path.home() / ".claude" / ".env"
token = os.environ.get("DATACRAZY_API_KEY_MASTERCLINIC") or os.environ.get("DATACRAZY_TOKEN")
if not token and env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("DATACRAZY_API_KEY_MASTERCLINIC="):
            token = line.split("=", 1)[1].strip("\"'")

if not token:
    print("ERRO: Token DATACRAZY_API_KEY_MASTERCLINIC não encontrado!")
    sys.exit(1)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


def chamar_mcp(metodo: str, params: dict, tentativas: int = 5) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 1000000,
        "method": "tools/call",
        "params": {
            "name": metodo,
            "arguments": params,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": UA,
            "Accept": "application/json",
        },
    )

    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if "error" in res:
                    return {"success": False, "error": res["error"]}
                text = res.get("result", {}).get("content", [{}])[0].get("text", "{}")
                return {"success": True, "data": json.loads(text) if text else {}}
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", errors="ignore")
            if e.code == 429:
                espera = 65
                print(f"\n[429 Rate Limit] Aguardando {espera}s antes de tentar novamente...")
                time.sleep(espera)
                continue
            if e.code in (502, 503, 504) and i < tentativas - 1:
                time.sleep(5 * (i + 1))
                continue
            return {"success": False, "error": f"HTTP {e.code}: {corpo}"}
        except Exception as e:
            if i < tentativas - 1:
                time.sleep(3 * (i + 1))
                continue
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "Excedeu número de tentativas"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sincroniza pacientes Clinicorp -> DataCrazy")
    parser.add_argument("--limite", type=int, default=0, help="Limita o numero de pacientes para teste")
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        print(f"ERRO: Arquivo {INPUT_FILE} não encontrado!")
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        pacientes = json.load(f)

    if args.limite > 0:
        pacientes = pacientes[:args.limite]

    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    progresso = {}
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progresso = json.load(f)
        except Exception:
            progresso = {}

    total = len(pacientes)
    print(f"Iniciando sincronização de {total} pacientes para o DataCrazy...")
    print(f"Já processados anteriormente: {len(progresso)}")

    criados = 0
    falhas = 0
    pulados = 0

    for idx, p in enumerate(pacientes, 1):
        cid = str(p.get("clinicorp_id"))
        phone = p.get("phone")
        name = p.get("name")
        email = p.get("email")

        # Verifica se já foi sincronizado
        if cid in progresso and progresso[cid].get("status") == "criado":
            pulados += 1
            continue

        params = {
            "name": name,
            "phone": phone,
            "tags": TAGS,
        }
        if email:
            params["email"] = email

        res = chamar_mcp("lead_create", params)

        if res.get("success"):
            lead_data = res.get("data", {})
            lead_id = lead_data.get("id")
            progresso[cid] = {
                "status": "criado",
                "lead_id": lead_id,
                "name": name,
                "phone": phone,
                "email": email,
                "timestamp": time.time(),
            }
            criados += 1
            print(f"[{idx}/{total}] SUCESSO: {name} ({phone}) -> Lead ID: {lead_id}")
        else:
            erro = res.get("error")
            progresso[cid] = {
                "status": "erro",
                "name": name,
                "phone": phone,
                "error": str(erro),
                "timestamp": time.time(),
            }
            falhas += 1
            print(f"[{idx}/{total}] ERRO: {name} ({phone}) -> {erro}")

        # Salva o progresso a cada item para resiliência total
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progresso, f, indent=2, ensure_ascii=False)

        time.sleep(INTERVALO)

    print("\n=== RESUMO DA SINCRONIZAÇÃO ===")
    print(f"Total analisados: {total}")
    print(f"Criados nesta execução: {criados}")
    print(f"Já existiam/processados: {pulados}")
    print(f"Falhas: {falhas}")
    print(f"Log salvo em: {PROGRESS_FILE}")


if __name__ == "__main__":
    main()

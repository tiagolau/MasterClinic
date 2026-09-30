#!/usr/bin/env python3
"""Exporta transcrições legíveis das conversas raspadas, filtrando por origem/intenção.

Uso:
    python3 scripts/exportar_transcricoes.py --trafego --n 30
    python3 scripts/exportar_transcricoes.py --trafego --procedimento --n 20 --saida data/transcricoes.txt
"""
import argparse
import json
import re
from pathlib import Path

import analisar_conversas as A  # reaproveita classificação e dicionários

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trafego", action="store_true", help="só leads de tráfego pago")
    ap.add_argument("--procedimento", action="store_true", help="só quem citou tratamento")
    ap.add_argument("--canal", help="filtra por nome da instância")
    ap.add_argument("--assunto", help="paciente | vaga | fornecedor")
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--min-msgs", type=int, default=4)
    ap.add_argument("--saida", default="")
    args = ap.parse_args()

    convs, leads, inst = A.carregar()
    linhas = []
    n = 0
    for c in convs:
        if n >= args.n:
            break
        msgs = A.mensagens(c["id"])
        if len(msgs) < args.min_msgs:
            continue
        contato = c.get("contact") or {}
        fone = re.sub(r"\D", "", contato.get("phoneNumber") or contato.get("contactId") or "")
        lead = leads.get(contato.get("externalId")) or leads.get(fone)
        cls = A.classificar(c, msgs, lead)
        canal = (c.get("instance") or {}).get("name")
        if args.trafego and cls["origem"] != "trafego":
            continue
        if args.procedimento and not cls["procedimentos_citados_pelo_lead"]:
            continue
        if args.canal and args.canal.lower() not in (canal or "").lower():
            continue
        if args.assunto and cls["assunto"] != args.assunto:
            continue
        n += 1
        linhas.append("=" * 78)
        linhas.append(
            f"[{n}] {c.get('name')} | canal: {canal} | origem: {cls['origem']} "
            f"({cls['evidencia_origem']}) | procs: {cls['procedimentos_citados_pelo_lead']}"
        )
        linhas.append(f"    início: {c.get('createdAt')} | msgs: {len(msgs)}")
        for m in msgs:
            quem = "LEAD    " if m.get("received") else "CLÍNICA "
            corpo = (m.get("body") or "").replace("\n", " ⏎ ").strip()
            anexos = m.get("attachments") or []
            if not corpo and anexos:
                tipos = ",".join(str(a.get("type") or a.get("mimeType")) for a in anexos)
                corpo = f"<mídia: {tipos}>"
            if not corpo:
                continue
            hora = (m.get("createdAt") or "")[5:16].replace("T", " ")
            linhas.append(f"  {hora} {quem}| {corpo[:600]}")
        linhas.append("")

    texto = "\n".join(linhas)
    if args.saida:
        Path(args.saida).write_text(texto)
        print(f"{n} conversas → {args.saida}")
    else:
        print(texto)


if __name__ == "__main__":
    main()

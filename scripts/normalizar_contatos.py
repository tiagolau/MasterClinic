#!/usr/bin/env python3
"""Normaliza números de telefone do CSV exportado do Cloudia para importação no DataCrazy.

Regras:
- 8 dígitos (fixo sem DDD): adiciona prefixo 31
- 9 dígitos (celular sem DDD): adiciona prefixo 31
- Demais comprimentos: mantém como está
"""

import csv
import sys
import re
from pathlib import Path


def normalizar_telefone(raw: str, ddd_padrao: str = "31") -> str:
    digitos = re.sub(r"\D", "", raw)

    if len(digitos) in (8, 9):
        return ddd_padrao + digitos

    return digitos if digitos else raw


def main():
    entrada = Path("/Users/tiagolau/Devs/MasterClinic/contatos_filtrados.csv")
    saida = Path("/Users/tiagolau/Devs/MasterClinic/contatos_importacao.csv")

    contadores = {"8": 0, "9": 0, "outros": 0}

    with entrada.open(encoding="utf-8") as fin, saida.open("w", encoding="utf-8", newline="") as fout:
        reader = csv.reader(fin, delimiter=";")
        writer = csv.writer(fout, delimiter=";", quoting=csv.QUOTE_ALL)

        header = next(reader)
        writer.writerow(header)

        idx_tel = header.index("Telefone")

        for row in reader:
            if len(row) <= idx_tel:
                writer.writerow(row)
                continue

            original = row[idx_tel]
            digitos = re.sub(r"\D", "", original)
            n = len(digitos)

            if n == 8:
                row[idx_tel] = "31" + digitos
                contadores["8"] += 1
            elif n == 9:
                row[idx_tel] = "31" + digitos
                contadores["9"] += 1
            else:
                contadores["outros"] += 1

            writer.writerow(row)

    total_norm = contadores["8"] + contadores["9"]
    print(f"Arquivo gerado: {saida}")
    print(f"  Fixos normalizados (8 dígitos → +31): {contadores['8']}")
    print(f"  Celulares normalizados (9 dígitos → +31): {contadores['9']}")
    print(f"  Mantidos sem alteração: {contadores['outros']}")
    print(f"  Total normalizados: {total_norm}")


if __name__ == "__main__":
    main()

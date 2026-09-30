"""Importa a raspagem local (data/) como carga inicial — evita re-raspar ~1h de API.

Uso:
    python -m app.seed /caminho/para/MasterClinic/data
"""
import json
import logging
import sys
from pathlib import Path

from . import db
from .sync_datacrazy import (
    _linha_conversa,
    _linha_lead,
    _sync_mensagens_local,
    _upsert_instancias,
)

log = logging.getLogger("painel.seed")


def main(pasta: str):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    data = Path(pasta)
    db.iniciar()

    inst = json.loads((data / "instances.json").read_text()).get("data", [])
    _upsert_instancias(inst)
    log.info("instâncias: %d", len(inst))

    leads = json.loads((data / "leads.json").read_text()).get("data", [])
    db.upsert("leads", [_linha_lead(l) for l in leads])
    log.info("leads: %d", len(leads))

    convs = json.loads((data / "conversations.json").read_text()).get("data", [])
    db.upsert("conversas", [_linha_conversa(c) for c in convs])
    log.info("conversas: %d", len(convs))

    msgs_dir = data / "messages"
    n = 0
    for arq in sorted(msgs_dir.glob("*.json")):
        conv_id = arq.stem
        try:
            d = json.loads(arq.read_text())
            msgs = d.get("messages", []) if isinstance(d, dict) else []
            _sync_mensagens_local(conv_id, msgs)
            n += 1
            if n % 200 == 0:
                log.info("mensagens: %d conversas processadas…", n)
        except Exception as e:
            log.warning("falha em %s: %s", conv_id, e)
    log.info("seed concluído: %d conversas com mensagens", n)
    db.pool.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: python -m app.seed /caminho/para/data")
    main(sys.argv[1])

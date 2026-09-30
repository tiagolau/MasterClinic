"""Cliente REST do DataCrazy com throttle global (30 req/min) e retries.

Peculiaridades do tenant (ver CLAUDE.md e ADR 004 do projeto):
- Cloudflare devolve 403/1010 sem User-Agent de browser
- 429 quando passa de 30 req/min; janela de 1 minuto
- paginação só funciona com take (máx 1000) + skip
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request

from . import config

log = logging.getLogger("painel.datacrazy")

# 2.2s entre requisições mantém ~27 req/min, abaixo do corte
_INTERVALO = 2.2
_trava = threading.Lock()
_ultima = [0.0]

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


def _aguardar_vez():
    with _trava:
        espera = _INTERVALO - (time.monotonic() - _ultima[0])
        if espera > 0:
            time.sleep(espera)
        _ultima[0] = time.monotonic()


def get(caminho: str, tentativas: int = 6):
    url = f"{config.DATACRAZY_BASE}/{caminho.lstrip('/')}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {config.DATACRAZY_TOKEN}",
            "User-Agent": _UA,
            "Accept": "application/json",
        },
    )
    for i in range(tentativas):
        try:
            _aguardar_vez()
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            corpo = e.read().decode()[:200]
            if e.code in (429, 502, 503, 504) and i < tentativas - 1:
                time.sleep(65 if e.code == 429 else min(30, 3 * 2**i))
                continue
            raise RuntimeError(f"HTTP {e.code} em {url}: {corpo}")
        except Exception:
            if i < tentativas - 1:
                time.sleep(min(60, 3 * 2**i))
                continue
            raise
    return None


def paginar(recurso: str, take: int = 1000, max_paginas: int = 0):
    """Baixa todas as páginas (ou até max_paginas) de um recurso."""
    itens, skip, paginas = [], 0, 0
    while True:
        sep = "&" if "?" in recurso else "?"
        d = get(f"{recurso}{sep}take={take}&skip={skip}")
        lote = d.get("data", [])
        itens.extend(lote)
        paginas += 1
        if len(lote) < take or (max_paginas and paginas >= max_paginas):
            break
        skip += take
    return itens


def paginar_ate(recurso: str, parar_quando, take: int = 200):
    """Pagina uma lista ordenada desc e para quando `parar_quando(item)` é True.

    Devolve só os itens anteriores ao corte. Usado no sync incremental:
    conversas/negócios vêm ordenados do mais recente para o mais antigo.
    """
    itens, skip = [], 0
    while True:
        sep = "&" if "?" in recurso else "?"
        d = get(f"{recurso}{sep}take={take}&skip={skip}")
        lote = d.get("data", [])
        for item in lote:
            if parar_quando(item):
                return itens
            itens.append(item)
        if len(lote) < take:
            return itens
        skip += take

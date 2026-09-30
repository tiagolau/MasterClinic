"""Envio de mensagens via uazapi (masterclinic.uazapi.com).

Auth: header `token: <token da instância>`. Doc: docs.uazapi.com.
"""
import json
import urllib.request

from . import config


def enviar_texto(numero: str, texto: str):
    corpo = {"number": numero, "text": texto}
    req = urllib.request.Request(
        f"{config.UAZAPI_URL.rstrip('/')}/send/text",
        data=json.dumps(corpo).encode(),
        headers={"token": config.UAZAPI_TOKEN, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

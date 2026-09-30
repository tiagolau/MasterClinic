"""Sessão por cookie assinado (HMAC) — simples e sem dependências extras."""
import base64
import hashlib
import hmac
import time

from . import config

COOKIE = "painel_sess"
VALIDADE_S = 30 * 24 * 3600  # 30 dias


def _assinar(msg: str) -> str:
    return hmac.new(config.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()


def emitir_token() -> str:
    exp = str(int(time.time()) + VALIDADE_S)
    exp_b64 = base64.urlsafe_b64encode(exp.encode()).decode()
    return f"{exp_b64}.{_assinar(exp)}"


def validar_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp_b64, assinatura = token.rsplit(".", 1)
    try:
        exp = base64.urlsafe_b64decode(exp_b64.encode()).decode()
    except Exception:
        return False
    if not hmac.compare_digest(_assinar(exp), assinatura):
        return False
    return int(exp) > time.time()

"""Pool Postgres (psycopg 3) + helpers de query e upsert."""
import json
import logging
from pathlib import Path

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from . import config

log = logging.getLogger("painel.db")

pool = ConnectionPool(
    config.DATABASE_URL,
    min_size=1,
    max_size=8,
    kwargs={"row_factory": dict_row, "autocommit": True},
    open=False,
)


def iniciar():
    pool.open(wait=True, timeout=60)
    schema = (Path(__file__).parent.parent / "schema.sql").read_text()
    with pool.connection() as conn:
        conn.execute(schema)
    log.info("schema aplicado")


def q(query: str, params=None):
    """SELECT → lista de dicts."""
    with pool.connection() as conn:
        return conn.execute(query, params or ()).fetchall()


def q1(query: str, params=None):
    with pool.connection() as conn:
        return conn.execute(query, params or ()).fetchone()


def ex(query: str, params=None):
    with pool.connection() as conn:
        conn.execute(query, params or ())


def upsert(tabela: str, linhas: list[dict], conflito: str | tuple = "id"):
    """UPSERT em lote. Colunas = chaves do primeiro dict; dicts/listas viram jsonb."""
    if not linhas:
        return 0
    if isinstance(conflito, str):
        conflito = (conflito,)
    cols = list(linhas[0].keys())
    atualizaveis = [c for c in cols if c not in conflito]

    def adaptar(v):
        return Jsonb(v) if isinstance(v, (dict, list)) else v

    query = sql.SQL(
        "INSERT INTO {t} ({cols}) VALUES ({vals}) ON CONFLICT ({conf}) DO UPDATE SET {sets}"
    ).format(
        t=sql.Identifier(tabela),
        cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
        vals=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
        conf=sql.SQL(", ").join(map(sql.Identifier, conflito)),
        sets=sql.SQL(", ").join(
            sql.SQL("{c} = EXCLUDED.{c}").format(c=sql.Identifier(c))
            for c in atualizaveis
        )
        or sql.SQL("id = EXCLUDED.id"),
    )
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, [[adaptar(l[c]) for c in cols] for l in linhas])
    return len(linhas)


def estado_get(chave: str, padrao=None):
    row = q1("SELECT valor FROM sync_state WHERE chave = %s", (chave,))
    return row["valor"] if row else padrao


def estado_set(chave: str, valor):
    ex(
        """INSERT INTO sync_state (chave, valor, atualizado_em) VALUES (%s, %s, now())
           ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, atualizado_em = now()""",
        (chave, Jsonb(valor)),
    )

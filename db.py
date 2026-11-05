# Small helper functions for MySQL.
# I did not use an ORM because this class is about writing the SQL by hand.
from __future__ import annotations

import mysql.connector
from mysql.connector import pooling
from flask import g

_pool: pooling.MySQLConnectionPool | None = None


def init_pool(app):
    global _pool
    _pool = pooling.MySQLConnectionPool(
        pool_name="cs2mp_pool",
        pool_size=5,
        **app.config["DB"],
    )
    # give the connection back after every request, even if the route crashed
    app.teardown_appcontext(close_db)


def get_db():
    # Saved on g so the whole request uses the same connection.
    if "db" not in g:
        g.db = _pool.get_connection()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()  # this gives it back to the pool, it does not really close it


def query_all(sql, params=None):
    cur = get_db().cursor(dictionary=True)
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close()
    return rows


def query_one(sql, params=None):
    cur = get_db().cursor(dictionary=True)
    cur.execute(sql, params or ())
    row = cur.fetchone()
    cur.close()
    return row


def execute(sql, params=None):
    # Commits right away. If more than one table has to change, use run_txn.
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    rid = cur.lastrowid
    cur.close()
    return rid


def run_txn(fn):
    # Runs fn inside one transaction. If anything fails we roll back, so the
    # tables never end up half updated. I use this for buy, rent and return.
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        result = fn(cur)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
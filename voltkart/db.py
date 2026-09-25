import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from psycopg2 import pool

load_dotenv()

_pool = pool.ThreadedConnectionPool(
    1,
    10,
    host=os.getenv("PGHOST", "localhost"),
    port=os.getenv("PGPORT", "5432"),
    user=os.getenv("PGUSER", "postgres"),
    password=os.getenv("PGPASSWORD", ""),
    dbname=os.getenv("PGDATABASE", "voltkart"),
)


@contextmanager
def get_conn(autocommit=True):
    conn = _pool.getconn()
    conn.autocommit = autocommit
    try:
        yield conn
    finally:
        conn.autocommit = True
        _pool.putconn(conn)


@contextmanager
def get_cursor(autocommit=True):
    with get_conn(autocommit=autocommit) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield conn, cur

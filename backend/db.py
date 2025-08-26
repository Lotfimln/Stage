import os
import oracledb
from contextlib import contextmanager

oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_21_13\instantclient_19_28")

DSN  = os.getenv('ORA_DSN', '127.0.0.1:1521/xe')
USER = os.getenv('ORA_USER')
PWD  = os.getenv('ORA_PASSWORD')

def get_conn():
    return oracledb.connect(user=USER, password=PWD, dsn=DSN)

@contextmanager
def cursor():
    con = get_conn()
    cur = con.cursor()
    try:
        yield cur
        con.commit()
    finally:
        cur.close()
        con.close()

def fetch_all(sql, binds):
    with cursor() as cur:
        cur.execute(sql, binds)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

def fetch_one(sql, binds):
    with cursor() as cur:
        cur.execute(sql, binds)
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0].lower() for c in cur.description]
        return dict(zip(cols, row))

def execute(sql, binds):
    with cursor() as cur:
        cur.execute(sql, binds)

    

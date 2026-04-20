# -*- coding: utf-8 -*-
"""
db.py - SQLite database access layer for CSR prototype.
Drop-in replacement for the Oracle-based version.
Same API: fetch_all(), fetch_one(), execute()

Auto-rebuild: on import, checks that the DB file exists and contains
all expected tables.  If anything is missing the database is rebuilt
automatically via init_db.main().
"""
import os
import sqlite3
from contextlib import contextmanager

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH  = os.getenv("CSR_DB_PATH", os.path.join(DATA_DIR, "csr.db"))

# ── Schema version tracking ──────────────────────────────────────────
# We compare the version stored in DB_META against init_db.SCHEMA_VERSION.
# Any mismatch (or missing DB / table) triggers a full rebuild.


def _db_schema_version():
    """Return the schema_version string stored in the DB, or None."""
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        # Check if DB_META table exists
        has_meta = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='DB_META'"
        ).fetchone()
        if not has_meta:
            conn.close()
            return None
        row = conn.execute(
            "SELECT value FROM DB_META WHERE key='schema_version'"
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def _ensure_db():
    """Rebuild the database if it is missing or its schema version is outdated."""
    # Import here to read SCHEMA_VERSION without circular issues
    import init_db

    current = _db_schema_version()
    expected = init_db.SCHEMA_VERSION

    if current == expected:
        return  # all good

    if current is None:
        print(f"\n  [db.py] Base absente ou sans version — reconstruction...")
    else:
        print(f"\n  [db.py] Version schéma obsolète ({current} → {expected}) — reconstruction...")

    init_db.main()
    print("  [db.py] Base reconstruite avec succès !\n")


# ── Run the check once at import time ────────────────────────────────
_ensure_db()


def get_conn():
    """Get a new SQLite connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def cursor():
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _convert_named_binds(sql, binds):
    """Convert Oracle-style :name binds to SQLite-style :name binds.

    SQLite supports :name natively, but we need to handle a few edge cases:
    - Oracle uses :name, SQLite also uses :name (compatible)
    - We just need to ensure the binds dict keys match
    """
    if isinstance(binds, dict):
        return sql, binds
    return sql, binds


def fetch_all(sql, binds):
    """Execute query and return all rows as list of dicts."""
    sql, binds = _convert_named_binds(sql, binds)
    with cursor() as cur:
        cur.execute(sql, binds)
        cols = [desc[0].lower() for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_one(sql, binds):
    """Execute query and return first row as dict, or None."""
    sql, binds = _convert_named_binds(sql, binds)
    with cursor() as cur:
        cur.execute(sql, binds)
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0].lower() for desc in cur.description]
        return dict(zip(cols, row))


def execute(sql, binds):
    """Execute a write query (INSERT/UPDATE/DELETE)."""
    sql, binds = _convert_named_binds(sql, binds)
    with cursor() as cur:
        cur.execute(sql, binds)

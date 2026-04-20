# -*- coding: utf-8 -*-
"""
init_db.py - Import CSV data into SQLite database for CSR prototype.
Creates tables PERSONNE, THEMES, POSITIONNEMENT and loads data from CSV files.
"""
import csv
import os
import sqlite3
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH  = os.path.join(DATA_DIR, "csr.db")

# ──────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────
SCHEMA = """
-- Themes hierarchy
CREATE TABLE IF NOT EXISTS THEMES (
    "CS_TH_COD#"   INTEGER PRIMARY KEY,
    THEME          TEXT NOT NULL,
    NIVEAU         INTEGER DEFAULT 0,
    THEME_PARENT   INTEGER,
    FOREIGN KEY (THEME_PARENT) REFERENCES THEMES("CS_TH_COD#")
);
CREATE INDEX IF NOT EXISTS idx_themes_parent ON THEMES(THEME_PARENT);
CREATE INDEX IF NOT EXISTS idx_themes_label  ON THEMES(THEME);

-- Persons
CREATE TABLE IF NOT EXISTS PERSONNE (
    "PE_PE_COD#"   INTEGER PRIMARY KEY,
    PE_PE_NOM      TEXT NOT NULL,
    PE_PE_PRENOM   TEXT
);
CREATE INDEX IF NOT EXISTS idx_personne_nom ON PERSONNE(PE_PE_NOM);

-- Positioning (theme-person-structure assignments)
CREATE TABLE IF NOT EXISTS POSITIONNEMENT (
    ROWID_POS          INTEGER PRIMARY KEY AUTOINCREMENT,
    IDPERS             INTEGER NOT NULL,
    IDCONTRIBUTION     INTEGER,
    LIBCONTRIBUTION    TEXT,
    IDTEMPORALITE      INTEGER,
    LIBELLETEMPORALITE TEXT,
    IDTHEME            INTEGER NOT NULL,
    LIBELLETHEME       TEXT,
    IDSTRUCTURE        INTEGER,
    LIBELLESTRUCTURE   TEXT,
    IDTYPESTRUCTURE    INTEGER,
    LIBELLETYPESTRUCTURE TEXT,
    IDSTRUCTUREPARENTE  INTEGER,
    LIBELLESTRUCTUREPARENTE TEXT,
    AUTO_GENERE        TEXT DEFAULT NULL,
    FOREIGN KEY (IDPERS)  REFERENCES PERSONNE("PE_PE_COD#"),
    FOREIGN KEY (IDTHEME) REFERENCES THEMES("CS_TH_COD#")
);
CREATE INDEX IF NOT EXISTS idx_pos_pers      ON POSITIONNEMENT(IDPERS);
CREATE INDEX IF NOT EXISTS idx_pos_theme     ON POSITIONNEMENT(IDTHEME);
CREATE INDEX IF NOT EXISTS idx_pos_struct    ON POSITIONNEMENT(IDSTRUCTURE);
CREATE INDEX IF NOT EXISTS idx_pos_temp      ON POSITIONNEMENT(LIBELLETEMPORALITE);
CREATE INDEX IF NOT EXISTS idx_pos_contrib   ON POSITIONNEMENT(LIBCONTRIBUTION);
CREATE INDEX IF NOT EXISTS idx_pos_auto      ON POSITIONNEMENT(AUTO_GENERE);

-- Users for authentication
CREATE TABLE IF NOT EXISTS USERS (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role     TEXT NOT NULL DEFAULT 'admin'
);

-- Structures reference table (acronyms for display)
CREATE TABLE IF NOT EXISTS STRUCTURES (
    id        INTEGER PRIMARY KEY,
    libelle   TEXT NOT NULL,
    acronyme  TEXT NOT NULL,
    type_structure TEXT DEFAULT 'Equipe'
);
CREATE INDEX IF NOT EXISTS idx_struct_acronyme ON STRUCTURES(acronyme);

-- Schema version tracking (for auto-rebuild detection)
CREATE TABLE IF NOT EXISTS DB_META (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Bump this version whenever the schema or seed data changes.
# db.py compares this against the DB to decide if a rebuild is needed.
SCHEMA_VERSION = "8"

# ── Structure acronym mapping ──────────────────────────────────────
STRUCTURE_ACRONYMS = {
    2:     ("Signal et Communication",                                                         "SC"),
    3:     ("Structuration, Analyse et MOdélisation de documents Vidéo et Audio",               "SAMOVA"),
    7:     ("Systèmes d'Informations Généralisés",                                             "SIG"),
    8:     ("Optimisation dynamique de requêtes réparties à grande échelle",                    "ODRGE"),
    10:    ("Systèmes MultiAgents Coopératifs",                                                 "SMAC"),
    11:    ("MEthodes et ingénierie des Langues, des Ontologies et du DIscours",                "MELODI"),
    16:    ("Logique, Interaction, Langue et Calcul",                                           "LILAC"),
    17:    ("Argumentation, Décision, Raisonnement, Incertitude et Apprentissage",              "ADRIA"),
    18:    ("Algorithmes Parallèles et Optimisation",                                           "APO"),
    23:    ("Réseaux, Mobiles, EmBarqués, Sans fil, Satellites",                                "RMESS"),
    24:    ("Service IntEgration and netwoRk Administration",                                   "SIERA"),
    30:    ("IRIT Général",                                                                     "IRIT"),
    31:    ("Système d'Exploitation, systèmes réPartis, de l'Intergiciel à l'Architecture",     "SEPIA"),
    32:    ("groupe de Recherche en Architecture et Compilation pour les Systèmes Embarqués",   "TRACES"),
    33:    ("Assistance à la Certification des Applications DIstribuées et Embarquées",         "ACADIE"),
    54:    ("Interactive Critical Systems",                                                     "ICS"),
    55:    ("Etude de l'Interaction Personne-SystèmE",                                         "ELIPSE"),
    58:    ("Temps Réel dans les Réseaux et Systèmes",                                         "TRRS"),
    73:    ("Information Retrieval and Information Synthesis",                                   "IRIS"),
    81:    ("Advancing Rigorous Software and System Engineering",                               "ARSSE"),
    82:    ("coMputational imagINg anD viSion",                                                 "MINDS"),
    83:    ("Reel Expression Vie Artificielle",                                                 "REVA"),
    84:    ("Smart Modeling for softw@re Research and Technology",                               "SMART"),
    85:    ("Structural Models and Tools in Computer Graphics",                                 "STORM"),
    101:   ("Teaching And Learning Enhanced by Technologies",                                    "TALENT"),
    149:   ("Machine Learning Integrity & Safety Fairness Impact Trust",                          "MISFIT"),
}


# ── Contribution type mapping ──────────────────────────────────────
CONTRIBUTION_MAP = {
    "Expert": 1,
    "Contributeur": 2,
    "Utilisateur": 3,
}


def load_themes(conn):
    """Load Themes.csv into THEMES table."""
    path = os.path.join(DATA_DIR, "Themes.csv")
    print(f"  Loading themes from {os.path.basename(path)}...")

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            tid = int(row["CS_TH_COD#"])
            label = row["THEME"].strip()
            niveau = int(row["NIVEAU"]) if row["NIVEAU"].strip() else 0
            parent = int(row["THEME_PARENT"]) if row["THEME_PARENT"].strip() else None

            conn.execute(
                'INSERT OR REPLACE INTO THEMES ("CS_TH_COD#", THEME, NIVEAU, THEME_PARENT) VALUES (?,?,?,?)',
                (tid, label, niveau, parent)
            )
            count += 1

    print(f"    -> {count} themes loaded")
    return count


def load_persons(conn):
    """Load unique persons from positions.csv into PERSONNE table.

    The dump (2026-04-15) embeds person info directly in positions.csv
    with columns: ID_MEMBRE, PE_PE_NOM, PE_PE_PRENOM.
    """
    path = os.path.join(DATA_DIR, "positions.csv")
    print(f"  Loading persons from {os.path.basename(path)}...")

    persons = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = int(row["ID_MEMBRE"])
            nom = row["PE_PE_NOM"].strip()
            prenom = row["PE_PE_PRENOM"].strip()
            persons[pid] = (nom, prenom)

    for pid, (nom, prenom) in persons.items():
        conn.execute(
            'INSERT OR REPLACE INTO PERSONNE ("PE_PE_COD#", PE_PE_NOM, PE_PE_PRENOM) VALUES (?,?,?)',
            (pid, nom, prenom)
        )

    print(f"    -> {len(persons)} persons loaded")
    return len(persons)


def load_positions(conn):
    """Load positions.csv into POSITIONNEMENT table.

    Dump format (2026-04-15) — UTF-8 CSV with columns:
      ID_MEMBRE, PE_PE_NOM, PE_PE_PRENOM, THEME_CODE, TYPE_CONTRIBUTION,
      ID_TEMPORALITE, TEMPORALITE, ID_STRUCTURE, ID_TYPE_STRUCTURE,
      TYPE_STRUCTURE, LIB_STRUCTURE, ID_STRUCTURE_PARENT, LIB_STRUCTURE_PARENT

    Structure and temporality data are now included directly in the dump.
    """
    path = os.path.join(DATA_DIR, "positions.csv")
    print(f"  Loading positions from {os.path.basename(path)}...")

    # Load valid theme IDs for validation
    valid_themes = set(
        r[0] for r in conn.execute('SELECT "CS_TH_COD#" FROM THEMES').fetchall()
    )

    with_struct = 0
    without_struct = 0

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        skipped = 0
        for row in reader:
            try:
                idpers = int(row["ID_MEMBRE"])
                idtheme = int(row["THEME_CODE"])
                libcontrib = row["TYPE_CONTRIBUTION"].strip()
            except (ValueError, KeyError):
                skipped += 1
                continue

            if idtheme not in valid_themes:
                skipped += 1
                continue

            idcontrib = CONTRIBUTION_MAP.get(libcontrib, 2)

            # Get theme label from THEMES table
            theme_row = conn.execute(
                'SELECT THEME FROM THEMES WHERE "CS_TH_COD#" = ?', (idtheme,)
            ).fetchone()
            libtheme = theme_row[0] if theme_row else None

            # Read structure data directly from CSV
            try:
                idstruct = int(row["ID_STRUCTURE"]) if row.get("ID_STRUCTURE", "").strip() else None
            except ValueError:
                idstruct = None
            libstruct = row.get("LIB_STRUCTURE", "").strip() or None

            try:
                idtypestruct = int(row["ID_TYPE_STRUCTURE"]) if row.get("ID_TYPE_STRUCTURE", "").strip() else None
            except ValueError:
                idtypestruct = None
            libtypestruct = row.get("TYPE_STRUCTURE", "").strip() or None

            try:
                idstructparent = int(row["ID_STRUCTURE_PARENT"]) if row.get("ID_STRUCTURE_PARENT", "").strip() else None
            except ValueError:
                idstructparent = None
            libstructparent = row.get("LIB_STRUCTURE_PARENT", "").strip() or None

            if idstruct is not None:
                with_struct += 1
            else:
                without_struct += 1

            # Read temporality directly from CSV
            try:
                idtemp = int(row["ID_TEMPORALITE"]) if row.get("ID_TEMPORALITE", "").strip() else 1
            except ValueError:
                idtemp = 1
            libtemp = row.get("TEMPORALITE", "").strip() or 'Présent'

            conn.execute(
                """INSERT INTO POSITIONNEMENT (
                    IDPERS, IDCONTRIBUTION, LIBCONTRIBUTION,
                    IDTEMPORALITE, LIBELLETEMPORALITE,
                    IDTHEME, LIBELLETHEME,
                    IDSTRUCTURE, LIBELLESTRUCTURE,
                    IDTYPESTRUCTURE, LIBELLETYPESTRUCTURE,
                    IDSTRUCTUREPARENTE, LIBELLESTRUCTUREPARENTE,
                    AUTO_GENERE
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, NULL)""",
                (idpers, idcontrib, libcontrib,
                 idtemp, libtemp,
                 idtheme, libtheme,
                 idstruct, libstruct,
                 idtypestruct, libtypestruct,
                 idstructparent, libstructparent)
            )
            count += 1

    print(f"    -> {count} positions loaded ({skipped} skipped)")
    print(f"    -> {with_struct} with structure, {without_struct} without")
    return count


def propagate_parents(conn):
    """Propagate positions from child themes to all parent themes.

    For every manual positioning on a child theme, create auto-generated
    entries on all ancestor themes (up to the root), matching the logic
    of the Oracle procedure PROPAGER_POSITIONNEMENT_PARENT.

    Auto-generated rows use AUTO_GENERE = 'O' (letter O, for 'Oui').
    If the person is already manually positioned on a parent theme
    (same role + same structure), no auto entry is created.
    """
    print("  Propagating positions to parent themes...")

    sql = """
        INSERT INTO POSITIONNEMENT (
            IDPERS, IDCONTRIBUTION, LIBCONTRIBUTION,
            IDTEMPORALITE, LIBELLETEMPORALITE,
            IDTHEME, LIBELLETHEME,
            IDSTRUCTURE, LIBELLESTRUCTURE,
            IDTYPESTRUCTURE, LIBELLETYPESTRUCTURE,
            IDSTRUCTUREPARENTE, LIBELLESTRUCTUREPARENTE,
            AUTO_GENERE
        )
        WITH RECURSIVE ancestors AS (
            -- Start from every manual position's direct parent
            SELECT
                p.IDPERS, p.IDCONTRIBUTION, p.LIBCONTRIBUTION,
                p.IDTEMPORALITE, p.LIBELLETEMPORALITE,
                tp."CS_TH_COD#" AS IDTHEME, tp.THEME AS LIBELLETHEME,
                p.IDSTRUCTURE, p.LIBELLESTRUCTURE,
                p.IDTYPESTRUCTURE, p.LIBELLETYPESTRUCTURE,
                p.IDSTRUCTUREPARENTE, p.LIBELLESTRUCTUREPARENTE
            FROM POSITIONNEMENT p
            JOIN THEMES tc ON tc."CS_TH_COD#" = p.IDTHEME
            JOIN THEMES tp ON tp."CS_TH_COD#" = tc.THEME_PARENT
            WHERE p.AUTO_GENERE IS NULL  -- only manual positions as source
              AND tc.THEME_PARENT IS NOT NULL
            UNION
            -- Walk up the hierarchy
            SELECT
                a.IDPERS, a.IDCONTRIBUTION, a.LIBCONTRIBUTION,
                a.IDTEMPORALITE, a.LIBELLETEMPORALITE,
                gp."CS_TH_COD#" AS IDTHEME, gp.THEME AS LIBELLETHEME,
                a.IDSTRUCTURE, a.LIBELLESTRUCTURE,
                a.IDTYPESTRUCTURE, a.LIBELLETYPESTRUCTURE,
                a.IDSTRUCTUREPARENTE, a.LIBELLESTRUCTUREPARENTE
            FROM ancestors a
            JOIN THEMES t ON t."CS_TH_COD#" = a.IDTHEME
            JOIN THEMES gp ON gp."CS_TH_COD#" = t.THEME_PARENT
            WHERE t.THEME_PARENT IS NOT NULL
        )
        SELECT DISTINCT
            a.IDPERS, a.IDCONTRIBUTION, a.LIBCONTRIBUTION,
            a.IDTEMPORALITE, a.LIBELLETEMPORALITE,
            a.IDTHEME, a.LIBELLETHEME,
            a.IDSTRUCTURE, a.LIBELLESTRUCTURE,
            a.IDTYPESTRUCTURE, a.LIBELLETYPESTRUCTURE,
            a.IDSTRUCTUREPARENTE, a.LIBELLESTRUCTUREPARENTE,
            'O' AS AUTO_GENERE
        FROM ancestors a
        -- Skip if already positioned (manual or auto) on this parent
        WHERE NOT EXISTS (
            SELECT 1 FROM POSITIONNEMENT p2
            WHERE p2.IDPERS = a.IDPERS
              AND p2.IDCONTRIBUTION = a.IDCONTRIBUTION
              AND p2.IDTHEME = a.IDTHEME
              AND COALESCE(p2.IDSTRUCTURE, -1) = COALESCE(a.IDSTRUCTURE, -1)
        )
    """
    conn.execute(sql)
    auto_count = conn.execute(
        "SELECT COUNT(*) FROM POSITIONNEMENT WHERE AUTO_GENERE = 'O'"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM POSITIONNEMENT").fetchone()[0]
    print(f"    -> {auto_count} auto-generated positions added (total now: {total})")
    return auto_count


def create_default_users(conn):
    """Create default dev users (to be replaced in production)."""
    # (username, password, role)
    users = [("lotfi", "admin", "admin"), ("admin", "admin", "admin"), ("guest", "", "viewer")]
    for u, p, r in users:
        conn.execute(
            "INSERT OR REPLACE INTO USERS (username, password, role) VALUES (?, ?, ?)",
            (u, p, r)
        )
    print(f"    -> {len(users)} default users created")


def populate_structures(conn):
    """Populate the STRUCTURES reference table from the acronym mapping
    + auto-discover any structures in POSITIONNEMENT not in the mapping."""
    print("  Populating STRUCTURES reference table...")

    # 1) Insert known acronyms
    for sid, (libelle, acronyme) in STRUCTURE_ACRONYMS.items():
        conn.execute(
            "INSERT OR REPLACE INTO STRUCTURES (id, libelle, acronyme) VALUES (?, ?, ?)",
            (sid, libelle, acronyme)
        )

    # 2) Auto-discover structures in POSITIONNEMENT that aren't in the mapping
    unknown = conn.execute("""
        SELECT DISTINCT p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM POSITIONNEMENT p
        WHERE p.IDSTRUCTURE IS NOT NULL
          AND p.IDSTRUCTURE NOT IN (SELECT id FROM STRUCTURES)
    """).fetchall()
    for uid, ulib in unknown:
        fallback = ulib or f"STRUCT-{uid}"
        conn.execute(
            "INSERT OR REPLACE INTO STRUCTURES (id, libelle, acronyme) VALUES (?, ?, ?)",
            (uid, fallback, fallback)
        )

    total = conn.execute("SELECT COUNT(*) FROM STRUCTURES").fetchone()[0]
    print(f"    -> {total} structures référencées ({len(STRUCTURE_ACRONYMS)} avec acronyme)")
    return total




def main():
    # Remove old DB if exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"  Removed old database: {DB_PATH}")

    print(f"\n  Creating database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create schema
    conn.executescript(SCHEMA)
    print("  Schema created.")

    # Load data
    n_themes = load_themes(conn)
    n_persons = load_persons(conn)
    n_positions = load_positions(conn)
    n_propagated = propagate_parents(conn)
    create_default_users(conn)

    populate_structures(conn)

    # Store schema version
    conn.execute(
        "INSERT OR REPLACE INTO DB_META (key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,)
    )
    print(f"  Schema version set to: {SCHEMA_VERSION}")

    conn.commit()

    # Verify
    print("\n  === Verification ===")
    for table in ("THEMES", "PERSONNE", "POSITIONNEMENT", "USERS", "DB_META"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"    {table}: {count} rows")

    # Check structures
    structs = conn.execute(
        "SELECT DISTINCT LIBELLESTRUCTURE FROM POSITIONNEMENT WHERE IDSTRUCTURE IS NOT NULL ORDER BY LIBELLESTRUCTURE"
    ).fetchall()
    print(f"    Structures distinctes: {len(structs)}")


    # Quick sanity checks
    roots = conn.execute(
        'SELECT COUNT(*) FROM THEMES WHERE THEME_PARENT IS NULL'
    ).fetchone()[0]
    print(f"    Root themes: {roots}")

    present = conn.execute(
        "SELECT COUNT(*) FROM POSITIONNEMENT WHERE LIBELLETEMPORALITE = 'Présent'"
    ).fetchone()[0]
    print(f"    Present positions: {present}")

    auto = conn.execute(
        "SELECT COUNT(*) FROM POSITIONNEMENT WHERE AUTO_GENERE = 'O'"
    ).fetchone()[0]
    manu = conn.execute(
        "SELECT COUNT(*) FROM POSITIONNEMENT WHERE AUTO_GENERE IS NULL"
    ).fetchone()[0]
    print(f"    Manual positions: {manu}")
    print(f"    Auto-generated (propagated): {auto}")

    # Contribution type breakdown
    contribs = conn.execute(
        "SELECT LIBCONTRIBUTION, COUNT(*) as cnt FROM POSITIONNEMENT WHERE AUTO_GENERE IS NULL GROUP BY LIBCONTRIBUTION ORDER BY cnt DESC"
    ).fetchall()
    print(f"    Contribution types: {', '.join(f'{r[0]}={r[1]}' for r in contribs)}")

    # Test recursive CTE (replacement for CONNECT BY)
    print("\n  === Testing recursive CTE (CONNECT BY replacement) ===")
    cte_sql = """
    WITH RECURSIVE theme_tree AS (
        SELECT "CS_TH_COD#", THEME, THEME_PARENT, NIVEAU, 0 as depth
        FROM THEMES
        WHERE THEME_PARENT IS NULL
        UNION ALL
        SELECT t."CS_TH_COD#", t.THEME, t.THEME_PARENT, t.NIVEAU, tt.depth + 1
        FROM THEMES t
        JOIN theme_tree tt ON t.THEME_PARENT = tt."CS_TH_COD#"
    )
    SELECT COUNT(*) FROM theme_tree
    """
    total_via_cte = conn.execute(cte_sql).fetchone()[0]
    total_direct = conn.execute("SELECT COUNT(*) FROM THEMES").fetchone()[0]
    if total_via_cte == total_direct:
        print(f"    [OK] Recursive CTE returns {total_via_cte} themes (matches direct count)")
    else:
        print(f"    [WARN] CTE={total_via_cte} vs Direct={total_direct}")

    conn.close()
    print(f"\n  Database ready: {DB_PATH}")
    print(f"  Size: {os.path.getsize(DB_PATH):,} bytes\n")


if __name__ == "__main__":
    main()

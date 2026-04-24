
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
import os, datetime, jwt
from db import fetch_all, fetch_one, execute
import secrets
from functools import wraps

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
FRONT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))

app = Flask(__name__, static_folder=FRONT_DIR, static_url_path='')

@app.get('/')
def front_index():
    return send_from_directory(FRONT_DIR, 'index.html')

@app.get('/dashboard')
def front_dashboard():
    return send_from_directory(FRONT_DIR, 'dashboard.html')


# 1) Keys & config
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
SECRET_KEY = app.config['SECRET_KEY']

# Allowed origin for front
FRONT_ORIGIN = os.getenv('FRONT_ORIGIN', 'http://localhost:3000')
TOKEN_TTL_MIN = int(os.getenv('TOKEN_TTL_MIN', '60'))


# 2) CORS
CORS(app, resources={r"/api/*": {"origins": "*"}},
     expose_headers=["Authorization"],
     supports_credentials=False)

# 3) JWT Helpers
def make_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=TOKEN_TTL_MIN)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == 'OPTIONS':
            return ('', 204)

        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            abort(401)
        token = auth.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user = payload.get("sub")
            request.role = payload.get("role", "admin")
        except jwt.ExpiredSignatureError:
            abort(401, description="Token expired")
        except jwt.InvalidTokenError:
            abort(401, description="Invalid token")
        return fn(*args, **kwargs)
    return wrapper

def require_admin(fn):
    """Decorator: reject viewers with 403 on admin-only endpoints."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(request, 'role', 'admin') == 'viewer':
            abort(403, description="Accès réservé aux administrateurs")
        return fn(*args, **kwargs)
    return wrapper


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.datetime.utcnow().isoformat() + "Z"})

@app.post("/api/login")
def login():
    body = request.get_json(force=True, silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    # Check against USERS table in SQLite
    user = fetch_one("SELECT username, password, role FROM USERS WHERE username = :u", {"u": username})
    if not user:
        abort(401, description="Bad credentials")

    # Guest login: skip password check
    if username != "guest":
        if user["password"] != password:
            abort(401, description="Bad credentials")

    role = user.get("role", "admin")

    exp = datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    token = jwt.encode({"sub": username, "role": role, "exp": exp}, SECRET_KEY, algorithm="HS256")
    return jsonify(access_token=token)



# --------- THEMES ---------
@app.get("/api/themes/tree")
@require_auth
def themes_tree():
    sql = """
        WITH RECURSIVE theme_tree AS (
            SELECT
                t."CS_TH_COD#" AS id,
                t.THEME        AS label,
                t.THEME_PARENT AS parent_id,
                t.NIVEAU       AS lvl,
                0 AS depth
            FROM THEMES t
            WHERE t.THEME_PARENT IS NULL
            UNION ALL
            SELECT
                t2."CS_TH_COD#",
                t2.THEME,
                t2.THEME_PARENT,
                t2.NIVEAU,
                tt.depth + 1
            FROM THEMES t2
            JOIN theme_tree tt ON t2.THEME_PARENT = tt.id
        )
        SELECT id, label, parent_id, lvl
        FROM theme_tree
        ORDER BY label
        """

    rows = fetch_all(sql, {})
    return jsonify(rows)

# --------- PEOPLE SEARCH ---------
@app.post("/api/people/search")
@require_auth
def people_search():
    body = request.get_json(force=True, silent=True) or {}
    ids          = body.get('theme_ids', [])      # list of ints
    include_desc = 1 if body.get('include_desc', True) else 0
    role         = body.get('role', '*')
    temp         = body.get('temporalite', '*')
    mode         = body.get('mode', '*')
    struct_id    = body.get('structure_id')

    if not ids:
        return jsonify([])

    # Build ID placeholders
    ids_placeholders = ", ".join(f":id{i}" for i in range(1, len(ids) + 1))
    binds = {
        'include_desc': include_desc,
        'p_role': role,
        'p_temp': temp,
        'p_mode': mode,
        'struct_id': struct_id
    }
    for i, v in enumerate(ids, start=1):
        binds[f"id{i}"] = int(v)

    if include_desc:
        theme_filter = f"""
            p.IDTHEME IN (
                WITH RECURSIVE descendants AS (
                    SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE "CS_TH_COD#" IN ({ids_placeholders})
                    UNION ALL
                    SELECT t."CS_TH_COD#" FROM THEMES t JOIN descendants d ON t.THEME_PARENT = d.tid
                )
                SELECT tid FROM descendants
            )
        """
    else:
        theme_filter = f"p.IDTHEME IN ({ids_placeholders})"

    sql = f"""
    SELECT
      p.IDPERS,
      per.PE_PE_NOM     AS NOM,
      per.PE_PE_PRENOM  AS PRENOM,
      t.THEME           AS THEME,
      p.IDTHEME,
      p.LIBCONTRIBUTION,
      p.LIBELLETEMPORALITE,
      p.AUTO_GENERE,
      p.IDSTRUCTURE,
      COALESCE(s.acronyme, CAST(p.IDSTRUCTURE AS TEXT)) AS STRUCTURE_ACRONYME
    FROM POSITIONNEMENT p
    JOIN PERSONNE per  ON per."PE_PE_COD#" = p.IDPERS
    JOIN THEMES t      ON t."CS_TH_COD#"  = p.IDTHEME
    LEFT JOIN STRUCTURES s ON s.id = p.IDSTRUCTURE
    WHERE {theme_filter}
      AND (:p_role = '*' OR p.LIBCONTRIBUTION = :p_role)
      AND (:p_temp = '*' OR p.LIBELLETEMPORALITE = :p_temp)
      AND (
           :p_mode = '*' OR
           (:p_mode = 'AUTO' AND p.AUTO_GENERE = 'O') OR
           (:p_mode = 'MANU' AND (p.AUTO_GENERE IS NULL OR p.AUTO_GENERE <> 'O'))
      )
      AND (:struct_id IS NULL OR p.IDSTRUCTURE = :struct_id)
    ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    rows = fetch_all(sql, binds)

    # Viewer: return count only, no nominative data
    if getattr(request, 'role', 'admin') == 'viewer':
        return jsonify([{"total_personnes": len(set(r['idpers'] for r in rows))}])

    return jsonify(rows)

# --------- NON POSITIONNES (global) ---------
@app.get("/api/stats/non_positionnes")
@require_auth
def non_positionnes():
    sql = """
      SELECT per."PE_PE_COD#" AS IDPERS,
             per.PE_PE_NOM  AS NOM,
             per.PE_PE_PRENOM AS PRENOM
      FROM PERSONNE per
      WHERE NOT EXISTS (
        SELECT 1 FROM POSITIONNEMENT p
        WHERE p.IDPERS = per."PE_PE_COD#"
          AND p.LIBELLETEMPORALITE = 'Présent'
      )
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    rows = fetch_all(sql, {})

    # Viewer: return count only, no names
    if getattr(request, 'role', 'admin') == 'viewer':
        return jsonify(dict(total=len(rows), people=[]))

    return jsonify(dict(total=len(rows), people=rows))

# --------- POSITION MANAGEMENT ---------
@app.post("/api/positions")
@require_auth
def add_position():
    body = request.get_json(force=True, silent=True) or {}
    required = ['idpers', 'idtheme', 'libcontr', 'libtemp']
    if any(k not in body for k in required):
        abort(400, "champs manquants")

    # Get theme label
    theme_row = fetch_one('SELECT THEME FROM THEMES WHERE "CS_TH_COD#" = :tid', {"tid": int(body['idtheme'])})
    theme_label = theme_row['theme'] if theme_row else None

    binds = {
      'idpers': int(body['idpers']),
      'idcontr': {'Expert':1,'Contributeur':2,'Utilisateur':3}.get(body['libcontr'],2),
      'libcontr': body['libcontr'],
      'idtemp': 1 if body['libtemp']=='Présent' else 2,
      'libtemp': body['libtemp'],
      'idtheme': int(body['idtheme']),
      'libtheme': theme_label,
      'idstruct': body.get('idstruct'),
      'libstruct': body.get('libstruct'),
      'idtypestruct': body.get('idtypestruct'),
      'libtypestruct': body.get('libtypestruct')
    }

    sql = """
      INSERT INTO POSITIONNEMENT (
        IDPERS, IDCONTRIBUTION, LIBCONTRIBUTION, IDTEMPORALITE, LIBELLETEMPORALITE,
        IDTHEME, LIBELLETHEME, IDSTRUCTURE, LIBELLESTRUCTURE,
        IDTYPESTRUCTURE, LIBELLETYPESTRUCTURE, AUTO_GENERE
      ) VALUES (
        :idpers,
        :idcontr, :libcontr,
        :idtemp,  :libtemp,
        :idtheme, :libtheme,
        :idstruct, :libstruct,
        :idtypestruct, :libtypestruct,
        NULL
      )
    """
    execute(sql, binds)

    # Propagate to parent themes (like Oracle trigger TRG_POS_PARENT)
    _propagate_for_person(binds['idpers'], binds['idcontr'], int(body['idtheme']), binds.get('idstruct'))

    return jsonify(ok=True)

@app.delete("/api/positions")
@require_auth
def delete_position():
    body = request.get_json(force=True, silent=True) or {}
    required = ['idpers', 'idtheme', 'libcontr', 'libtemp']
    if any(k not in body for k in required):
        abort(400, "champs manquants")

    binds = {
        'idpers': int(body['idpers']),
        'idtheme': int(body['idtheme']),
        'libcontr': body['libcontr'],
        'libtemp': body['libtemp'],
    }

    # Delete the manual position
    sql = """
      DELETE FROM POSITIONNEMENT
      WHERE IDPERS = :idpers
        AND IDTHEME = :idtheme
        AND LIBCONTRIBUTION = :libcontr
        AND LIBELLETEMPORALITE = :libtemp
        AND (AUTO_GENERE IS NULL OR AUTO_GENERE <> 'O')
    """
    execute(sql, binds)
    # Also clean up auto-propagated entries that no longer have a source
    _cleanup_orphan_auto(int(body['idpers']))
    return jsonify(ok=True)


def _propagate_for_person(idpers, idcontrib, idtheme, idstruct):
    """Propagate a single manual position to all parent themes.

    Mirrors the Oracle procedure PROPAGER_POSITIONNEMENT_PARENT.
    Walks up the theme hierarchy and creates AUTO_GENERE='O' entries.
    """
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
        WITH RECURSIVE anc AS (
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
            WHERE p.IDPERS = :idpers
              AND p.IDCONTRIBUTION = :idcontrib
              AND p.IDTHEME = :idtheme
              AND COALESCE(p.IDSTRUCTURE, -1) = COALESCE(:idstruct, -1)
              AND p.AUTO_GENERE IS NULL
              AND tc.THEME_PARENT IS NOT NULL
            UNION
            SELECT
                a.IDPERS, a.IDCONTRIBUTION, a.LIBCONTRIBUTION,
                a.IDTEMPORALITE, a.LIBELLETEMPORALITE,
                gp."CS_TH_COD#", gp.THEME,
                a.IDSTRUCTURE, a.LIBELLESTRUCTURE,
                a.IDTYPESTRUCTURE, a.LIBELLETYPESTRUCTURE,
                a.IDSTRUCTUREPARENTE, a.LIBELLESTRUCTUREPARENTE
            FROM anc a
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
        FROM anc a
        WHERE NOT EXISTS (
            SELECT 1 FROM POSITIONNEMENT p2
            WHERE p2.IDPERS = a.IDPERS
              AND p2.IDCONTRIBUTION = a.IDCONTRIBUTION
              AND p2.IDTHEME = a.IDTHEME
              AND COALESCE(p2.IDSTRUCTURE, -1) = COALESCE(a.IDSTRUCTURE, -1)
        )
    """
    execute(sql, {'idpers': idpers, 'idcontrib': idcontrib,
                  'idtheme': idtheme, 'idstruct': idstruct})


def _cleanup_orphan_auto(idpers):
    """Remove auto-propagated entries for a person that no longer have
    a manual source in any child theme."""
    sql = """
        DELETE FROM POSITIONNEMENT
        WHERE IDPERS = :idpers
          AND AUTO_GENERE = 'O'
          AND NOT EXISTS (
            -- keep only if there's still a manual position on a descendant
            WITH RECURSIVE descs AS (
                SELECT "CS_TH_COD#" AS tid FROM THEMES
                WHERE THEME_PARENT = POSITIONNEMENT.IDTHEME
                UNION ALL
                SELECT t."CS_TH_COD#" FROM THEMES t
                JOIN descs d ON t.THEME_PARENT = d.tid
            )
            SELECT 1 FROM POSITIONNEMENT p2
            JOIN descs ON descs.tid = p2.IDTHEME
            WHERE p2.IDPERS = :idpers
              AND p2.AUTO_GENERE IS NULL
          )
    """
    execute(sql, {'idpers': idpers})


# --------- PROPAGATION STATS ---------
@app.get("/api/stats/propagation")
@require_auth
def propagation_stats():
    """Return auto vs manual breakdown for the dashboard."""
    summary = fetch_all("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN AUTO_GENERE IS NULL THEN 1 ELSE 0 END) AS manual,
            SUM(CASE WHEN AUTO_GENERE = 'O' THEN 1 ELSE 0 END)  AS auto
        FROM POSITIONNEMENT
    """, {})

    # Top themes by auto-generated count
    by_theme = fetch_all("""
        SELECT
            t.THEME AS theme,
            p.IDTHEME AS id_theme,
            SUM(CASE WHEN p.AUTO_GENERE IS NULL THEN 1 ELSE 0 END) AS manual,
            SUM(CASE WHEN p.AUTO_GENERE = 'O'    THEN 1 ELSE 0 END) AS auto,
            COUNT(DISTINCT p.IDPERS) AS people
        FROM POSITIONNEMENT p
        JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
        GROUP BY p.IDTHEME, t.THEME
        HAVING auto > 0
        ORDER BY auto DESC
        LIMIT 20
    """, {})

    # Recent auto-generated entries (sample for traceability)
    sample = fetch_all("""
        SELECT
            per.PE_PE_NOM || ' ' || per.PE_PE_PRENOM AS personne,
            p.LIBELLETHEME AS theme,
            p.LIBCONTRIBUTION AS role,
            p.LIBELLETEMPORALITE AS temporalite,
            p.AUTO_GENERE AS mode
        FROM POSITIONNEMENT p
        JOIN PERSONNE per ON per."PE_PE_COD#" = p.IDPERS
        WHERE p.AUTO_GENERE = 'O'
        ORDER BY p.LIBELLETHEME
        LIMIT 30
    """, {})

    s = summary[0] if summary else {'total': 0, 'manual': 0, 'auto': 0}
    return jsonify(
        total=s['total'],
        manual=s['manual'],
        auto=s['auto'],
        by_theme=by_theme,
        sample=sample
    )


# ---------- AUTOCOMPLETE ----------
@app.get("/api/people/find")
@require_auth
@require_admin
def people_find():
    q = (request.args.get("q") or "").strip().lower()

    if len(q) == 0:
        sql = """
        SELECT
            per."PE_PE_COD#"   AS idpers,
            per.PE_PE_NOM    AS nom,
            per.PE_PE_PRENOM AS prenom
        FROM PERSONNE per
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        LIMIT 25
        """
        rows = fetch_all(sql, {})
        return jsonify(rows)

    binds = {"q": f"%{q}%"}
    id_clause = ""
    if q.isdigit():
        id_clause = ' OR CAST(per."PE_PE_COD#" AS TEXT) LIKE :qid'
        binds["qid"] = f"{q}%"

    sql = f"""
    SELECT
        per."PE_PE_COD#"   AS idpers,
        per.PE_PE_NOM    AS nom,
        per.PE_PE_PRENOM AS prenom
    FROM PERSONNE per
    WHERE LOWER(per.PE_PE_NOM) LIKE :q
       OR LOWER(per.PE_PE_PRENOM) LIKE :q
       {id_clause}
    ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    LIMIT 25
    """
    rows = fetch_all(sql, binds)
    return jsonify(rows)


@app.get("/api/themes/find")
@require_auth
def themes_find():
    q = (request.args.get("q") or "").strip().lower()

    if len(q) == 0:
        sql = """
        SELECT
            t."CS_TH_COD#" AS id,
            t.THEME      AS label
        FROM THEMES t
        ORDER BY t.THEME
        LIMIT 25
        """
        rows = fetch_all(sql, {})
        return jsonify(rows)

    sql = """
    SELECT
        t."CS_TH_COD#" AS id,
        t.THEME      AS label
    FROM THEMES t
    WHERE LOWER(t.THEME) LIKE :q
    ORDER BY t.THEME
    LIMIT 25
    """
    rows = fetch_all(sql, {"q": f"%{q}%"})
    return jsonify(rows)


# ========= CSR QUERIES =========

# Helpers
def _as_bool(v):
    if isinstance(v, bool): return v
    return str(v).lower() in ("1","true","yes","y","on")

def _star(v):
    if v is None: return '*'
    s = str(v).strip()
    if s == '' or s.lower() == 'str': return '*'
    return s

def _role_temp_mode_where(alias="p"):
    w = []
    w.append(f"(:r = '*' OR {alias}.LIBCONTRIBUTION = :r)")
    w.append(f"(:t = '*' OR {alias}.LIBELLETEMPORALITE = :t)")
    w.append(f"(:m = '*' OR (:m = 'AUTO' AND {alias}.AUTO_GENERE = 'O') OR (:m = 'MANU' AND ({alias}.AUTO_GENERE IS NULL OR {alias}.AUTO_GENERE <> 'O')))")
    return " AND ".join(w)

def _bind_ids(prefix, ids, binds):
    names = []
    for i, v in enumerate(ids, 1):
        k = f"{prefix}{i}"
        binds[k] = int(v)
        names.append(f":{k}")
    return names

def _themes_descendants_cte(ids_bindnames):
    """Return a CTE that recursively finds all descendants of given theme IDs."""
    ids_csv = ", ".join(ids_bindnames)
    return f"""
    WITH RECURSIVE theme_desc AS (
        SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE "CS_TH_COD#" IN ({ids_csv})
        UNION ALL
        SELECT t."CS_TH_COD#" FROM THEMES t JOIN theme_desc td ON t.THEME_PARENT = td.tid
    )
    """

def _themes_set_sql(ids_bindnames, include_desc=True):
    ids_csv = ", ".join(ids_bindnames)
    if include_desc:
        return f"""IN (
            SELECT tid FROM (
                WITH RECURSIVE td AS (
                    SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE "CS_TH_COD#" IN ({ids_csv})
                    UNION ALL
                    SELECT t."CS_TH_COD#" FROM THEMES t JOIN td ON t.THEME_PARENT = td.tid
                )
                SELECT tid FROM td
            )
        )"""
    else:
        return f"IN ({ids_csv})"


CSR_QUERIES = {}

def register_query(qid, label, params, sql_builder):
    CSR_QUERIES[qid] = {"id": qid, "label": label, "params": params, "sql_builder": sql_builder}

# -------------- Q1 ------------------
def _q_people_with_no_theme(body):
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    sql = f"""
      SELECT
        per."PE_PE_COD#" AS IDPERS,
        per.PE_PE_NOM  AS NOM,
        per.PE_PE_PRENOM AS PRENOM,
        NULL AS IDSTRUCTURE,
        NULL AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE NOT EXISTS (
        SELECT 1 FROM POSITIONNEMENT p
        WHERE p.IDPERS = per."PE_PE_COD#"
          AND {_role_temp_mode_where('p')}
      )
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    binds = {"r": role, "t": temp, "m": mode}
    return sql, binds

register_query(
    "people_with_no_theme",
    "Chercheurs sans positionnement thématique",
    {"role":"str","temporalite":"str","mode":"str"},
    _q_people_with_no_theme
)

# -------------- Q2 ------------------
def _q_people_by_themes(body):
    ids = body.get("theme_ids", []) or []
    if not ids:
        return "SELECT 1 WHERE 0", {}
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"):
        match = "ANY"
    inc   = _as_bool(body.get("include_desc", True))
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"r": role, "t": temp, "m": mode}
    idnames = _bind_ids("th", ids, binds)
    theme_in = _themes_set_sql(idnames, inc)

    if match == "ANY":
        sql = f"""
        SELECT DISTINCT
          per."PE_PE_COD#" AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
          p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM PERSONNE per
        JOIN POSITIONNEMENT p ON p.IDPERS = per."PE_PE_COD#"
        WHERE p.IDTHEME {theme_in}
          AND {_role_temp_mode_where('p')}
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        """
        return sql, binds

    # ALL
    exists_clauses = []
    for i, n in enumerate(idnames, 1):
        if inc:
            one_sub = f"""
            SELECT tid FROM (
                WITH RECURSIVE td AS (
                    SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE "CS_TH_COD#" = {n}
                    UNION ALL
                    SELECT t."CS_TH_COD#" FROM THEMES t JOIN td ON t.THEME_PARENT = td.tid
                )
                SELECT tid FROM td
            )
            """
        else:
            one_sub = f"SELECT {n}"
        exists_clauses.append(f"""
          EXISTS (
            SELECT 1 FROM POSITIONNEMENT px
            WHERE px.IDPERS = per."PE_PE_COD#"
              AND px.IDTHEME IN ({one_sub})
              AND {_role_temp_mode_where('px')}
          )
        """)

    sql = f"""
      SELECT per."PE_PE_COD#" AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
             NULL AS IDSTRUCTURE, NULL AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE {' AND '.join(exists_clauses)}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    return sql, binds

register_query(
    "people_by_themes",
    "Chercheurs positionnés sur des thèmes donnés",
    {"theme_ids":"int[]","match":"str","include_desc":"bool","role":"str","temporalite":"str","mode":"str"},
    _q_people_by_themes
)

# -------------- Q3 ------------------
def _q_people_by_themes_with_exclusion(body):
    ids_inc = body.get("theme_ids", []) or []
    if not ids_inc:
        return "SELECT 1 WHERE 0", {}
    ids_exc = body.get("exclude_theme_ids", []) or []
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"): match = "ANY"
    inc_desc = _as_bool(body.get("include_desc", True))
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"r": role, "t": temp, "m": mode}
    in_names = _bind_ids("inc", ids_inc, binds)
    in_sql = _themes_set_sql(in_names, inc_desc)

    out_sql = None
    if ids_exc:
        out_names = _bind_ids("ex", ids_exc, binds)
        out_sql = _themes_set_sql(out_names, inc_desc)

    if match == "ANY":
        sql = f"""
        SELECT DISTINCT per."PE_PE_COD#" AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
               p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM PERSONNE per
        JOIN POSITIONNEMENT p ON p.IDPERS = per."PE_PE_COD#"
        WHERE p.IDTHEME {in_sql}
          {"AND p.IDTHEME NOT " + out_sql if out_sql else ""}
          AND {_role_temp_mode_where('p')}
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        """
        return sql, binds

    exists_in = []
    for n in in_names:
        if inc_desc:
            one_sub = f"""SELECT tid FROM (WITH RECURSIVE td AS (SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE "CS_TH_COD#" = {n} UNION ALL SELECT t."CS_TH_COD#" FROM THEMES t JOIN td ON t.THEME_PARENT = td.tid) SELECT tid FROM td)"""
        else:
            one_sub = f"SELECT {n}"
        exists_in.append(f"""EXISTS (SELECT 1 FROM POSITIONNEMENT px WHERE px.IDPERS = per."PE_PE_COD#" AND px.IDTHEME IN ({one_sub}) AND {_role_temp_mode_where('px')})""")

    not_exists_out = ""
    if out_sql:
        not_exists_out = f"""AND NOT EXISTS (SELECT 1 FROM POSITIONNEMENT py WHERE py.IDPERS = per."PE_PE_COD#" AND py.IDTHEME {out_sql} AND {_role_temp_mode_where('py')})"""

    sql = f"""
      SELECT per."PE_PE_COD#" AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
             NULL AS IDSTRUCTURE, NULL AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE {' AND '.join(exists_in)} {not_exists_out}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    return sql, binds

register_query(
    "people_by_themes_excluding",
    "Chercheurs sur un thème, excluant un autre",
    {"theme_ids":"int[]","exclude_theme_ids":"int[]","match":"str","include_desc":"bool","role":"str","temporalite":"str","mode":"str"},
    _q_people_by_themes_with_exclusion
)

# -------------- Q4 ------------------
def _q_people_of_structure_by_themes(body):
    struct_id = body.get("structure_id")
    ids = body.get("theme_ids", []) or []
    if not struct_id or not ids:
        return "SELECT 1 WHERE 0", {}
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"): match = "ANY"
    inc   = _as_bool(body.get("include_desc", True))
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"sid": int(struct_id), "r": role, "t": temp, "m": mode}
    idnames = _bind_ids("th", ids, binds)
    theme_in = _themes_set_sql(idnames, inc)

    if match == "ANY":
        sql = f"""
        SELECT DISTINCT per."PE_PE_COD#" AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
               p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM PERSONNE per
        JOIN POSITIONNEMENT p ON p.IDPERS = per."PE_PE_COD#"
        WHERE p.IDSTRUCTURE = :sid
          AND p.IDTHEME {theme_in}
          AND {_role_temp_mode_where('p')}
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        """
        return sql, binds

    exists_parts = []
    for n in idnames:
        if inc:
            one_sub = f"""SELECT tid FROM (WITH RECURSIVE td AS (SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE "CS_TH_COD#" = {n} UNION ALL SELECT t."CS_TH_COD#" FROM THEMES t JOIN td ON t.THEME_PARENT = td.tid) SELECT tid FROM td)"""
        else:
            one_sub = f"SELECT {n}"
        exists_parts.append(f"""EXISTS (SELECT 1 FROM POSITIONNEMENT px WHERE px.IDPERS = per."PE_PE_COD#" AND px.IDSTRUCTURE = :sid AND px.IDTHEME IN ({one_sub}) AND {_role_temp_mode_where('px')})""")

    sql = f"""
      SELECT per."PE_PE_COD#" AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
             :sid AS IDSTRUCTURE, NULL AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE {' AND '.join(exists_parts)}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    return sql, binds

register_query(
    "people_of_structure_by_themes",
    "Chercheurs d'une structure sur des thèmes donnés",
    {"structure_id":"int","theme_ids":"int[]","match":"str","include_desc":"bool","role":"str","temporalite":"str","mode":"str"},
    _q_people_of_structure_by_themes
)

# -------------- Q5 ------------------
def _q_people_of_structure_by_themes_excl(body):
    struct_id = body.get("structure_id")
    ids_inc = body.get("theme_ids", []) or []
    ids_exc = body.get("exclude_theme_ids", []) or []
    if not struct_id or not ids_inc:
        return "SELECT 1 WHERE 0", {}
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"): match = "ANY"
    inc   = _as_bool(body.get("include_desc", True))
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"sid": int(struct_id), "r": role, "t": temp, "m": mode}
    in_names = _bind_ids("inc", ids_inc, binds)
    out_names = _bind_ids("ex", ids_exc, binds) if ids_exc else []
    in_sql = _themes_set_sql(in_names, inc)
    out_sql = _themes_set_sql(out_names, inc) if out_names else None

    if match == "ANY":
        sql = f"""
        SELECT DISTINCT per."PE_PE_COD#" AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
               p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM PERSONNE per
        JOIN POSITIONNEMENT p ON p.IDPERS = per."PE_PE_COD#"
        WHERE p.IDSTRUCTURE = :sid
          AND p.IDTHEME {in_sql}
          {"AND p.IDTHEME NOT " + out_sql if out_sql else ""}
          AND {_role_temp_mode_where('p')}
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        """
        return sql, binds

    exists_in = []
    for n in in_names:
        if inc:
            one_sub = f"""SELECT tid FROM (WITH RECURSIVE td AS (SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE "CS_TH_COD#" = {n} UNION ALL SELECT t."CS_TH_COD#" FROM THEMES t JOIN td ON t.THEME_PARENT = td.tid) SELECT tid FROM td)"""
        else:
            one_sub = f"SELECT {n}"
        exists_in.append(f"""EXISTS (SELECT 1 FROM POSITIONNEMENT px WHERE px.IDPERS = per."PE_PE_COD#" AND px.IDSTRUCTURE = :sid AND px.IDTHEME IN ({one_sub}) AND {_role_temp_mode_where('px')})""")

    not_exists_out = ""
    if out_sql:
        not_exists_out = f"""AND NOT EXISTS (SELECT 1 FROM POSITIONNEMENT py WHERE py.IDPERS = per."PE_PE_COD#" AND py.IDSTRUCTURE = :sid AND py.IDTHEME {out_sql} AND {_role_temp_mode_where('py')})"""

    sql = f"""
      SELECT per."PE_PE_COD#" AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
             :sid AS IDSTRUCTURE, NULL AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE {' AND '.join(exists_in)} {not_exists_out}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    return sql, binds

register_query(
    "people_of_structure_by_themes_excluding",
    "Chercheurs d'une structure sur un thème, excluant un autre",
    {"structure_id":"int","theme_ids":"int[]","exclude_theme_ids":"int[]","match":"str","include_desc":"bool","role":"str","temporalite":"str","mode":"str"},
    _q_people_of_structure_by_themes_excl
)

# -------------- Q6 ------------------
def _q_themes_of_person(body):
    pid = body.get("person_id")
    if not pid: return "SELECT 1 WHERE 0", {}
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    sql = f"""
      SELECT DISTINCT t."CS_TH_COD#" AS IDTHEME, t.THEME
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
      WHERE p.IDPERS = :pid
        AND {_role_temp_mode_where('p')}
      ORDER BY t.THEME
    """
    return sql, {"pid": int(pid), "r": role, "t": temp, "m": mode}

register_query(
    "themes_of_person",
    "Thèmes d'un chercheur",
    {"person_id":"int","role":"str","temporalite":"str","mode":"str"},
    _q_themes_of_person
)

# -------------- Q7 ------------------
def _q_themes_in_structures(body):
    structs = body.get("structure_ids") or []
    any_or_all = (body.get("match") or "ANY").upper()
    if any_or_all not in ("ANY","ALL"): any_or_all = "ANY"
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    binds = {"r": role, "t": temp, "m": mode}

    if not structs or structs == ['*'] or structs == '*':
        sql = f"""
          SELECT DISTINCT t."CS_TH_COD#" AS IDTHEME, t.THEME
          FROM POSITIONNEMENT p
          JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
          WHERE {_role_temp_mode_where('p')}
          ORDER BY t.THEME
        """
        return sql, binds

    snames = _bind_ids("s", structs, binds)

    if any_or_all == "ANY":
        sql = f"""
          SELECT DISTINCT t."CS_TH_COD#" AS IDTHEME, t.THEME
          FROM POSITIONNEMENT p
          JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
          WHERE p.IDSTRUCTURE IN ({", ".join(snames)})
            AND {_role_temp_mode_where('p')}
          ORDER BY t.THEME
        """
        return sql, binds

    sql = f"""
      SELECT t."CS_TH_COD#" AS IDTHEME, t.THEME
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
      WHERE p.IDSTRUCTURE IN ({", ".join(snames)}) AND {_role_temp_mode_where('p')}
      GROUP BY t."CS_TH_COD#", t.THEME
      HAVING COUNT(DISTINCT p.IDSTRUCTURE) = {len(snames)}
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "themes_in_structures",
    "Thèmes couverts par une structure",
    {"structure_ids":"int[]","match":"str","role":"str","temporalite":"str","mode":"str"},
    _q_themes_in_structures
)

# -------------- Q8 ------------------
def _q_themes_not_in_structures(body):
    structs = body.get("structure_ids") or []
    if not structs: return "SELECT 1 WHERE 0", {}
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    binds = {"r": role, "t": temp, "m": mode}
    snames = _bind_ids("s", structs, binds)

    sql = f"""
      SELECT t."CS_TH_COD#" AS IDTHEME, t.THEME
      FROM THEMES t
      WHERE NOT EXISTS (
        SELECT 1 FROM POSITIONNEMENT p
        WHERE p.IDTHEME = t."CS_TH_COD#"
          AND p.IDSTRUCTURE IN ({", ".join(snames)})
          AND {_role_temp_mode_where('p')}
      )
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "themes_not_in_structures",
    "Thèmes non couverts par une structure",
    {"structure_ids":"int[]","role":"str","temporalite":"str","mode":"str"},
    _q_themes_not_in_structures
)

# -------------- Q9 ------------------
def _q_themes_in_S_not_in_Sp(body):
    S  = body.get("include_structures") or []
    Sp = body.get("exclude_structures") or []
    if not S: return "SELECT 1 WHERE 0", {}
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    binds = {"r": role, "t": temp, "m": mode}
    s1 = _bind_ids("s", S, binds)
    s2 = _bind_ids("sp", Sp, binds) if Sp else []

    not_in_sp = ""
    if s2:
        not_in_sp = f"""
        AND NOT EXISTS (
          SELECT 1 FROM POSITIONNEMENT p2
          WHERE p2.IDTHEME = t."CS_TH_COD#"
            AND p2.IDSTRUCTURE IN ({", ".join(s2)})
            AND {_role_temp_mode_where('p2')}
        )
        """

    sql = f"""
      SELECT DISTINCT t."CS_TH_COD#" AS IDTHEME, t.THEME
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
      WHERE p.IDSTRUCTURE IN ({", ".join(s1)})
        AND {_role_temp_mode_where('p')}
        {not_in_sp}
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "themes_in_S_not_in_Sp",
    "Thèmes présents dans une structure mais absents d'une autre",
    {"include_structures":"int[]","exclude_structures":"int[]","role":"str","temporalite":"str","mode":"str"},
    _q_themes_in_S_not_in_Sp
)

# -------------- Q10 ------------------
def _q_subthemes_of_X_in_S(body):
    root = body.get("root_theme_id")
    if not root: return "SELECT 1 WHERE 0", {}
    structs = body.get("structure_ids") or []
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"): match = "ANY"
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"r": role, "t": temp, "m": mode, "rt": int(root)}
    sfilter = ""
    if structs:
        sn = _bind_ids("s", structs, binds)
        sfilter = f" AND p.IDSTRUCTURE IN ({', '.join(sn)})"

    # Descendants of root (excluding root itself)
    sub_cte = """
    WITH RECURSIVE sub_themes AS (
        SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE THEME_PARENT = :rt
        UNION ALL
        SELECT t."CS_TH_COD#" FROM THEMES t JOIN sub_themes st ON t.THEME_PARENT = st.tid
    )
    """

    if match == "ANY":
        sql = f"""
          {sub_cte}
          SELECT DISTINCT t."CS_TH_COD#" AS IDTHEME, t.THEME
          FROM POSITIONNEMENT p
          JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
          WHERE p.IDTHEME IN (SELECT tid FROM sub_themes)
            {sfilter}
            AND {_role_temp_mode_where('p')}
          ORDER BY t.THEME
        """
        return sql, binds

    if not structs:
        return _q_subthemes_of_X_in_S({**body, "match": "ANY"})

    sql = f"""
      {sub_cte}
      SELECT t."CS_TH_COD#" AS IDTHEME, t.THEME
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
      WHERE p.IDTHEME IN (SELECT tid FROM sub_themes)
        AND p.IDSTRUCTURE IN ({', '.join([f':s{i}' for i in range(1, len(structs)+1)])})
        AND {_role_temp_mode_where('p')}
      GROUP BY t."CS_TH_COD#", t.THEME
      HAVING COUNT(DISTINCT p.IDSTRUCTURE) = {len(structs)}
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "subthemes_of_X_in_S",
    "Sous-thèmes d'un thème couverts par une structure",
    {"root_theme_id":"int","structure_ids":"int[]","match":"str","role":"str","temporalite":"str","mode":"str"},
    _q_subthemes_of_X_in_S
)

# -------------- Q11 ------------------
def _q_subthemes_of_X_not_in_S(body):
    root = body.get("root_theme_id")
    structs = body.get("structure_ids") or []
    if not root: return "SELECT 1 WHERE 0", {}
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    binds = {"rt": int(root), "r": role, "t": temp, "m": mode}

    sfilter = ""
    if structs:
        sn = _bind_ids("s", structs, binds)
        sfilter = f" AND p.IDSTRUCTURE IN ({', '.join(sn)})"

    sub_cte = """
    WITH RECURSIVE sub_themes AS (
        SELECT "CS_TH_COD#" AS tid FROM THEMES WHERE THEME_PARENT = :rt
        UNION ALL
        SELECT t."CS_TH_COD#" FROM THEMES t JOIN sub_themes st ON t.THEME_PARENT = st.tid
    )
    """

    sql = f"""
      {sub_cte}
      SELECT t."CS_TH_COD#" AS IDTHEME, t.THEME
      FROM THEMES t
      WHERE t."CS_TH_COD#" IN (SELECT tid FROM sub_themes)
        AND NOT EXISTS (
          SELECT 1 FROM POSITIONNEMENT p
          WHERE p.IDTHEME = t."CS_TH_COD#"
            {sfilter}
            AND {_role_temp_mode_where('p')}
        )
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "subthemes_of_X_not_in_S",
    "Sous-thèmes d'un thème non couverts par une structure",
    {"root_theme_id":"int","structure_ids":"int[]","role":"str","temporalite":"str","mode":"str"},
    _q_subthemes_of_X_not_in_S
)

# -------------- Q12 ------------------
def _q_people_of_structure(body):
    struct_id = body.get("structure_id")
    if not struct_id:
        return "SELECT 1 WHERE 0", {}
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    sql = f"""
      SELECT DISTINCT
        per."PE_PE_COD#" AS IDPERS,
        per.PE_PE_NOM    AS NOM,
        per.PE_PE_PRENOM AS PRENOM,
        p.LIBCONTRIBUTION AS ROLE,
        p.LIBELLETEMPORALITE AS TEMPORALITE,
        GROUP_CONCAT(DISTINCT t.THEME) AS THEMES,
        p.IDSTRUCTURE,
        COALESCE(s.acronyme, CAST(p.IDSTRUCTURE AS TEXT)) AS STRUCTURE_ACRONYME
      FROM POSITIONNEMENT p
      JOIN PERSONNE per  ON per."PE_PE_COD#" = p.IDPERS
      JOIN THEMES t      ON t."CS_TH_COD#"  = p.IDTHEME
      LEFT JOIN STRUCTURES s ON s.id = p.IDSTRUCTURE
      WHERE p.IDSTRUCTURE = :sid
        AND {_role_temp_mode_where('p')}
      GROUP BY per."PE_PE_COD#", per.PE_PE_NOM, per.PE_PE_PRENOM,
               p.LIBCONTRIBUTION, p.LIBELLETEMPORALITE, p.IDSTRUCTURE
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM, p.LIBCONTRIBUTION
    """
    return sql, {"sid": int(struct_id), "r": role, "t": temp, "m": mode}

register_query(
    "people_of_structure",
    "Chercheurs d'une structure",
    {"structure_id":"int","role":"str","temporalite":"str","mode":"str"},
    _q_people_of_structure
)

@app.get("/api/queries")
@require_auth
def list_queries():
    return jsonify([
        {"id": q["id"], "label": q["label"], "params": q.get("params", {})}
        for q in CSR_QUERIES.values()
    ])

# CSR queries that return person-level data — viewers get counts only
VIEWER_COUNT_QUERIES = {
    'people_with_no_theme', 'people_by_themes', 'people_by_themes_excluding',
    'people_of_structure_by_themes', 'people_of_structure_by_themes_excluding',
    'themes_of_person', 'people_of_structure'
}

@app.post("/api/queries/<qid>")
@require_auth
def run_query(qid):
    q = CSR_QUERIES.get(qid)
    if not q:
        abort(404, description=f"Query '{qid}' not found")
    body = request.get_json(force=True, silent=True) or {}
    sql, binds = q["sql_builder"](body)
    rows = fetch_all(sql, binds)

    # Viewer: return aggregated count instead of nominative data
    if getattr(request, 'role', 'admin') == 'viewer' and qid in VIEWER_COUNT_QUERIES:
        # Count distinct persons
        ids_col = next((k for k in ('idpers', 'IDPERS') if rows and k in rows[0]), None)
        if ids_col:
            n = len(set(r[ids_col] for r in rows))
        else:
            n = len(rows)
        return jsonify([{"total_personnes": n}])

    return jsonify(rows)

@app.get("/api/structures/find")
@require_auth
def structures_find():
    q = (request.args.get("q") or "").strip().lower()
    sql = """
      SELECT DISTINCT
             p.IDSTRUCTURE AS id,
             COALESCE(p.LIBELLESTRUCTURE, CAST(p.IDSTRUCTURE AS TEXT)) AS label,
             COALESCE(s.acronyme, CAST(p.IDSTRUCTURE AS TEXT)) AS acronyme
      FROM POSITIONNEMENT p
      LEFT JOIN STRUCTURES s ON s.id = p.IDSTRUCTURE
      WHERE p.IDSTRUCTURE IS NOT NULL
        AND (:q = '' OR LOWER(COALESCE(p.LIBELLESTRUCTURE,'')) LIKE :likeq
             OR CAST(p.IDSTRUCTURE AS TEXT) LIKE :likeq
             OR LOWER(COALESCE(s.acronyme,'')) LIKE :likeq)
      ORDER BY label
      LIMIT 25
    """
    likeq = f"%{q}%"
    rows = fetch_all(sql, {"q": q, "likeq": likeq})
    return jsonify(rows)

# --------- DASHBOARD STATS ---------

def _manu_filter(alias=""):
    """Return SQL clause to filter manual-only positionings when ?mode=manu.
    Default is 'manu'. Pass ?mode=all to include auto-propagated ones."""
    mode = (request.args.get("mode") or "manu").lower()
    if mode == "all":
        return "1=1"  # no filter
    pfx = (alias + ".") if alias else ""
    return f"({pfx}AUTO_GENERE IS NULL OR {pfx}AUTO_GENERE <> 'O')"

@app.get("/api/stats/overview")
@require_auth
def stats_overview():
    mf = _manu_filter()
    sql = f"""
    SELECT
      (SELECT COUNT(DISTINCT IDPERS) FROM POSITIONNEMENT WHERE LIBELLETEMPORALITE = 'Présent' AND {mf}) AS people_present,
      (SELECT COUNT(*) FROM PERSONNE)
        - (SELECT COUNT(DISTINCT IDPERS) FROM POSITIONNEMENT WHERE LIBELLETEMPORALITE = 'Présent' AND {mf}) AS non_positionnes,
      (SELECT COUNT(DISTINCT IDTHEME) FROM POSITIONNEMENT WHERE LIBELLETEMPORALITE = 'Présent' AND {mf}) AS themes_active,
      (SELECT COUNT(DISTINCT IDSTRUCTURE)
         FROM POSITIONNEMENT WHERE LIBELLETEMPORALITE = 'Présent' AND IDSTRUCTURE IS NOT NULL AND {mf}) AS structures_active,
      (SELECT ROUND(AVG(cnt), 2) FROM (
         SELECT IDPERS, COUNT(DISTINCT IDTHEME) cnt
         FROM POSITIONNEMENT WHERE LIBELLETEMPORALITE = 'Présent' AND {mf} GROUP BY IDPERS
      )) AS themes_per_person
    """
    row = fetch_one(sql, {})
    return jsonify(row)


@app.get("/api/stats/top/themes")
@require_auth
def stats_top_themes():
    limit = int(request.args.get("limit", 10))
    mf = _manu_filter("p")
    sql = f"""
    SELECT
        t."CS_TH_COD#" AS id,
        t.THEME      AS label,
        COUNT(DISTINCT p.IDPERS) AS cnt
    FROM POSITIONNEMENT p
    JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
    WHERE p.LIBELLETEMPORALITE = 'Présent'
      AND {mf}
    GROUP BY t."CS_TH_COD#", t.THEME
    ORDER BY cnt DESC
    LIMIT :limit
    """
    rows = fetch_all(sql, {"limit": limit})
    return jsonify(rows)


@app.get("/api/stats/top/structures")
@require_auth
def stats_top_structures():
    limit = int(request.args.get("limit", 10))
    mf = _manu_filter("p")
    sql = f"""
    SELECT
        p.IDSTRUCTURE AS id,
        COALESCE(p.LIBELLESTRUCTURE, CAST(p.IDSTRUCTURE AS TEXT)) AS label,
        COUNT(DISTINCT p.IDPERS) AS cnt
    FROM POSITIONNEMENT p
    WHERE p.IDSTRUCTURE IS NOT NULL
      AND p.LIBELLETEMPORALITE = 'Présent'
      AND {mf}
    GROUP BY p.IDSTRUCTURE, COALESCE(p.LIBELLESTRUCTURE, CAST(p.IDSTRUCTURE AS TEXT))
    ORDER BY cnt DESC
    LIMIT :limit
    """
    rows = fetch_all(sql, {"limit": limit})
    return jsonify(rows)


@app.get("/api/stats/distribution")
@require_auth
def stats_distribution():
    mf = _manu_filter()
    sql_role = f"""
      SELECT COALESCE(LIBCONTRIBUTION,'(N/A)') AS label,
             COUNT(DISTINCT IDPERS) AS cnt
      FROM POSITIONNEMENT
      WHERE LIBELLETEMPORALITE = 'Présent'
        AND {mf}
      GROUP BY COALESCE(LIBCONTRIBUTION,'(N/A)')
      ORDER BY cnt DESC
    """
    sql_temp = f"""
      SELECT COALESCE(LIBELLETEMPORALITE,'(N/A)') AS label,
             COUNT(DISTINCT IDPERS) AS cnt
      FROM POSITIONNEMENT
      WHERE {mf}
      GROUP BY COALESCE(LIBELLETEMPORALITE,'(N/A)')
      ORDER BY cnt DESC
    """
    role = fetch_all(sql_role, {})
    temp = fetch_all(sql_temp, {})
    return jsonify({"role": role, "temporalite": temp})


@app.get("/api/stats/themes_no_expert")
@require_auth
def stats_themes_no_expert():
    """Themes covered by Contributeur/Utilisateur only, with no Expert (Présent)."""
    mf_p = _manu_filter("p")
    mf_pe = _manu_filter("pe")
    sql = f"""
    WITH RECURSIVE anc AS (
      SELECT "CS_TH_COD#" AS tid, THEME_PARENT AS pid,
             CAST(THEME AS TEXT) AS path
      FROM THEMES
      UNION ALL
      SELECT anc.tid, p.THEME_PARENT,
             p.THEME || ' › ' || anc.path
      FROM anc
      JOIN THEMES p ON p."CS_TH_COD#" = anc.pid
    )
    SELECT t."CS_TH_COD#" AS id, t.THEME AS label,
           t.NIVEAU + 1 AS niveau,
           (SELECT a.path FROM anc a WHERE a.tid = t."CS_TH_COD#" AND a.pid IS NULL
            LIMIT 1) AS hierarchy
    FROM THEMES t
    WHERE NOT EXISTS (
        SELECT 1 FROM THEMES child WHERE child.THEME_PARENT = t."CS_TH_COD#"
      )
      AND EXISTS (
        SELECT 1 FROM POSITIONNEMENT p
        WHERE p.IDTHEME = t."CS_TH_COD#"
          AND p.LIBELLETEMPORALITE = 'Présent'
          AND {mf_p}
      )
      AND NOT EXISTS (
        SELECT 1 FROM POSITIONNEMENT pe
        WHERE pe.IDTHEME = t."CS_TH_COD#"
          AND pe.LIBCONTRIBUTION = 'Expert'
          AND pe.LIBELLETEMPORALITE = 'Présent'
          AND {mf_pe}
      )
    ORDER BY t.THEME
    """
    rows = fetch_all(sql, {})
    return jsonify(rows)


@app.get("/api/stats/themes_per_person")
@require_auth
def stats_themes_per_person():
    """Distribution: how many people cover 1, 2, 3... N themes (Présent only)."""
    mf = _manu_filter()
    sql = f"""
    SELECT theme_count AS bucket, COUNT(*) AS people
    FROM (
      SELECT IDPERS, COUNT(DISTINCT IDTHEME) AS theme_count
      FROM POSITIONNEMENT
      WHERE LIBELLETEMPORALITE = 'Présent'
        AND {mf}
      GROUP BY IDPERS
    )
    GROUP BY theme_count
    ORDER BY theme_count
    """
    rows = fetch_all(sql, {})
    return jsonify(rows)


@app.get("/api/stats/top_structures_diversity")
@require_auth
def stats_top_structures_diversity():
    """Top structures by number of distinct themes covered."""
    mf = _manu_filter("pos")
    sql = f"""
    SELECT 
        COALESCE(s.acronyme || ' — ', '') || pos.LIBELLESTRUCTURE AS label, 
        COUNT(DISTINCT pos.IDTHEME) AS total
    FROM POSITIONNEMENT pos
    LEFT JOIN STRUCTURES s ON s.id = pos.IDSTRUCTURE
    WHERE pos.LIBELLETEMPORALITE = 'Présent'
      AND pos.LIBELLESTRUCTURE IS NOT NULL
      AND {mf}
    GROUP BY pos.IDSTRUCTURE, pos.LIBELLESTRUCTURE, s.acronyme
    ORDER BY total DESC
    """
    return jsonify(fetch_all(sql, {}))

@app.get("/api/stats/top_researchers")
@require_auth
def stats_top_researchers():
    """Top 15 researchers with the highest number of present themes.
    Viewers see anonymised labels ('Chercheur #1', etc.)."""
    mf = _manu_filter("pos")
    sql = f"""
    SELECT p."PE_PE_COD#" AS id, p.PE_PE_NOM || ' ' || p.PE_PE_PRENOM AS label, COUNT(DISTINCT pos.IDTHEME) AS total
    FROM POSITIONNEMENT pos
    JOIN PERSONNE p ON p."PE_PE_COD#" = pos.IDPERS
    WHERE pos.LIBELLETEMPORALITE = 'Présent'
      AND {mf}
    GROUP BY p."PE_PE_COD#", p.PE_PE_NOM, p.PE_PE_PRENOM
    ORDER BY total DESC
    LIMIT 15
    """
    rows = fetch_all(sql, {})
    if getattr(request, 'role', 'admin') == 'viewer':
        rows = [{**r, 'label': f'Chercheur #{i+1}'} for i, r in enumerate(rows)]
    return jsonify(rows)


@app.get("/api/stats/all_structures")
@require_auth
def stats_all_structures():
    """Return all structures with their member count (Présent only), sorted by count."""
    mf = _manu_filter("p")
    sql = f"""
    SELECT
        p.IDSTRUCTURE AS id,
        COALESCE(s.acronyme, CAST(p.IDSTRUCTURE AS TEXT)) AS acronyme,
        COALESCE(p.LIBELLESTRUCTURE, CAST(p.IDSTRUCTURE AS TEXT)) AS label,
        COUNT(DISTINCT p.IDPERS) AS cnt
    FROM POSITIONNEMENT p
    LEFT JOIN STRUCTURES s ON s.id = p.IDSTRUCTURE
    WHERE p.IDSTRUCTURE IS NOT NULL
      AND p.LIBELLETEMPORALITE = 'Présent'
      AND {mf}
    GROUP BY p.IDSTRUCTURE
    ORDER BY cnt DESC
    """
    rows = fetch_all(sql, {})
    return jsonify(rows)


@app.get("/api/stats/themes_coverage")
@require_auth
def stats_themes_coverage():
    """Return level-1 themes (NIVEAU=1) with role breakdown (Expert/Contributeur/Utilisateur)."""
    mf = _manu_filter("p")
    sql = f"""
    SELECT
        t."CS_TH_COD#" AS id,
        t.THEME AS label,
        COUNT(DISTINCT CASE WHEN p.LIBCONTRIBUTION = 'Expert' THEN p.IDPERS END) AS experts,
        COUNT(DISTINCT CASE WHEN p.LIBCONTRIBUTION = 'Contributeur' THEN p.IDPERS END) AS contributeurs,
        COUNT(DISTINCT CASE WHEN p.LIBCONTRIBUTION = 'Utilisateur' THEN p.IDPERS END) AS utilisateurs,
        COUNT(DISTINCT p.IDPERS) AS total
    FROM THEMES t
    JOIN POSITIONNEMENT p ON p.IDTHEME = t."CS_TH_COD#"
    WHERE t.NIVEAU = 1
      AND p.LIBELLETEMPORALITE = 'Présent'
      AND {mf}
    GROUP BY t."CS_TH_COD#", t.THEME
    ORDER BY total DESC
    """
    rows = fetch_all(sql, {})
    return jsonify(rows)

@app.get("/api/stats/people_count")
@require_auth
def people_count():
    sid = request.args.get("structure_id", type=int)
    tid = request.args.get("theme_id", type=int)
    limit = int(request.args.get("limit", 15))
    mf = _manu_filter("p")

    if sid and tid:
        sql = f"""
          SELECT COUNT(DISTINCT p.IDPERS) AS cnt
          FROM POSITIONNEMENT p
          WHERE p.LIBELLETEMPORALITE = 'Présent'
            AND p.IDSTRUCTURE = :sid
            AND p.IDTHEME = :tid
            AND {mf}
        """
        row = fetch_one(sql, {"sid": sid, "tid": tid})
        return jsonify({"count": int(row.get("cnt", 0))})

    if sid and not tid:
        sql = f"""
        SELECT t."CS_TH_COD#" AS id,
               t.THEME      AS label,
               COUNT(DISTINCT p.IDPERS) AS cnt
        FROM POSITIONNEMENT p
        JOIN THEMES t ON t."CS_TH_COD#" = p.IDTHEME
        WHERE p.LIBELLETEMPORALITE = 'Présent'
          AND p.IDSTRUCTURE = :sid
          AND {mf}
        GROUP BY t."CS_TH_COD#", t.THEME
        ORDER BY cnt DESC
        LIMIT :limit
        """
        rows = fetch_all(sql, {"sid": sid, "limit": limit})
        return jsonify({"by": "theme", "rows": rows})

    if tid and not sid:
        sql = f"""
        SELECT p.IDSTRUCTURE AS id,
               COALESCE(p.LIBELLESTRUCTURE, CAST(p.IDSTRUCTURE AS TEXT)) AS label,
               COUNT(DISTINCT p.IDPERS) AS cnt
        FROM POSITIONNEMENT p
        WHERE p.LIBELLETEMPORALITE = 'Présent'
          AND p.IDTHEME = :tid
          AND p.IDSTRUCTURE IS NOT NULL
          AND {mf}
        GROUP BY p.IDSTRUCTURE, COALESCE(p.LIBELLESTRUCTURE, CAST(p.IDSTRUCTURE AS TEXT))
        ORDER BY cnt DESC
        LIMIT :limit
        """
        rows = fetch_all(sql, {"tid": tid, "limit": limit})
        return jsonify({"by": "structure", "rows": rows})

    abort(400, description="Provide structure_id and/or theme_id")


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="127.0.0.1", port=5000)

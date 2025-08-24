
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
import os, datetime, jwt
from db import fetch_all, fetch_one, execute
import secrets
from functools import wraps

app = Flask(__name__)

# 1) Clés & config
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
SECRET_KEY = app.config['SECRET_KEY']

# Origine autorisée pour le front
FRONT_ORIGIN = os.getenv('FRONT_ORIGIN', 'http://localhost:3000')
TOKEN_TTL_MIN = int(os.getenv('TOKEN_TTL_MIN', '60'))


# 2) CORS bien configuré pour le front + header Authorization
CORS(app, resources={r"/api/*": {"origins": "*"}},
     expose_headers=["Authorization"],
     supports_credentials=False)
USERS = {"lotfi": "admin", "admin": "admin"}

# 3) Helpers JWT
def make_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=TOKEN_TTL_MIN)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Laisser passer les preflights de CORS
        if request.method == 'OPTIONS':
            return ('', 204)

        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            abort(401)
        token = auth.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user = payload.get("sub")
        except jwt.ExpiredSignatureError:
            abort(401, description="Token expired")
        except jwt.InvalidTokenError:
            abort(401, description="Invalid token")
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
    if username not in USERS or USERS[username] != password:
        abort(401, description="Bad credentials")

    exp = datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    token = jwt.encode({"sub": username, "exp": exp}, SECRET_KEY, algorithm="HS256")
    return jsonify(access_token=token)



# --------- THEMES ---------
@app.get("/api/themes/tree")
@require_auth
def themes_tree():
    sql = """
        SELECT
            t.cs_th_cod#    AS id,
            t.theme         AS label,
            t.theme_parent  AS parent_id,
            t.niveau        AS lvl
        FROM themes t
        START WITH t.theme_parent IS NULL
        CONNECT BY PRIOR t.cs_th_cod# = t.theme_parent
        ORDER SIBLINGS BY t.theme
        """

    rows = fetch_all(sql, {})
    return jsonify(rows)

# --------- PEOPLE SEARCH ---------
@app.post("/api/people/search")
@require_auth
def people_search():
    body = request.get_json(force=True, silent=True) or {}
    ids          = body.get('theme_ids', [])      # liste d'entiers
    include_desc = 1 if body.get('include_desc', True) else 0
    role         = body.get('role', '*')          # 'Expert' | 'Contributeur' | 'Utilisateur' | '*'
    temp         = body.get('temporalite', '*')   # 'Présent' | 'Passé' | '*'
    mode         = body.get('mode', '*')          # 'AUTO' | 'MANU' | '*'
    struct_id    = body.get('structure_id')       # int or None

    if not ids:
        return jsonify([])

    # On construit la clause pour la liste d’IDs (binds nommés)
    ids_bind_names = []
    binds = {
        'include_desc': include_desc,
        'p_role': role,
        'p_temp': temp,
        'p_mode': mode,
        'struct_id': struct_id
    }
    for i, v in enumerate(ids, start=1):
        key = f"id{i}"
        ids_bind_names.append(f":{key}")
        binds[key] = int(v)

    ids_sql = ", ".join(ids_bind_names)

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
      p.IDSTRUCTURE
    FROM POSITIONNEMENT p
    JOIN PERSONNE per  ON per.PE_PE_COD# = p.IDPERS
    JOIN THEMES t      ON t.CS_TH_COD#   = p.IDTHEME
    WHERE 1=1
      AND (
         (:include_desc = 0 AND p.IDTHEME IN ({ids_sql}))
       OR (:include_desc = 1 AND p.IDTHEME IN (
            SELECT cs_th_cod#
            FROM THEMES
            START WITH cs_th_cod# IN ({ids_sql})
            CONNECT BY PRIOR cs_th_cod# = theme_parent
          ))
      )
      AND (:p_role = '*' OR p.LIBCONTRIBUTION = :p_role)
      AND (:p_temp = '*' OR p.LIBELLETEMPORALITE = :p_temp)
      AND (
           :p_mode = '*' OR
           (:p_mode = 'AUTO' AND p.AUTO_GENERE = '0') OR
           (:p_mode = 'MANU' AND (p.AUTO_GENERE IS NULL OR p.AUTO_GENERE <> '0'))
      )
      AND (:struct_id IS NULL OR p.IDSTRUCTURE = :struct_id)
    ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    print("DEBUG /api/people/search binds:", binds)

    rows = fetch_all(sql, binds)
    return jsonify(rows)

# --------- NON POSITIONNES (global) ---------
@app.get("/api/stats/non_positionnes")
@require_auth
def non_positionnes():
    sql = """
      SELECT per.PE_PE_COD# AS IDPERS,
             per.PE_PE_NOM  AS NOM,
             per.PE_PE_PRENOM AS PRENOM
      FROM PERSONNE per
      WHERE NOT EXISTS (
        SELECT 1 FROM POSITIONNEMENT p
        WHERE p.IDPERS = per.PE_PE_COD#
          AND p.LIBELLETEMPORALITE = 'Présent'
      )
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    rows = fetch_all(sql, {})
    return jsonify(dict(total=len(rows), people=rows))

# --------- AJOUT D’UN POSITIONNEMENT MANUEL ---------
@app.post("/api/positions")
@require_auth
def add_position():
    body = request.get_json(force=True, silent=True) or {}
    required = ['idpers', 'idtheme', 'libcontr', 'libtemp']
    if any(k not in body for k in required):
        abort(400, "champs manquants")

    binds = {
      'idpers': int(body['idpers']),
      'idcontr': {'Expert':1,'Contributeur':2,'Utilisateur':3}.get(body['libcontr'],2),
      'libcontr': body['libcontr'],
      'idtemp': 1 if body['libtemp']=='Présent' else 2,
      'libtemp': body['libtemp'],
      'idtheme': int(body['idtheme']),
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
        :idtheme, (SELECT theme FROM THEMES WHERE cs_th_cod# = :idtheme),
        :idstruct, :libstruct,
        :idtypestruct, :libtypestruct,
        NULL
      )
    """
    execute(sql, binds)
    return jsonify(ok=True)
# --------- SUPPRESSION D’UN POSITIONNEMENT MANUEL ---------
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

    # Important: ne supprime QUE les positionnements MANU (non AUTO)
    sql = """
      DELETE FROM POSITIONNEMENT
      WHERE IDPERS = :idpers
        AND IDTHEME = :idtheme
        AND LIBCONTRIBUTION = :libcontr
        AND LIBELLETEMPORALITE = :libtemp
        AND (AUTO_GENERE IS NULL OR AUTO_GENERE <> '0')
    """
    execute(sql, binds)
    return jsonify(ok=True)
# ---------- AUTOCOMPLETE ----------
@app.get("/api/people/find")
@require_auth
def people_find():
    q = (request.args.get("q") or "").strip().lower()

    # 1) Sans saisie -> petite liste par défaut
    if len(q) == 0:
        sql = """
        SELECT * FROM (
          SELECT
            per.PE_PE_COD#   AS idpers,
            per.PE_PE_NOM    AS nom,
            per.PE_PE_PRENOM AS prenom
          FROM PERSONNE per
          ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        )
        WHERE ROWNUM <= 25
        """
        rows = fetch_all(sql, {})
        return jsonify(rows)

    # 2) Avec saisie -> nom/prénom + ID si q est numérique
    binds = {"q": f"%{q}%"}
    id_clause = ""
    if q.isdigit():
        id_clause = " OR TO_CHAR(per.PE_PE_COD#) LIKE :qid"
        binds["qid"] = f"{q}%"

    sql = f"""
    SELECT * FROM (
      SELECT
        per.PE_PE_COD#   AS idpers,
        per.PE_PE_NOM    AS nom,
        per.PE_PE_PRENOM AS prenom
      FROM PERSONNE per
      WHERE LOWER(per.PE_PE_NOM) LIKE :q
         OR LOWER(per.PE_PE_PRENOM) LIKE :q
         {id_clause}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    )
    WHERE ROWNUM <= 25
    """
    rows = fetch_all(sql, binds)
    return jsonify(rows)


@app.get("/api/themes/find")
@require_auth
def themes_find():
    q = (request.args.get("q") or "").strip().lower()

    # 0) Sans saisie -> petite liste de départ
    if len(q) == 0:
        sql = """
        SELECT * FROM (
          SELECT
            t.CS_TH_COD# AS id,
            t.THEME      AS label
          FROM THEMES t
          ORDER BY t.THEME
        )
        WHERE ROWNUM <= 25
        """
        rows = fetch_all(sql, {})
        return jsonify(rows)

    # 1) Avec saisie (filtre nom) — limite 25
    sql = """
    SELECT * FROM (
      SELECT
        t.CS_TH_COD# AS id,
        t.THEME      AS label
      FROM THEMES t
      WHERE LOWER(t.THEME) LIKE :q
      ORDER BY t.THEME
    )
    WHERE ROWNUM <= 25
    """
    rows = fetch_all(sql, {"q": f"%{q}%"})
    return jsonify(rows)


# ========= CSR QUERIES (implémentation) =========

# Helpers
def _as_bool(v): 
    if isinstance(v, bool): return v
    return str(v).lower() in ("1","true","yes","y","on")
def _star(v):
    """
    Normalise rôle/temp/mode : '', None, 'str' -> '*'
    """
    if v is None:
        return '*'
    s = str(v).strip()
    if s == '' or s.lower() == 'str':
        return '*'
    return s

def _role_temp_mode_where(alias="p", role="*", temp="*", mode="*"):
    w = []
    w.append(f"(:r = '*' OR {alias}.LIBCONTRIBUTION = :r)")
    w.append(f"(:t = '*' OR {alias}.LIBELLETEMPORALITE = :t)")
    # AUTO = '0' / MANU = NULL or <> '0'
    w.append(f"(:m = '*' OR (:m = 'AUTO' AND {alias}.AUTO_GENERE = '0') OR (:m = 'MANU' AND ({alias}.AUTO_GENERE IS NULL OR {alias}.AUTO_GENERE <> '0')))")
    return " AND ".join(w)

def _themes_set_sql(ids_bindnames, include_desc=True):
    """
    Retourne un SQL 'IN ( ... )' s'appuyant sur THEMES et descendants (si include_desc).
    ids_bindnames -> e.g. [':th1', ':th2']
    """
    ids_csv = ", ".join(ids_bindnames)
    if include_desc:
        return f"""IN (
            SELECT cs_th_cod# FROM THEMES
            START WITH cs_th_cod# IN ({ids_csv})
            CONNECT BY PRIOR cs_th_cod# = theme_parent
        )"""
    else:
        return f"IN ({ids_csv})"

def _bind_ids(prefix, ids, binds):
    names = []
    for i, v in enumerate(ids, 1):
        k = f"{prefix}{i}"
        binds[k] = int(v)
        names.append(f":{k}")
    return names

def _to_bool(v):
    if isinstance(v, bool): return v
    if v is None: return False
    return str(v).lower() in ("1", "true", "yes", "y", "on")

# Registre: id -> {label, params:{name:type}, sql_builder(body)->(sql, binds)}
CSR_QUERIES = {}

def register_query(qid, label, params, sql_builder):
    CSR_QUERIES[qid] = {"id": qid, "label": label, "params": params, "sql_builder": sql_builder}

# -------------- Q1 ------------------
# I.1  Personnes ne travaillant sur aucune thématique (optionnel: role/temp/mode)
# NOTE: groupement par Equipe/Département/DAS exact impossible pour non-positionnés
# faute d’une table STRUCTURES. On renvoie IDSTRUCTURE/LIBELLESTRUCTURE = NULL.
def _q_people_with_no_theme(body):
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    # On considère "Présent" par défaut si pas fourni ? On laisse '*' par défaut.
    sql = f"""
      SELECT
        per.PE_PE_COD# AS IDPERS,
        per.PE_PE_NOM  AS NOM,
        per.PE_PE_PRENOM AS PRENOM,
        CAST(NULL AS NUMBER) AS IDSTRUCTURE,
        CAST(NULL AS VARCHAR2(200)) AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE NOT EXISTS (
        SELECT 1 FROM POSITIONNEMENT p
        WHERE p.IDPERS = per.PE_PE_COD#
          AND {_role_temp_mode_where('p')}
      )
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    binds = {"r": role, "t": temp, "m": mode}
    return sql, binds

register_query(
    "people_with_no_theme",
    "Personnes sans thématique",
    {"role":"str","temporalite":"str","mode":"str"},
    _q_people_with_no_theme
)

# -------------- Q2 ------------------
# I.2  Personnes travaillant sur (ANY|ALL) de T1..Tn (role/temp/mode), avec include_desc
def _q_people_by_themes(body):
    ids = body.get("theme_ids", []) or []
    if not ids:
        return "SELECT 1 FROM dual WHERE 1=0", {}
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
          per.PE_PE_COD# AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
          p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM PERSONNE per
        JOIN POSITIONNEMENT p ON p.IDPERS = per.PE_PE_COD#
        WHERE p.IDTHEME {theme_in}
          AND {_role_temp_mode_where('p')}
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        """
        return sql, binds

    # ALL: for each root theme, one EXISTS
    exists_clauses = []
    for i, n in enumerate(idnames, 1):
        # sous-ensemble pour un seul root id
        if inc:
            one_sub = f"""
            SELECT cs_th_cod# FROM THEMES
            START WITH cs_th_cod# = {n}
            CONNECT BY PRIOR cs_th_cod# = theme_parent
            """
        else:
            one_sub = f"SELECT {n} FROM dual"

        exists_sql = f"""
          EXISTS (
            SELECT 1 FROM POSITIONNEMENT px
            WHERE px.IDPERS = per.PE_PE_COD#
              AND px.IDTHEME IN ({one_sub})
              AND {_role_temp_mode_where('px')}
          )
        """
        exists_clauses.append(exists_sql)

    sql = f"""
      SELECT per.PE_PE_COD# AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
             CAST(NULL AS NUMBER) AS IDSTRUCTURE, CAST(NULL AS VARCHAR2(200)) AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE {' AND '.join(exists_clauses)}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    return sql, binds

register_query(
    "people_by_themes",
    "Personnes sur T (ANY/ALL, descendants)",
    {"theme_ids":"int[]","match":"str","include_desc":"bool","role":"str","temporalite":"str","mode":"str"},
    _q_people_by_themes
)

# -------------- Q3 ------------------
# I.3  Personnes sur T (ANY|ALL) et pas sur T' (exclusion)
def _q_people_by_themes_with_exclusion(body):
    ids_inc = body.get("theme_ids", []) or []
    if not ids_inc:
        return "SELECT 1 FROM dual WHERE 1=0", {}
    ids_exc = body.get("exclude_theme_ids", []) or []
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"):
        match = "ANY"

    inc_desc = _as_bool(body.get("include_desc", True))
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"r": role, "t": temp, "m": mode}

    # inclusion
    in_names = _bind_ids("in", ids_inc, binds)
    in_sql = _themes_set_sql(in_names, inc_desc)

    # exclusion
    out_sql = "NOT IN (SELECT 0 FROM dual)"  # neutre si liste vide
    if ids_exc:
        out_names = _bind_ids("ex", ids_exc, binds)
        out_sql = _themes_set_sql(out_names, inc_desc)

    if match == "ANY":
        sql = f"""
        SELECT DISTINCT per.PE_PE_COD# AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
               p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM PERSONNE per
        JOIN POSITIONNEMENT p ON p.IDPERS = per.PE_PE_COD#
        WHERE p.IDTHEME {in_sql}
          AND p.IDTHEME NOT {out_sql}
          AND {_role_temp_mode_where('p')}
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        """
        return sql, binds

    # ALL + exclusion : ALL sur inclusion via EXISTS chainés + NOT EXISTS sur exclusion
    exists_in = []
    for i, n in enumerate(in_names, 1):
        if inc_desc:
            one_sub = f"""
            SELECT cs_th_cod# FROM THEMES
            START WITH cs_th_cod# = {n}
            CONNECT BY PRIOR cs_th_cod# = theme_parent
            """
        else:
            one_sub = f"SELECT {n} FROM dual"
        exists_in.append(f"""
        EXISTS (
          SELECT 1 FROM POSITIONNEMENT px
          WHERE px.IDPERS = per.PE_PE_COD#
            AND px.IDTHEME IN ({one_sub})
            AND {_role_temp_mode_where('px')}
        )""")

    not_exists_out = ""
    if ids_exc:
        not_exists_out = f"""
        AND NOT EXISTS (
          SELECT 1 FROM POSITIONNEMENT py
          WHERE py.IDPERS = per.PE_PE_COD#
            AND py.IDTHEME {out_sql}
            AND {_role_temp_mode_where('py')}
        )
        """

    sql = f"""
      SELECT per.PE_PE_COD# AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
             CAST(NULL AS NUMBER) AS IDSTRUCTURE, CAST(NULL AS VARCHAR2(200)) AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE {' AND '.join(exists_in)}
        {not_exists_out}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    return sql, binds

register_query(
    "people_by_themes_excluding",
    "Personnes sur T mais pas sur T’",
    {"theme_ids":"int[]","exclude_theme_ids":"int[]","match":"str","include_desc":"bool","role":"str","temporalite":"str","mode":"str"},
    _q_people_by_themes_with_exclusion
)

# -------------- Q4 ------------------
# I.4  Personnes de la structure S sur T (ANY/ALL)
# NOTE: sans table STRUCTURES, pas de “sous-structures de S”; on filtre IDSTRUCTURE = S
def _q_people_of_structure_by_themes(body):
    struct_id = body.get("structure_id")
    ids = body.get("theme_ids", []) or []
    if not struct_id or not ids:
        return "SELECT 1 FROM dual WHERE 1=0", {}
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"):
        match = "ANY"
    inc   = _as_bool(body.get("include_desc", True))
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"sid": int(struct_id), "r": role, "t": temp, "m": mode}
    idnames = _bind_ids("th", ids, binds)
    theme_in = _themes_set_sql(idnames, inc)

    if match == "ANY":
        sql = f"""
        SELECT DISTINCT per.PE_PE_COD# AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
               p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM PERSONNE per
        JOIN POSITIONNEMENT p ON p.IDPERS = per.PE_PE_COD#
        WHERE p.IDSTRUCTURE = :sid
          AND p.IDTHEME {theme_in}
          AND {_role_temp_mode_where('p')}
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        """
        return sql, binds

    # ALL
    exists_parts = []
    for n in idnames:
        if inc:
            one_sub = f"""
            SELECT cs_th_cod# FROM THEMES
            START WITH cs_th_cod# = {n}
            CONNECT BY PRIOR cs_th_cod# = theme_parent
            """
        else:
            one_sub = f"SELECT {n} FROM dual"
        exists_parts.append(f"""
          EXISTS (
            SELECT 1 FROM POSITIONNEMENT px
            WHERE px.IDPERS = per.PE_PE_COD#
              AND px.IDSTRUCTURE = :sid
              AND px.IDTHEME IN ({one_sub})
              AND {_role_temp_mode_where('px')}
          )
        """)

    sql = f"""
      SELECT per.PE_PE_COD# AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
             :sid AS IDSTRUCTURE, CAST(NULL AS VARCHAR2(200)) AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE {' AND '.join(exists_parts)}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    return sql, binds

register_query(
    "people_of_structure_by_themes",
    "Personnes de la structure S sur T",
    {"structure_id":"int","theme_ids":"int[]","match":"str","include_desc":"bool","role":"str","temporalite":"str","mode":"str"},
    _q_people_of_structure_by_themes
)

# -------------- Q5 ------------------
# I.5 idem Q4 mais “et pas sur T’”
def _q_people_of_structure_by_themes_excl(body):
    struct_id = body.get("structure_id")
    ids_inc = body.get("theme_ids", []) or []
    ids_exc = body.get("exclude_theme_ids", []) or []
    if not struct_id or not ids_inc:
        return "SELECT 1 FROM dual WHERE 1=0", {}
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"):
        match = "ANY"
    inc   = _as_bool(body.get("include_desc", True))
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"sid": int(struct_id), "r": role, "t": temp, "m": mode}
    in_names = _bind_ids("in", ids_inc, binds)
    out_names = _bind_ids("ex", ids_exc, binds) if ids_exc else []
    in_sql = _themes_set_sql(in_names, inc)
    out_sql = _themes_set_sql(out_names, inc) if out_names else None

    if match == "ANY":
        sql = f"""
        SELECT DISTINCT per.PE_PE_COD# AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
               p.IDSTRUCTURE, p.LIBELLESTRUCTURE
        FROM PERSONNE per
        JOIN POSITIONNEMENT p ON p.IDPERS = per.PE_PE_COD#
        WHERE p.IDSTRUCTURE = :sid
          AND p.IDTHEME {in_sql}
          {"AND p.IDTHEME NOT " + out_sql if out_sql else ""}
          AND {_role_temp_mode_where('p')}
        ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
        """
        return sql, binds

    # ALL + exclusion
    exists_in = []
    for n in in_names:
        if inc:
            one_sub = f"""
            SELECT cs_th_cod# FROM THEMES
            START WITH cs_th_cod# = {n}
            CONNECT BY PRIOR cs_th_cod# = theme_parent
            """
        else:
            one_sub = f"SELECT {n} FROM dual"
        exists_in.append(f"""
        EXISTS (
          SELECT 1 FROM POSITIONNEMENT px
          WHERE px.IDPERS = per.PE_PE_COD#
            AND px.IDSTRUCTURE = :sid
            AND px.IDTHEME IN ({one_sub})
            AND {_role_temp_mode_where('px')}
        )""")
    not_exists_out = ""
    if out_sql:
        not_exists_out = f"""
        AND NOT EXISTS (
          SELECT 1 FROM POSITIONNEMENT py
          WHERE py.IDPERS = per.PE_PE_COD#
            AND py.IDSTRUCTURE = :sid
            AND py.IDTHEME {out_sql}
            AND {_role_temp_mode_where('py')}
        )
        """

    sql = f"""
      SELECT per.PE_PE_COD# AS IDPERS, per.PE_PE_NOM AS NOM, per.PE_PE_PRENOM AS PRENOM,
             :sid AS IDSTRUCTURE, CAST(NULL AS VARCHAR2(200)) AS LIBELLESTRUCTURE
      FROM PERSONNE per
      WHERE {' AND '.join(exists_in)}
        {not_exists_out}
      ORDER BY per.PE_PE_NOM, per.PE_PE_PRENOM
    """
    return sql, binds

register_query(
    "people_of_structure_by_themes_excluding",
    "Personnes de S sur T mais pas sur T’",
    {"structure_id":"int","theme_ids":"int[]","exclude_theme_ids":"int[]","match":"str","include_desc":"bool","role":"str","temporalite":"str","mode":"str"},
    _q_people_of_structure_by_themes_excl
)

# -------------- Q6 ------------------
# II.6 Thématiques développées par la personne X (filtrable role/temp/mode)
def _q_themes_of_person(body):
    pid = body.get("person_id")
    if not pid: return "SELECT 1 FROM dual WHERE 1=0", {}
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    sql = f"""
      SELECT DISTINCT t.CS_TH_COD# AS IDTHEME, t.THEME
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t.CS_TH_COD# = p.IDTHEME
      WHERE p.IDPERS = :pid
        AND {_role_temp_mode_where('p')}
      ORDER BY t.THEME
    """
    return sql, {"pid": int(pid), "r": role, "t": temp, "m": mode}

register_query(
    "themes_of_person",
    "Thématiques d’une personne",
    {"person_id":"int","role":"str","temporalite":"str","mode":"str"},
    _q_themes_of_person
)

# -------------- Q7 ------------------
# II.7 Thématiques développées dans (ANY|ALL) structures S1..Sn (ou '*')
def _q_themes_in_structures(body):
    structs = body.get("structure_ids") or []
    any_or_all = (body.get("match") or "ANY").upper()
    # '*' -> toutes structures : on ignore le filtre
    if any_or_all not in ("ANY","ALL"): any_or_all = "ANY"

    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    binds = {"r": role, "t": temp, "m": mode}

    if not structs or structs == ['*'] or structs == '*':
        sql = f"""
          SELECT DISTINCT t.CS_TH_COD# AS IDTHEME, t.THEME
          FROM POSITIONNEMENT p
          JOIN THEMES t ON t.CS_TH_COD# = p.IDTHEME
          WHERE {_role_temp_mode_where('p')}
          ORDER BY t.THEME
        """
        return sql, binds

    # structures explicites
    snames = _bind_ids("s", structs, binds)

    if any_or_all == "ANY":
        sql = f"""
          SELECT DISTINCT t.CS_TH_COD# AS IDTHEME, t.THEME
          FROM POSITIONNEMENT p
          JOIN THEMES t ON t.CS_TH_COD# = p.IDTHEME
          WHERE p.IDSTRUCTURE IN ({", ".join(snames)})
            AND {_role_temp_mode_where('p')}
          ORDER BY t.THEME
        """
        return sql, binds

    # ALL = thématiques présentes dans TOUTES les structures fournies
    # -> intersection par HAVING COUNT(DISTINCT structure) = N
    sql = f"""
      SELECT t.CS_TH_COD# AS IDTHEME, t.THEME
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t.CS_TH_COD# = p.IDTHEME
      WHERE p.IDSTRUCTURE IN ({", ".join(snames)}) AND {_role_temp_mode_where('p')}
      GROUP BY t.CS_TH_COD#, t.THEME
      HAVING COUNT(DISTINCT p.IDSTRUCTURE) = {len(snames)}
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "themes_in_structures",
    "Thèmes présents dans S (ANY/ALL ou toutes structures)",
    {"structure_ids":"int[]","match":"str","role":"str","temporalite":"str","mode":"str"},
    _q_themes_in_structures
)

# -------------- Q8 ------------------
# II.8 Thématiques non développées dans les structures S
def _q_themes_not_in_structures(body):
    structs = body.get("structure_ids") or []
    if not structs: return "SELECT 1 FROM dual WHERE 1=0", {}
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    binds = {"r": role, "t": temp, "m": mode}
    snames = _bind_ids("s", structs, binds)

    sql = f"""
      SELECT t.CS_TH_COD# AS IDTHEME, t.THEME
      FROM THEMES t
      WHERE NOT EXISTS (
        SELECT 1 FROM POSITIONNEMENT p
        WHERE p.IDTHEME = t.CS_TH_COD#
          AND p.IDSTRUCTURE IN ({", ".join(snames)})
          AND {_role_temp_mode_where('p')}
      )
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "themes_not_in_structures",
    "Thèmes absents de S",
    {"structure_ids":"int[]","role":"str","temporalite":"str","mode":"str"},
    _q_themes_not_in_structures
)

# -------------- Q9 ------------------
# II.9 Thématiques développées dans S et pas dans S'
def _q_themes_in_S_not_in_Sp(body):
    S  = body.get("include_structures") or []
    Sp = body.get("exclude_structures") or []
    if not S: return "SELECT 1 FROM dual WHERE 1=0", {}
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
          WHERE p2.IDTHEME = t.CS_TH_COD#
            AND p2.IDSTRUCTURE IN ({", ".join(s2)})
            AND {_role_temp_mode_where('p2')}
        )
        """

    sql = f"""
      SELECT DISTINCT t.CS_TH_COD# AS IDTHEME, t.THEME
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t.CS_TH_COD# = p.IDTHEME
      WHERE p.IDSTRUCTURE IN ({", ".join(s1)})
        AND {_role_temp_mode_where('p')}
        {not_in_sp}
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "themes_in_S_not_in_Sp",
    "Thèmes présents dans S mais pas dans S’",
    {"include_structures":"int[]","exclude_structures":"int[]","role":"str","temporalite":"str","mode":"str"},
    _q_themes_in_S_not_in_Sp
)

# -------------- Q10 ------------------
# II.10 Sous-thèmes de X développés dans (ANY|ALL) structures S
def _q_subthemes_of_X_in_S(body):
    root = body.get("root_theme_id")
    if not root: return "SELECT 1 FROM dual WHERE 1=0", {}
    structs = body.get("structure_ids") or []
    match = (body.get("match") or "ANY").upper()
    if match not in ("ANY", "ALL"):
        match = "ANY"

    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))

    binds = {"r": role, "t": temp, "m": mode, "rt": int(root)}
    sfilter = ""
    if structs:
        sn = _bind_ids("s", structs, binds)
        sfilter = f" AND p.IDSTRUCTURE IN ({', '.join(sn)})"

    # Ensemble des sous-thèmes du root (descendants directs/indirects, root exclu)
    sub_sql = """
      SELECT cs_th_cod# FROM THEMES
      START WITH theme_parent = :rt
      CONNECT BY PRIOR cs_th_cod# = theme_parent
    """

    if match == "ANY":
        sql = f"""
          SELECT DISTINCT t.CS_TH_COD# AS IDTHEME, t.THEME
          FROM POSITIONNEMENT p
          JOIN THEMES t ON t.CS_TH_COD# = p.IDTHEME
          WHERE p.IDTHEME IN ({sub_sql})
            {sfilter}
            AND {_role_temp_mode_where('p')}
          ORDER BY t.THEME
        """
        return sql, binds

    # ALL: chaque structure doit le développer
    if not structs:
        # ALL sans structures explicites <=> toutes les structures du dataset -> complexe,
        # on garde ANY equivalent si pas de liste fournie.
        return _q_subthemes_of_X_in_S({**body, "match": "ANY"})

    sql = f"""
      SELECT t.CS_TH_COD# AS IDTHEME, t.THEME
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t.CS_TH_COD# = p.IDTHEME
      WHERE p.IDTHEME IN ({sub_sql})
        AND p.IDSTRUCTURE IN ({', '.join([f':s{i}' for i in range(1, len(structs)+1)])})
        AND {_role_temp_mode_where('p')}
      GROUP BY t.CS_TH_COD#, t.THEME
      HAVING COUNT(DISTINCT p.IDSTRUCTURE) = {len(structs)}
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "subthemes_of_X_in_S",
    "Sous-thèmes de X présents dans S",
    {"root_theme_id":"int","structure_ids":"int[]","match":"str","role":"str","temporalite":"str","mode":"str"},
    _q_subthemes_of_X_in_S
)

# -------------- Q11 ------------------
# II.11 Sous-thèmes de X non développés dans S
def _q_subthemes_of_X_not_in_S(body):
    root = body.get("root_theme_id")
    structs = body.get("structure_ids") or []
    if not root: return "SELECT 1 FROM dual WHERE 1=0", {}
    role  = _star(body.get("role"))
    temp  = _star(body.get("temporalite"))
    mode  = _star(body.get("mode"))
    binds = {"rt": int(root), "r": role, "t": temp, "m": mode}

    sfilter = ""
    if structs:
        sn = _bind_ids("s", structs, binds)
        sfilter = f" AND p.IDSTRUCTURE IN ({', '.join(sn)})"

    sub_sql = """
      SELECT cs_th_cod# FROM THEMES
      START WITH theme_parent = :rt
      CONNECT BY PRIOR cs_th_cod# = theme_parent
    """

    sql = f"""
      SELECT t.CS_TH_COD# AS IDTHEME, t.THEME
      FROM THEMES t
      WHERE t.CS_TH_COD# IN ({sub_sql})
        AND NOT EXISTS (
          SELECT 1 FROM POSITIONNEMENT p
          WHERE p.IDTHEME = t.CS_TH_COD#
            {sfilter}
            AND {_role_temp_mode_where('p')}
        )
      ORDER BY t.THEME
    """
    return sql, binds

register_query(
    "subthemes_of_X_not_in_S",
    "Sous-thèmes de X absents de S",
    {"root_theme_id":"int","structure_ids":"int[]","role":"str","temporalite":"str","mode":"str"},
    _q_subthemes_of_X_not_in_S
)

@app.get("/api/queries")
@require_auth
def list_queries():
    # renvoie le registre dynamique (format "params" que ton front sait lire via normalizeFields)
    return jsonify([
        {"id": q["id"], "label": q["label"], "params": q.get("params", {})}
        for q in CSR_QUERIES.values()
    ])

@app.post("/api/queries/<qid>")
@require_auth
def run_query(qid):
    q = CSR_QUERIES.get(qid)
    if not q:
        abort(404, description=f"Query '{qid}' not found")
    body = request.get_json(force=True, silent=True) or {}
    sql, binds = q["sql_builder"](body)
    rows = fetch_all(sql, binds)
    return jsonify(rows)

@app.get("/api/structures/find")
@require_auth
def structures_find():
    q = (request.args.get("q") or "").strip().lower()
    # On exploite POSITIONNEMENT (pas de table STRUCTURES dédiée pour l’instant)
    sql = """
      SELECT * FROM (
        SELECT DISTINCT
               p.IDSTRUCTURE AS id,
               COALESCE(p.LIBELLESTRUCTURE, TO_CHAR(p.IDSTRUCTURE)) AS label
        FROM POSITIONNEMENT p
        WHERE (:q = '' OR LOWER(COALESCE(p.LIBELLESTRUCTURE,'')) LIKE :likeq
               OR TO_CHAR(p.IDSTRUCTURE) LIKE :likeq)
        ORDER BY label
      ) WHERE ROWNUM <= 25
    """
    likeq = f"%{q}%"
    rows = fetch_all(sql, {"q": q, "likeq": likeq})
    return jsonify(rows)

# --------- DASHBOARD STATS ---------
@app.get("/api/stats/overview")
@require_auth
def stats_overview():
    sql = """
    SELECT
      (SELECT COUNT(*) FROM POSITIONNEMENT) AS positions_total,
      (SELECT COUNT(*) FROM PERSONNE) AS people_total,
      (SELECT COUNT(*) FROM THEMES) AS themes_total,
      (SELECT COUNT(DISTINCT p.IDSTRUCTURE) FROM POSITIONNEMENT p WHERE p.IDSTRUCTURE IS NOT NULL) AS structures_total,
      (SELECT COUNT(*) FROM PERSONNE per
         WHERE NOT EXISTS (
           SELECT 1 FROM POSITIONNEMENT p
           WHERE p.IDPERS = per.PE_PE_COD# AND p.LIBELLETEMPORALITE = 'Présent'
         )
      ) AS non_positionnes
    FROM dual
    """
    row = fetch_one(sql, {})
    return jsonify(row)


@app.get("/api/stats/top/themes")
@require_auth
def stats_top_themes():
    limit = int(request.args.get("limit", 10))
    sql = """
    SELECT * FROM (
      SELECT
        t.CS_TH_COD# AS id,
        t.THEME      AS label,
        COUNT(*)     AS cnt
      FROM POSITIONNEMENT p
      JOIN THEMES t ON t.CS_TH_COD# = p.IDTHEME
      GROUP BY t.CS_TH_COD#, t.THEME
      ORDER BY cnt DESC
    )
    WHERE ROWNUM <= :limit
    """
    rows = fetch_all(sql, {"limit": limit})
    return jsonify(rows)


@app.get("/api/stats/top/structures")
@require_auth
def stats_top_structures():
    limit = int(request.args.get("limit", 10))
    sql = """
    SELECT * FROM (
      SELECT
        p.IDSTRUCTURE AS id,
        COALESCE(p.LIBELLESTRUCTURE, TO_CHAR(p.IDSTRUCTURE)) AS label,
        COUNT(*) AS cnt
      FROM POSITIONNEMENT p
      WHERE p.IDSTRUCTURE IS NOT NULL
      GROUP BY p.IDSTRUCTURE, COALESCE(p.LIBELLESTRUCTURE, TO_CHAR(p.IDSTRUCTURE))
      ORDER BY cnt DESC
    )
    WHERE ROWNUM <= :limit
    """
    rows = fetch_all(sql, {"limit": limit})
    return jsonify(rows)


@app.get("/api/stats/distribution")
@require_auth
def stats_distribution():
    sql_role = """
      SELECT NVL(LIBCONTRIBUTION,'(N/A)') AS label, COUNT(*) AS cnt
      FROM POSITIONNEMENT
      GROUP BY NVL(LIBCONTRIBUTION,'(N/A)')
      ORDER BY cnt DESC
    """
    sql_temp = """
      SELECT NVL(LIBELLETEMPORALITE,'(N/A)') AS label, COUNT(*) AS cnt
      FROM POSITIONNEMENT
      GROUP BY NVL(LIBELLETEMPORALITE,'(N/A)')
      ORDER BY cnt DESC
    """
    sql_mode = """
      SELECT
        SUM(CASE WHEN AUTO_GENERE = '0' THEN 1 ELSE 0 END) AS auto_cnt,
        SUM(CASE WHEN AUTO_GENERE IS NULL OR AUTO_GENERE <> '0' THEN 1 ELSE 0 END) AS manu_cnt
      FROM POSITIONNEMENT
    """
    role = fetch_all(sql_role, {})
    temp = fetch_all(sql_temp, {})
    mode = fetch_one(sql_mode, {})
    mode_rows = [
        {"label": "AUTO", "cnt": int(mode.get("AUTO_CNT", 0) if isinstance(mode, dict) else mode[0])},
        {"label": "MANU", "cnt": int(mode.get("MANU_CNT", 0) if isinstance(mode, dict) else mode[1])},
    ]
    return jsonify({"role": role, "temporalite": temp, "mode": mode_rows})



if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="127.0.0.1", port=5000)


# CSR IRIT — Contexte Complet du Projet

> **Objectif** : Ce document contient TOUTES les informations nécessaires pour que le prochain dev puisse travailler sur ce projet sans ambiguïté. Il couvre l'architecture, le schéma de la BD, les API, le frontend, et les mécanismes internes.
> **Dernière mise à jour** : 2026-04-20

---

## 1. VUE D'ENSEMBLE

**Nom** : Prototype CSR (Cartographie Scientifique et de Recherche)
**Contexte** : Application web pour l'IRIT (Institut de Recherche en Informatique de Toulouse). Elle permet d'explorer les positionnements de chercheurs sur des thématiques scientifiques, par structure (équipe de recherche), rôle et temporalité.
**Stack** : Flask (Python) + HTML/CSS/JS vanilla (pas de framework frontend)
**Base de données** : SQLite (migration depuis Oracle — les requêtes utilisaient CONNECT BY, remplacé par des CTEs récursives)
**Authentification** : JWT avec système de rôles (admin/viewer)

### Données sources
Les données viennent de dumps Oracle exportés en CSV. La BD SQLite est reconstruite automatiquement à partir de ces CSV au démarrage si la version du schéma change.

### Fonctionnalités principales
- Exploration hiérarchique des thèmes
- Recherche multicritère de chercheurs
- 11 requêtes CSR paramétrables
- Dashboard analytique (Chart.js)
- Gestion des positionnements (ajout/suppression)
- Propagation automatique aux thèmes parents
- **Double mode d'accès** : admin (données nominatives) / invité (données anonymisées)

---

## 2. STRUCTURE DES FICHIERS

```
Stage/
├── .env.example              # Variables d'environnement (SECRET_KEY, DB path, etc.)
├── .gitignore
├── readme.md                 # README utilisateur
├── run_dev.py                # Script de lancement rapide
├── PROJECT_CONTEXT.md        # Ce fichier
│
├── backend/
│   ├── app.py                # Serveur Flask principal (1510 lignes) — TOUS les endpoints
│   ├── db.py                 # Couche d'accès SQLite (fetch_all, fetch_one, execute) + auto-rebuild
│   ├── init_db.py            # Initialisation BD : schéma + import CSV + propagation + structures
│   ├── config.py             # Config Oracle legacy (plus utilisée, gardée pour référence)
│   ├── audit_data.py         # Script d'audit des données (standalone)
│   ├── requirements.txt      # Flask==3.0.3, Flask-Cors==4.0.1, python-dotenv==1.0.1, PyJWT==2.8.0
│   └── data/
│       ├── csr.db            # Base SQLite générée (~1 MB)
│       ├── Themes.csv        # Thématiques hiérarchiques
│       ├── positions.csv     # Positionnements (nouveau dump)
│       └── original_dump/    # Dumps Oracle originaux
│
├── frontend/
│   ├── index.html            # Page principale (login + exploration + requêtes CSR)
│   ├── dashboard.html        # Dashboard analytique (KPIs, graphiques Chart.js)
│   ├── css/
│   │   └── styles.css        # Styles globaux (dark theme, glassmorphism)
│   └── js/
│       ├── core.js           # Module partagé : state, api(), login/logout, isAdmin(), JWT, helpers
│       ├── app.js            # Logique index.html (arbre, recherche, pickers, requêtes CSR)
│       └── dashboard.js      # Logique dashboard.html (KPIs, Chart.js, query builder)
```

---

## 3. BASE DE DONNÉES (SQLite)

### 3.1 Schéma complet

```sql
-- Thèmes hiérarchiques
CREATE TABLE THEMES (
    "CS_TH_COD#"   INTEGER PRIMARY KEY,  -- ID unique du thème
    THEME          TEXT NOT NULL,          -- Libellé
    NIVEAU         INTEGER DEFAULT 0,     -- Niveau dans la hiérarchie (0 = racine)
    THEME_PARENT   INTEGER,               -- FK vers le thème parent (NULL = racine)
    FOREIGN KEY (THEME_PARENT) REFERENCES THEMES("CS_TH_COD#")
);

-- Personnes
CREATE TABLE PERSONNE (
    "PE_PE_COD#"   INTEGER PRIMARY KEY,  -- ID unique
    PE_PE_NOM      TEXT NOT NULL,          -- Nom
    PE_PE_PRENOM   TEXT                    -- Prénom
);

-- Positionnements (theme-person-structure assignments)
CREATE TABLE POSITIONNEMENT (
    ROWID_POS              INTEGER PRIMARY KEY AUTOINCREMENT,
    IDPERS                 INTEGER NOT NULL,    -- FK → PERSONNE
    IDCONTRIBUTION         INTEGER,              -- 1=Expert, 2=Contributeur, 3=Utilisateur
    LIBCONTRIBUTION        TEXT,                 -- "Expert", "Contributeur", "Utilisateur"
    IDTEMPORALITE          INTEGER,              -- 1=Présent, 2=Passé
    LIBELLETEMPORALITE     TEXT,                 -- "Présent", "Passé"
    IDTHEME                INTEGER NOT NULL,     -- FK → THEMES
    LIBELLETHEME           TEXT,
    IDSTRUCTURE            INTEGER,              -- FK → équipe (peut être NULL)
    LIBELLESTRUCTURE       TEXT,
    IDTYPESTRUCTURE        INTEGER,
    LIBELLETYPESTRUCTURE   TEXT,
    IDSTRUCTUREPARENTE     INTEGER,
    LIBELLESTRUCTUREPARENTE TEXT,
    AUTO_GENERE            TEXT DEFAULT NULL     -- NULL=manuel, 'O'=auto-propagé
);

-- Utilisateurs avec rôles
CREATE TABLE USERS (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role     TEXT NOT NULL DEFAULT 'admin'   -- 'admin' ou 'viewer'
);

-- Table de référence structures avec acronymes
CREATE TABLE STRUCTURES (
    id              INTEGER PRIMARY KEY,
    libelle         TEXT NOT NULL,
    acronyme        TEXT NOT NULL,
    type_structure  TEXT DEFAULT 'Equipe'
);

-- Versioning pour auto-rebuild
CREATE TABLE DB_META (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### 3.2 Statistiques actuelles

| Table           | Lignes |
|----------------|--------|
| THEMES          | ~563   |
| PERSONNE        | 248    |
| POSITIONNEMENT  | 3727   |
| USERS           | 3      |
| STRUCTURES      | 26     |
| DB_META         | 1      |

### 3.3 Utilisateurs par défaut

| Username | Password | Rôle | Description |
|----------|----------|------|-------------|
| `admin`  | `admin`  | `admin` | Accès complet, données nominatives |
| `lotfi`  | `admin`  | `admin` | Accès complet, données nominatives |
| `guest`  | *(vide)* | `viewer` | Mode invité, données anonymisées |

### 3.4 Mapping des structures (acronymes)

| ID | Acronyme | Libellé complet |
|----|----------|----------------|
| 2 | SC | Signal et Communication |
| 3 | SAMOVA | Structuration, Analyse et MOdélisation de documents Vidéo et Audio |
| 7 | SIG | Systèmes d'Informations Généralisés |
| 8 | ODRGE | Optimisation dynamique de requêtes réparties à grande échelle |
| 10 | SMAC | Systèmes MultiAgents Coopératifs |
| 11 | MELODI | MEthodes et ingénierie des Langues, des Ontologies et du DIscours |
| 16 | LILAC | Logique, Interaction, Langue et Calcul |
| 17 | ADRIA | Argumentation, Décision, Raisonnement, Incertitude et Apprentissage |
| 18 | APO | Algorithmes Parallèles et Optimisation |
| 23 | RMESS | Réseaux, Mobiles, EmBarqués, Sans fil, Satellites |
| 24 | SIERA | Service IntEgration and netwoRk Administration |
| 30 | IRIT | IRIT Général |
| 31 | SEPIA | Système d'Exploitation, systèmes réPartis, de l'Intergiciel à l'Architecture |
| 32 | TRACES | groupe de Recherche en Architecture et Compilation pour les Systèmes Embarqués |
| 33 | ACADIE | Assistance à la Certification des Applications DIstribuées et Embarquées |
| 54 | ICS | Interactive Critical Systems |
| 55 | ELIPSE | Etude de l'Interaction Personne-SystèmE |
| 58 | TRRS | Temps Réel dans les Réseaux et Systèmes |
| 73 | IRIS | Information Retrieval and Information Synthesis |
| 81 | ARSSE | Advancing Rigorous Software and System Engineering |
| 82 | MINDS | coMputational imagINg anD viSion |
| 83 | REVA | Reel Expression Vie Artificielle |
| 84 | SMART | Smart Modeling for softw@re Research and Technology |
| 85 | STORM | Structural Models and Tools in Computer Graphics |
| 101 | TALENT | Teaching And Learning Enhanced by Technologies |
| 149 | MISFIT | Machine Learning Integrity & Safety Fairness Impact Trust |

---

## 4. MÉCANISME D'AUTO-REBUILD

### Fonctionnement

```
Démarrage serveur → import db.py
  └→ db._ensure_db() s'exécute
       └→ Compare DB_META.schema_version vs init_db.SCHEMA_VERSION
            ├── MATCH → démarrage normal (rapide)
            └── MISMATCH ou BD absente → init_db.main()
                  └→ Supprime csr.db, recrée tout depuis les CSV
                       ├── Charge Themes.csv → thèmes hiérarchiques
                       ├── Charge positions.csv → positionnements
                       ├── Propage vers parents → positions AUTO
                       ├── Crée 3 utilisateurs par défaut (admin, lotfi, guest)
                       ├── Peuple la table STRUCTURES (acronymes)
                       └→ Écrit SCHEMA_VERSION dans DB_META
```

### Pour ajouter un nouveau dump ou modifier le schéma
1. Modifier `init_db.py` (schéma, données, fonctions)
2. **Incrémenter `SCHEMA_VERSION`** (ex: "8" → "9")
3. Au prochain démarrage, la BD se reconstruit automatiquement

### Version actuelle : `SCHEMA_VERSION = "8"`

---

## 5. SYSTÈME DE RÔLES (ADMIN / VIEWER)

### Architecture du double mode

Le système implémente deux modes d'accès : **admin** (membre IRIT) et **viewer** (invité anonyme).

#### Backend (app.py)

1. **JWT avec rôle** : Le token JWT contient un champ `role` (`admin` ou `viewer`)
   ```python
   # Dans require_auth : extrait le rôle du JWT
   request.role = payload.get("role", "admin")
   ```

2. **Login invité** : L'utilisateur `guest` se connecte sans mot de passe
   ```python
   if username != "guest":
       if user["password"] != password:
           abort(401)
   ```

3. **Anonymisation des données** : Les endpoints sensibles vérifient `request.role`
   - `POST /api/people/search` → Viewer reçoit `[{"total_personnes": N}]` au lieu des noms
   - `GET /api/stats/non_positionnes` → Viewer reçoit `{total: N, people: []}` (liste vide)
   - `GET /api/stats/top_researchers` → Viewer reçoit `"Chercheur #1"`, `"Chercheur #2"`, etc. au lieu des vrais noms

4. **Protection des mutations** : Le décorateur `@require_admin` bloque les viewers (HTTP 403)
   ```python
   def require_admin(fn):
       if getattr(request, 'role', 'admin') == 'viewer':
           abort(403, "Accès réservé aux administrateurs")
   ```

#### Frontend

1. **core.js** : `isAdmin()` vérifie `state.role === 'admin'` (rôle décodé du JWT et stocké en localStorage)

2. **index.html** : Bouton "Continuer en tant qu'invité" (`#btnGuest`) qui appelle `login('guest', '')`

3. **app.js** :
   - `updateAuthUI()` → affiche `"Connecté : guest (invité)"` si viewer
   - `renderPeople()` → si la réponse contient `total_personnes` (mode viewer), affiche un message "🔒 N personne(s) trouvée(s) — données nominatives masquées (mode invité)" au lieu du tableau
   - Les requêtes CSR en mode viewer retournent aussi des comptages

4. **dashboard.js** :
   - `loadTopResearchers()` → affiche un bandeau jaune "🔒 Données anonymisées — mode invité" + masque les IDs réels (remplacés par index)
   - Les stats agrégées (KPIs, charts, distributions) restent visibles pour tous les rôles — seules les données nominatives sont protégées

### Ce que voit un viewer vs un admin

| Fonctionnalité | Admin (IRIT) | Viewer (invité) |
|---|---|---|
| Recherche personnes | Tableau complet (nom, prénom, thème, rôle...) | "🔒 7 personne(s) trouvée(s)" (comptage seul) |
| Non positionnés | Liste complète avec noms | Comptage total seulement |
| Top chercheurs | Noms réels + IDs | "Chercheur #1", "Chercheur #2"... |
| KPIs dashboard | ✅ | ✅ |
| Charts (thèmes, structures) | ✅ | ✅ |
| Diversité thématique/structure | ✅ | ✅ |
| Requêtes CSR | Résultats détaillés | Comptages uniquement |
| Ajout/suppression positionnement | ✅ | ❌ (403) |

---

## 6. API ENDPOINTS

**Base URL** : `http://127.0.0.1:5000`
**Auth** : Tous les endpoints (sauf `/api/login` et `/api/health`) nécessitent `Authorization: Bearer <token>`

### 6.1 Auth & Santé

| Méthode | Route | Description | Body/Params | Réponse |
|---------|-------|-------------|-------------|---------|
| GET | `/api/health` | Ping | — | `{status:"ok", time:"..."}` |
| POST | `/api/login` | Connexion | `{username, password}` | `{access_token:"..."}` |

### 6.2 Thèmes

| Méthode | Route | Description | Réponse |
|---------|-------|-------------|---------|
| GET | `/api/themes/tree` | Arbre complet (CTE récursive) | `[{id, label, parent_id, lvl}, ...]` |
| GET | `/api/themes/find?q=<texte>` | Autocomplete thèmes | `[{id, label}, ...]` (max 25) |

### 6.3 Personnes

| Méthode | Route | Description | Réponse |
|---------|-------|-------------|---------|
| GET | `/api/people/find?q=<texte>` | Autocomplete personnes | `[{idpers, nom, prenom}, ...]` (max 25) |
| POST | `/api/people/search` | Recherche multicritère | Admin: `[{idpers, nom, prenom, theme, ...}]` / Viewer: `[{total_personnes: N}]` |

**Body de `/api/people/search`** :
```json
{
  "theme_ids": [14],
  "include_desc": true,
  "role": "*",
  "temporalite": "*",
  "mode": "*",
  "structure_id": null
}
```

### 6.4 Structures

| Méthode | Route | Description | Réponse |
|---------|-------|-------------|---------|
| GET | `/api/structures/find?q=<texte>` | Autocomplete structures | `[{id, label, acronyme}, ...]` (max 25) |

### 6.5 Positionnements (CRUD — admin only)

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/api/positions` | Ajouter un pos. MANU (propage aux parents) |
| DELETE | `/api/positions` | Supprimer un pos. MANU (nettoie orphelins) |

### 6.6 Requêtes CSR (11 requêtes paramétrables)

| Route | `GET /api/queries` → liste, `POST /api/queries/<qid>` → exécution |
|-------|------|

| ID | Label | Paramètres |
|----|-------|-----------|
| `people_with_no_theme` | Chercheurs sans positionnement thématique | `role, temporalite, mode` |
| `people_by_themes` | Chercheurs positionnés sur des thèmes donnés | `theme_ids[], match(ANY/ALL), include_desc, role, temporalite, mode` |
| `people_by_themes_excluding` | Chercheurs sur un thème, excluant un autre | `theme_ids[], exclude_theme_ids[], match, include_desc, role, temporalite, mode` |
| `people_of_structure_by_themes` | Chercheurs d'une structure sur des thèmes donnés | `structure_id, theme_ids[], match, include_desc, role, temporalite, mode` |
| `people_of_structure_by_themes_excluding` | Chercheurs d'une structure, thème exclu | `structure_id, theme_ids[], exclude_theme_ids[], match, include_desc, role, temporalite, mode` |
| `themes_of_person` | Thèmes d'un chercheur | `person_id, role, temporalite, mode` |
| `themes_in_structures` | Thèmes couverts par une structure | `structure_ids[], match, role, temporalite, mode` |
| `themes_not_in_structures` | Thèmes non couverts par une structure | `structure_ids[], role, temporalite, mode` |
| `themes_in_S_not_in_Sp` | Thèmes dans S mais absents de S' | `include_structures[], exclude_structures[], role, temporalite, mode` |
| `subthemes_of_X_in_S` | Sous-thèmes d'un thème couverts par une structure | `root_theme_id, structure_ids[], match, role, temporalite, mode` |
| `subthemes_of_X_not_in_S` | Sous-thèmes non couverts | `root_theme_id, structure_ids[], role, temporalite, mode` |

### 6.7 Dashboard Stats

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/stats/overview` | KPIs globaux |
| GET | `/api/stats/top/themes?limit=N` | Top N thèmes par nb personnes |
| GET | `/api/stats/top/structures?limit=N` | Top N structures par nb personnes |
| GET | `/api/stats/distribution` | Répartition par rôle et temporalité |
| GET | `/api/stats/non_positionnes` | Personnes sans positionnement (anonymisé si viewer) |
| GET | `/api/stats/propagation` | Stats auto vs manuel |
| GET | `/api/stats/people_count?structure_id=X&theme_id=Y` | Comptage croisé |
| GET | `/api/stats/top_researchers` | Top 15 chercheurs polyvalents (anonymisé si viewer) |
| GET | `/api/stats/all_structures` | Toutes les structures avec comptage membres |
| GET | `/api/stats/themes_coverage` | Thèmes niveau 1 avec répartition Expert/Contributeur/Utilisateur |
| GET | `/api/stats/struct_theme_diversity` | Diversité thématique par structure |

---

## 7. ARCHITECTURE FRONTEND

### 7.1 Module partagé : `core.js`

Expose `window.core` avec :
- **`state`** : `{baseUrl, token, user, role, flat[], tree[]}` — persisté en `localStorage`
- **`api(path, options)`** : Fetch wrapper avec JWT automatique
- **`login(user, pass)`** / **`logout()`** — gère token + rôle + dispatch `CustomEvent('csr:auth')`
- **`isAdmin()`** : retourne `state.role === 'admin'` — utilisé partout pour conditionner l'affichage
- **`setBaseUrl(), setToken(), setUser()`** — setters avec persistence
- **`buildTree(), renderTree()`** — construction/affichage de l'arbre des thèmes
- **`escapeHtml(), showView()`** — helpers

### 7.2 Page principale : `index.html` + `app.js`

**Sections UI** :
1. **Login** (`view-login`) — form + bouton "Continuer en tant qu'invité" (`#btnGuest`)
2. **App** (`view-app`) — topbar (avec badge rôle) + arbre + recherche + résultats + requêtes CSR

**Fonctions clés** :
- `updateAuthUI()` — affiche `"Connecté : guest (invité)"` si viewer
- `renderPeople(rows)` — si viewer : affiche "🔒 N personne(s) — données masquées", si admin : tableau complet avec acronymes
- `renderCSRTable(rows)` — résultats CSR avec mapping `idstructure` → acronyme via cache `_structMap`
- `attachPicker(input, {mode, fetcher, toItem, minChars})` — picker générique (single/multi, chips, navigation clavier)
- `fetchStructsLike(q)` → `{id, label, acronyme}`
- `fetchThemesLike(q)` → `{id, label}`
- `fetchPeopleLike(q)` → `{id, label}`

### 7.3 Dashboard : `dashboard.html` + `dashboard.js`

**Sections** :
1. **KPIs** : 5 cartes (Chercheurs, Non positionnés, Thèmes, Structures, Moy. thèmes/personne)
2. **Top charts** : bar chart top thèmes + bar horizontal top structures
3. **Distribution** : doughnut rôles + doughnut temporalité
4. **Propagation** : doughnut auto/manuel + stacked bar + tableau
5. **Diversité thématique par structure** : tableau acronyme — nb thèmes distincts
6. **Top chercheurs polyvalents** : anonymisé en mode invité ("Chercheur #1"...)
7. **Explorateur** : autocomplete thème/struct → chart
8. **Query Builder avancé** : multi-pickers + filtres → recherche + export CSV
9. **Zoom modal** : clic graphique → agrandissement

### 7.4 Styles : `styles.css`

- **Dark theme** : fond `#0b0f19`, surface `#111827`, border `#1e293b`
- **Glassmorphism** : `backdrop-filter: blur(12px)`
- **Composants** : `.card`, `.chip`, `.picker-portal`, `.ac-list`, `table`
- **Responsive** : flexbox, media queries

---

## 8. BACKEND — DÉTAILS INTERNES

### 8.1 `db.py` — Couche d'accès

```python
fetch_all(sql, binds) → [dict, ...]  # clés en lowercase
fetch_one(sql, binds) → dict | None
execute(sql, binds)                    # INSERT/UPDATE/DELETE
# Auto-rebuild au moment de l'import via _ensure_db()
```

### 8.2 `init_db.py` — Initialisation

**Fonctions** : `main()`, `load_themes()`, `load_positions()`, `propagate_parents()`, `create_default_users()`, `populate_structures()`

**Variables** : `SCHEMA_VERSION = "8"`, `STRUCTURE_ACRONYMS = {id: (libellé, acronyme), ...}`

### 8.3 `app.py` — Décorateurs

```python
@require_auth    # Vérifie JWT, set request.user et request.role
@require_admin   # Rejette les viewers (403) — pour les endpoints de mutation (positions)
```

### 8.4 Propagation automatique

- Ajout MANU → `_propagate_for_person()` crée des entrées `AUTO_GENERE='O'` sur tous les thèmes parents
- Suppression MANU → `_cleanup_orphan_auto()` nettoie les propagations sans source

---

## 9. CONVENTIONS & PATTERNS

### Nommage SQL
- Colonnes avec `#` : `"CS_TH_COD#"`, `"PE_PE_COD#"` (héritage Oracle, guillemets obligatoires)
- `fetch_all` retourne les clés en **lowercase**
- Frontend : `pick(r, 'nom', 'NOM')` tolère les deux casses

### Acronymes
- L'API retourne `structure_acronyme` via `LEFT JOIN STRUCTURES`
- Frontend : cache `_structMap` (id → acronyme) pour les résultats CSR
- Pickers : affichent `"ACRONYME — Nom complet"`

### Rôles
- JWT contient `role: "admin"` ou `role: "viewer"`
- Backend vérifie avec `getattr(request, 'role', 'admin') == 'viewer'`
- Frontend vérifie avec `isAdmin()` exporté par `core.js`

---

## 10. CONFIGURATION & DÉPLOIEMENT

### Variables d'environnement
```env
SECRET_KEY=change-me-to-a-random-32-char-string
TOKEN_TTL_MIN=360
CSR_DB_PATH=./data/csr.db
HOST=127.0.0.1
PORT=5000
DEBUG=false
```

### Lancement en dev
```bash
cd backend
pip install -r requirements.txt
python app.py
# → http://127.0.0.1:5000 (API + frontend servi par Flask)
```

---

## 11. POINTS D'ATTENTION / GOTCHAS

1. **Encodage CSV** : Les fichiers CSV viennent d'Oracle, parfois en latin1. `fix_encoding()` gère la correction.
2. **Colonnes avec `#`** : `"CS_TH_COD#"` et `"PE_PE_COD#"` doivent toujours être entre guillemets dans le SQL.
3. **Import circulaire** : `db.py` importe `init_db` localement dans `_ensure_db()`.
4. **Pas de framework frontend** : Tout est en vanilla JS, servi par Flask.
5. **CORS ouvert** : `"*"` en dev — à restreindre en production.
6. **Mots de passe en clair** : Prototype uniquement.
7. **Le reloader Flask est désactivé** : `use_reloader=False` pour éviter le double-import.
8. **Guest login** : Pas de vérification de mot de passe pour `username == "guest"`.
9. **ADRIA → MISFIT** : Les anciens membres d'ADRIA (ex: Serrurier, Claeys, Sicre) sont maintenant dans MISFIT (ID=149) dans le nouveau dump.
10. **Structures auto-découvertes** : `populate_structures()` détecte les structures dans POSITIONNEMENT qui n'ont pas d'acronyme et les ajoute avec le libellé complet comme fallback.

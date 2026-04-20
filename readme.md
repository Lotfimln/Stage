# CSR IRIT — Cartographie Scientifique et de Recherche

Application web pour explorer les **positionnements de chercheurs** sur des thématiques scientifiques à l'[IRIT](https://www.irit.fr/) (Institut de Recherche en Informatique de Toulouse).

---

## ✨ Fonctionnalités

### Exploration & Recherche
- **Arbre thématique** hiérarchique (563 thèmes, CTEs récursives)
- **Recherche multicritère** de personnes par thème(s), rôle, temporalité, mode (AUTO/MANU), structure
- **Acronymes de structures** affichés partout (IRIS, SMAC, MISFIT…)
- **Pickers ergonomiques** avec autocomplétion, navigation clavier (↑/↓/Enter/Esc), chips multi-valeurs

### Requêtes CSR (11 modèles paramétrables)
- Chercheurs positionnés / non positionnés sur des thèmes
- Thèmes couverts / non couverts par des structures
- Sous-thèmes présents/absents dans une structure
- Exécution dynamique → rendu tabulaire

### Dashboard analytique
- KPIs globaux, top thèmes, top structures, répartition par rôle/temporalité
- Propagation auto vs manuel, diversité thématique par structure
- Top chercheurs polyvalents, couverture thématique niveau 1
- Graphiques interactifs (Chart.js) avec zoom modal

### Gestion des positionnements
- **Ajouter** un positionnement manuel (formulaire dédié)
- **Supprimer** un positionnement manuel (les AUTO sont protégés)
- **Propagation automatique** aux thèmes parents (émulation du trigger Oracle)

### Double mode d'accès 🔐
| | Membre IRIT (admin) | Invité (viewer) |
|---|---|---|
| Recherche | Tableau nominatif complet | Comptage anonymisé uniquement |
| Top chercheurs | Noms réels | "Chercheur #1", "Chercheur #2"… |
| Stats & graphiques | ✅ | ✅ |
| Ajout/suppression | ✅ | ❌ |

---

## 📁 Structure du projet

```
Stage/
├── .env.example              # Variables d'environnement
├── .gitignore
├── readme.md
├── PROJECT_CONTEXT.md        # Documentation technique complète (pour LLM)
│
├── backend/
│   ├── app.py                # Serveur Flask — tous les endpoints (1510 lignes)
│   ├── db.py                 # Couche SQLite (fetch_all, fetch_one, execute) + auto-rebuild
│   ├── init_db.py            # Schéma + import CSV + propagation + structures
│   ├── audit_data.py         # Script d'audit standalone
│   ├── requirements.txt      # Flask, Flask-Cors, PyJWT, python-dotenv, gunicorn
│   └── data/                 # CSV sources + csr.db (généré, gitignored)
│
├── frontend/
│   ├── index.html            # Page principale (login + exploration + requêtes)
│   ├── dashboard.html        # Dashboard analytique
│   ├── css/styles.css        # Dark theme, glassmorphism
│   └── js/
│       ├── core.js           # Module partagé (state, api, auth, isAdmin)
│       ├── app.js            # Logique page principale
│       └── dashboard.js      # Logique dashboard
│
└── deploy/
    ├── deploy.sh             # Script de déploiement Linux
    ├── nginx.conf            # Reverse proxy Nginx
    └── csr.service           # Service systemd (gunicorn)
```

---

## 🚀 Démarrage rapide

### Prérequis

- **Python 3.10+**
- Fichiers CSV de données dans `backend/data/` (Themes.csv, positions.csv)

### Installation

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Configuration

Copier `.env.example` en `.env` et adapter :

```env
SECRET_KEY=change-me-to-a-random-32-char-string
TOKEN_TTL_MIN=360
CSR_DB_PATH=./data/csr.db
```

### Lancer le serveur

```bash
cd backend
python app.py
```

L'application est accessible sur **http://127.0.0.1:5000** (API + frontend servi par Flask).

> **Note** : Au premier démarrage (ou après incrémentation de `SCHEMA_VERSION` dans `init_db.py`), la base SQLite est reconstruite automatiquement à partir des CSV.

---

## 🔑 Identifiants

| Utilisateur | Mot de passe | Rôle | Accès |
|-------------|-------------|------|-------|
| `admin` | `admin` | admin | Complet (données nominatives) |
| `lotfi` | `admin` | admin | Complet (données nominatives) |
| *(bouton "Continuer en tant qu'invité")* | — | viewer | Anonymisé (comptages seuls) |

> ⚠️ Identifiants de développement uniquement — à sécuriser pour la production.

---

## 📡 API

Tous les endpoints (sauf `/api/login` et `/api/health`) nécessitent `Authorization: Bearer <token>`.

### Auth & Santé
| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/api/login` | Connexion → `{access_token}` |
| GET | `/api/health` | Ping → `{status, time}` |

### Thèmes
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/themes/tree` | Arbre complet |
| GET | `/api/themes/find?q=` | Autocomplétion |

### Personnes
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/people/find?q=` | Autocomplétion |
| POST | `/api/people/search` | Recherche multicritère |

### Structures
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/structures/find?q=` | Autocomplétion (id, label, acronyme) |

### Positionnements (admin uniquement)
| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/api/positions` | Ajouter un positionnement MANU |
| DELETE | `/api/positions` | Supprimer un positionnement MANU |

### Requêtes CSR
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/queries` | Liste des 11 requêtes disponibles |
| POST | `/api/queries/<id>` | Exécuter une requête |

### Dashboard / Stats
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/stats/overview` | KPIs globaux |
| GET | `/api/stats/top/themes` | Top thèmes |
| GET | `/api/stats/top/structures` | Top structures |
| GET | `/api/stats/distribution` | Répartition rôles/temporalité |
| GET | `/api/stats/non_positionnes` | Personnes sans positionnement |
| GET | `/api/stats/propagation` | Stats propagation auto/manuel |
| GET | `/api/stats/top_researchers` | Top 15 chercheurs polyvalents |
| GET | `/api/stats/all_structures` | Toutes les structures + comptage |
| GET | `/api/stats/themes_coverage` | Couverture thématique niveau 1 |
| GET | `/api/stats/people_count` | Comptage croisé structure/thème |

---

## 🧪 Quick tests (cURL)

```bash
# 1) Login
TOKEN=$(curl -s http://127.0.0.1:5000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | jq -r .access_token)

# 2) Ping
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5000/api/health

# 3) Autocomplétion thèmes
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5000/api/themes/find?q=machine"

# 4) Recherche multicritère
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"theme_ids":[492],"include_desc":true,"role":"*","temporalite":"Présent","mode":"*"}' \
  http://127.0.0.1:5000/api/people/search
```

---

## 🔧 Mise à jour du schéma / données

1. Modifier `backend/init_db.py` (schéma, CSV, mappings)
2. **Incrémenter `SCHEMA_VERSION`** (obligatoire pour déclencher le rebuild)
3. Redémarrer le serveur → la base est reconstruite automatiquement

---

## 🚢 Déploiement (production)

Les fichiers de configuration sont dans `deploy/` :

```bash
# Copier le projet sur le serveur
# Configurer nginx (deploy/nginx.conf)
# Installer le service systemd (deploy/csr.service)
# Lancer :
sudo systemctl enable csr && sudo systemctl start csr
```

---

## 🔒 Sécurité

- Les identifiants en dur et la `SECRET_KEY` de développement **ne doivent pas** être utilisés en production.
- Le mode CORS est ouvert (`*`) en dev — à restreindre en production.
- Les mots de passe sont stockés en clair (prototype) — ajouter du hashing (bcrypt) pour la production.

---

## 📖 Documentation technique

Pour une documentation exhaustive (schéma BD, mécanismes internes, architecture frontend, conventions…), voir **[PROJECT_CONTEXT.md](./PROJECT_CONTEXT.md)**.

# Prototype CSR — Front + API (Flask)

Interface web (HTML/JS) + API Flask pour explorer des **personnes / thématiques / structures**, gérer des **positionnements** manuels et exécuter des **requêtes CSR** paramétrables.

---

## Fonctionnalités

- **Authentification JWT** (login simple, token côté client).
- **Exploration des thématiques**
  - `Charger l’arbre` (Oracle `CONNECT BY`) + rendu hiérarchique.
  - Suggestions de thèmes (ouvre une liste même sans saisie).
- **Recherche de personnes**
  - Par thème(s) (avec/sans sous thèmes), rôle, temporalité, mode (AUTO/MANU) et structure.
  - Affichage tabulaire + actions.
- **Positionnements**
  - **Ajouter** un positionnement **MANU** (formulaire dédié).
  - **Supprimer** un positionnement **MANU** (les “AUTO” sont protégés).
- **Pickers** ergonomiques (thèmes / structures / personnes)
  - Ouverture au focus, **navigation clavier** (↑/↓/Enter/Esc), clic.
  - **Chips** (étiquettes) pour champs multi-valeurs, croix de suppression.
  - `structure_id` utilise un **chip single** (croix uniquement sur le chip).
- **Requêtes CSR** (11 modèles)
  - Sélection → génération dynamique des champs (select/bool/number/pickers).
  - Exécution → rendu tabulaire.

---

## Structure du projet
```
.
├── README.md
├── requirements.txt
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── core.js
│   └── app.js
└── backend/
    ├── app.py
    ├── db.py
    └── __init__.py
```
---

## Démarrage

### Prérequis

- **Python 3.10+**
- Accès à une base **Oracle** (les requêtes utilisent `CONNECT BY`).
- Renseigner la connexion dans `backend/db.py` (driver conseillé : `oracledb`).

Installer les dépendances :

```
pip install Flask flask-cors PyJWT oracledb
# ou : pip install -r requirements.txt

## Lancer l’API (backend)

cd backend

# 1) Environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# 2) Dépendances
pip install -r ../requirements.txt

# 3) Variables d'environnement (exemples)
export SECRET_KEY="dev"
export TOKEN_TTL_MIN=360

# 4) Démarrer l’API
python app.py
# L’API écoute sur http://127.0.0.1:5000

```
---
### Identifiants de développement

Par défaut (configurés dans `backend/app.py`) :

- **admin / admin**
- **lotfi / admin**

> A changer pour utilisation future, sécurisé & robuste

---

### Servir le front (frontend)

Plusieurs options possibles :

### Python HTTP server
```
cd frontend
python -m http.server 5500
# Puis ouvrir http://127.0.0.1:5500/frontend/
```
## Utilisation (UI)

- Ouvrir l’interface : http://127.0.0.1:5500/frontend/.

- Se connecter : utilisez un identifiant de dev (voir plus haut).

- Base URL : dans la barre supérieure, entrez http://127.0.0.1:5000.

- Vérifier l’API : bouton “Check”.

- (Optionnel) Charger l’arbre : bouton “Charger l’arbre” (utile pour naviguer visuellement dans les thèmes, non requis pour les pickers).

- Requêtes CSR :

  - Choisir une requête dans la liste.

  - Renseigner les paramètres (grâce aux pickers).

  - Cliquer “Exécuter”.

## Pickers (sélection assistée)

- Ouverture : cliquer dans un champ ouvre un menu déroulant avec des suggestions (préchargé si possible).

- Recherche : taper des caractères filtre la liste.

- Navigation :

  - ↓ / ↑ pour surligner un élément / survoler avec la souris (hover)

  - Enter pour sélectionner / clic souris

  - Esc pour fermer / clic en dehors du champs

- Multi-sélection (thèmes) : les éléments choisis apparaissent sous forme d’étiquettes (chips) au-dessus du champ.

  - Cliquer sur × pour retirer un chip.

- Fermeture : clic à l’extérieur ou sélection d’un item.

- Champs concernés :

  - theme_ids, exclude_theme_ids → multi (chips)

  - root_theme_id, structure_id → simple (un seul choix)

  - person_id / idpers → simple, recherche par Nom/Prénom ou ID

- Les pickers appellent :

  - /api/themes/find?q= pour les thèmes

  - /api/people/find?q= pour les personnes

  - /api/structures/find?q= pour les structures
 
## API (aperçu)

Auth / santé

- POST /api/login → { access_token }

- GET /api/health

Thèmes

- GET /api/themes/tree → arbre à plat (pour l’UI)

- GET /api/themes/find?q= → suggestions

Personnes

- GET /api/people/find?q= → suggestions

- POST /api/people/search → recherche par filtres

Positionnements

- POST /api/positions → ajout MANU

- DELETE /api/positions → suppression MANU

- GET /api/stats/non_positionnes

Structures

- GET /api/structures/find?q=

CSR

- GET /api/queries → liste des requêtes

- POST /api/queries/<id> → exécution

Tous les endpoints (sauf /api/login et /api/health) attendent Authorization: Bearer <token>.

## Configuration

Variables lues par backend/app.py :

- SECRET_KEY (défaut dev) — à changer.

- TOKEN_TTL_MIN (défaut 60).

- FRONT_ORIGIN (défaut http://localhost:3000) — CORS : le projet autorise * pour /api/*.

Connexion base : adapter backend/db.py (DSN, user/pass, etc.).

## Quick tests (cURL)
```
# 1) Login
TOKEN=$(curl -s http://127.0.0.1:5000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"lotfi","password":"admin"}' | jq -r .access_token)

# 2) Ping
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5000/api/health

# 3) Themes suggestions
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5000/api/themes/find?q="

```

## Dépannage

- Pas de liste dans les pickers :

  - Vérifiez que l’API est joignable (voir Ping /api/health).

  - Vérifiez que le token est valide (reconnectez-vous si 401).

- Arbre vide / Oracle :

  - Confirmez la connexion dans db.py.

  - Les requêtes utilisent CONNECT BY (Oracle) : base requise.

- CORS :

  - Le back expose les en-têtes et accepte Authorization (voir flask_cors.CORS dans app.py).

## Sécurité

- Les identifiants en dur (USERS) et la SECRET_KEY de dev ne doivent pas être utilisés pour le déploiement.


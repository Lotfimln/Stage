# API IRIT – Prototype Flask (Oracle thin)

## 1) Prérequis
- Python 3.10+ (idéalement)
- Oracle Database accessible (ex: XE sur localhost:1521/xe)
- Un schéma contenant PERSONNE, THEMES, POSITIONNEMENT (+ tes vues)
- Identifiants (par défaut LOTFI/admion)

## 2) Installation
cd PROTOTYPE
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
python run_dev.py


# (Optionnel) Copier .env.example en .env et ajuster ORACLE_USER / ORACLE_PASSWORD / ORACLE_DSN

## 3) Lancer
python app.py
# -> écoute sur http://127.0.0.1:8000

## 4) Tester
curl http://127.0.0.1:8000/health

curl http://127.0.0.1:8000/themes
curl http://127.0.0.1:8000/themes/tree

curl "http://127.0.0.1:8000/themes/1/people?include_auto=true"
curl http://127.0.0.1:8000/people/14811/positions

curl http://127.0.0.1:8000/structures
  
# -*- coding: utf-8 -*-
"""audit_data.py - Audit des fichiers CSV du prototype CSR IRIT."""
import csv
import os
import sys
import io

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────
def detect_encoding(filepath):
    """Try UTF-8, then latin-1 (always succeeds)."""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(filepath, encoding=enc) as f:
                f.read(4096)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "latin-1"


def load_csv(filename, delimiter=","):
    """Load a CSV and return (rows, encoding, issues)."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None, None, [f"FICHIER MANQUANT: {filename}"]

    enc = detect_encoding(path)
    issues = []
    rows = []

    # Check for encoding problems (mojibake)
    with open(path, encoding=enc) as f:
        raw = f.read()
    mojibake_markers = ["�", "Ã©", "Ã¨", "Ã ", "Ã§", "Ã´", "Ãª"]
    for marker in mojibake_markers:
        if marker in raw:
            issues.append(f"ENCODAGE: caractère suspect '{marker}' trouvé (mojibake probable)")
            break

    with open(path, encoding=enc, newline="") as f:
        # Handle the weird quoting in postion.csv
        try:
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                rows.append(row)
        except csv.Error as e:
            issues.append(f"CSV PARSE ERROR: {e}")

    return rows, enc, issues


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_ok(msg):
    print(f"  [OK] {msg}")


def print_warn(msg):
    print(f"  [WARN] {msg}")


def print_err(msg):
    print(f"  [ERR] {msg}")


def print_info(msg):
    print(f"  [INFO] {msg}")


# ────────────────────────────────────────────────────────
# Audit: Themes.csv (source principale)
# ────────────────────────────────────────────────────────
def audit_themes_csv():
    print_section("THEMES.CSV (source principale)")

    rows, enc, issues = load_csv("Themes.csv")
    if rows is None:
        print_err(issues[0])
        return {}, set()

    print_info(f"Encodage détecté: {enc}")
    print_info(f"Lignes totales: {len(rows)} (dont 1 en-tête)")

    header = rows[0]
    print_info(f"Colonnes: {header}")
    data = rows[1:]

    # Parse
    themes = {}
    parent_refs = set()
    dup_ids = []
    bad_rows = []

    for i, row in enumerate(data, start=2):
        if len(row) < 4:
            bad_rows.append((i, row))
            continue
        try:
            tid = int(row[0])
            label = row[1].strip()
            niveau = int(row[2]) if row[2].strip() else None
            parent = int(row[3]) if row[3].strip() else None
        except (ValueError, IndexError) as e:
            bad_rows.append((i, row, str(e)))
            continue

        if tid in themes:
            dup_ids.append(tid)
        themes[tid] = {"label": label, "niveau": niveau, "parent": parent}
        if parent is not None:
            parent_refs.add(parent)

    print_info(f"Thèmes uniques: {len(themes)}")
    print_info(f"Racines (niveau 0, sans parent): {sum(1 for t in themes.values() if t['parent'] is None)}")

    # Check orphan parents
    orphan_parents = parent_refs - set(themes.keys())
    if orphan_parents:
        print_err(f"Parents orphelins (référencés mais inexistants): {orphan_parents}")
    else:
        print_ok("Tous les parents référencés existent")

    if dup_ids:
        print_warn(f"IDs dupliqués: {dup_ids}")
    else:
        print_ok("Pas d'IDs dupliqués")

    if bad_rows:
        print_warn(f"Lignes malformées: {len(bad_rows)}")
        for br in bad_rows[:5]:
            print(f"      Ligne {br[0]}: {br[1:]}")
    else:
        print_ok("Toutes les lignes sont bien formées")

    for issue in issues:
        print_warn(issue)

    return themes, set(themes.keys())


# ────────────────────────────────────────────────────────
# Audit: theme.csv (ancien format)
# ────────────────────────────────────────────────────────
def audit_theme_csv_old(themes_ids):
    print_section("THEME.CSV (ancien format)")

    rows, enc, issues = load_csv("theme.csv")
    if rows is None:
        print_err(issues[0])
        return

    print_info(f"Encodage détecté: {enc}")
    print_info(f"Lignes totales: {len(rows)} (dont 1 en-tête)")

    header = rows[0]
    print_info(f"Colonnes: {header}")

    # Check for duplicate columns
    col_counts = Counter(header)
    dups = {k: v for k, v in col_counts.items() if v > 1}
    if dups:
        print_warn(f"Colonnes dupliquées: {dups}")

    data = rows[1:]
    old_ids = set()
    for row in data:
        try:
            old_ids.add(int(row[0]))
        except (ValueError, IndexError):
            pass

    print_info(f"IDs uniques: {len(old_ids)}")

    # Compare with Themes.csv
    only_old = old_ids - themes_ids
    only_new = themes_ids - old_ids
    if only_old:
        print_warn(f"IDs dans theme.csv mais PAS dans Themes.csv: {len(only_old)} ({list(only_old)[:10]}...)")
    if only_new:
        print_warn(f"IDs dans Themes.csv mais PAS dans theme.csv: {len(only_new)} ({list(only_new)[:10]}...)")
    if not only_old and not only_new:
        print_ok("Les deux fichiers couvrent exactement les mêmes IDs")

    for issue in issues:
        print_warn(issue)


# ────────────────────────────────────────────────────────
# Audit: postion.csv (positionnements)
# ────────────────────────────────────────────────────────
def audit_positions():
    print_section("POSTION.CSV (positionnements)")

    path = os.path.join(DATA_DIR, "postion.csv")
    enc = detect_encoding(path)
    print_info(f"Encodage détecté: {enc}")

    # This file has a weird format: first line is header with ;
    # subsequent lines are quoted with nested double-quotes
    issues = []
    rows = []
    person_ids = set()
    theme_ids_used = set()
    structure_ids = set()

    with open(path, encoding=enc) as f:
        lines = f.readlines()

    print_info(f"Lignes totales: {len(lines)} (dont 1 en-tête)")

    # Parse header
    header_line = lines[0].strip().rstrip(";")
    header = header_line.split(",")
    print_info(f"Colonnes ({len(header)}): {header}")

    # Parse data lines (complex quoting)
    parse_errors = 0
    roles = Counter()
    temporalites = Counter()
    auto_genere_vals = Counter()

    for i, line in enumerate(lines[1:], start=2):
        line = line.strip().rstrip(";")
        if not line:
            continue

        # Remove outer quotes if present
        if line.startswith('"') and line.endswith('"'):
            line = line[1:-1]

        # Split by ,"" pattern (columns separated by comma + double-double-quotes)
        parts = line.split(',""')
        cleaned = []
        for p in parts:
            p = p.strip('"').strip()
            cleaned.append(p)

        if len(cleaned) < 7:
            parse_errors += 1
            if parse_errors <= 3:
                print_warn(f"  Ligne {i}: {len(cleaned)} colonnes (attendu 13): {cleaned[:5]}...")
            continue

        try:
            pid = int(cleaned[0])
            person_ids.add(pid)
        except ValueError:
            pass

        # LIBCONTRIBUTION (index 2)
        if len(cleaned) > 2:
            roles[cleaned[2]] += 1

        # LIBELLETEMPORALITE (index 4)
        if len(cleaned) > 4:
            temporalites[cleaned[4]] += 1

        # IDTHEME (index 5)
        if len(cleaned) > 5:
            try:
                theme_ids_used.add(int(cleaned[5]))
            except ValueError:
                pass

        # IDSTRUCTURE (index 7)
        if len(cleaned) > 7:
            try:
                sid = int(cleaned[7])
                structure_ids.add(sid)
            except ValueError:
                pass

        rows.append(cleaned)

    print_info(f"Lignes parsées avec succès: {len(rows)}")
    if parse_errors:
        print_warn(f"Erreurs de parsing: {parse_errors}")

    print_info(f"Personnes uniques: {len(person_ids)}")
    print_info(f"Thèmes référencés: {len(theme_ids_used)}")
    print_info(f"Structures uniques: {len(structure_ids)}")

    print_info(f"Rôles: {dict(roles)}")
    print_info(f"Temporalités: {dict(temporalites)}")

    # Check encoding issues in temporalites
    for t in temporalites:
        if "?" in t or "�" in t or "Ã" in t:
            print_err(f"ENCODAGE CASSÉ dans temporalité: '{t}' (devrait être 'Présent' ou 'Passé')")

    # Check for mojibake in all data
    mojibake_count = sum(1 for row in rows for cell in row if "�" in cell or "Ã©" in cell)
    if mojibake_count:
        print_err(f"Cellules avec mojibake: {mojibake_count}")
    else:
        print_ok("Pas de mojibake détecté dans les données parsées")

    for issue in issues:
        print_warn(issue)

    return person_ids, theme_ids_used, structure_ids


# ────────────────────────────────────────────────────────
# Audit: Contributions.csv (personnes + contributions)
# ────────────────────────────────────────────────────────
def audit_contributions(theme_ids_master):
    print_section("CONTRIBUTIONS.CSV")

    rows, enc, issues = load_csv("Contributions.csv")
    if rows is None:
        print_err(issues[0])
        return set()

    print_info(f"Encodage détecté: {enc}")
    print_info(f"Lignes totales: {len(rows)} (dont 1 en-tête)")

    header = rows[0]
    print_info(f"Colonnes: {header}")
    data = rows[1:]

    persons = {}
    theme_refs = set()
    contrib_types = Counter()

    for row in data:
        if len(row) < 5:
            continue
        try:
            pid = int(row[0])
            nom = row[1].strip()
            prenom = row[2].strip()
            theme_code = int(row[3])
            type_contrib = row[4].strip()
        except (ValueError, IndexError):
            continue

        persons[pid] = {"nom": nom, "prenom": prenom}
        theme_refs.add(theme_code)
        contrib_types[type_contrib] += 1

    print_info(f"Personnes uniques: {len(persons)}")
    print_info(f"Thèmes référencés: {len(theme_refs)}")
    print_info(f"Types de contribution: {dict(contrib_types)}")

    # Check encoding of person names
    mojibake_names = [p for p in persons.values() if "�" in p["nom"] or "�" in p["prenom"]]
    if mojibake_names:
        print_err(f"Noms avec encodage cassé: {len(mojibake_names)}")
        for p in mojibake_names[:5]:
            print(f"      {p['nom']} {p['prenom']}")
    else:
        print_ok("Noms correctement encodés (ou latin-1 récupérable)")

    # Themes referenced but not in master
    missing = theme_refs - theme_ids_master
    if missing:
        print_warn(f"Thèmes dans Contributions mais absents de Themes.csv: {missing}")
    else:
        print_ok("Tous les thèmes référencés existent dans Themes.csv")

    for issue in issues:
        print_warn(issue)

    return set(persons.keys())


# ────────────────────────────────────────────────────────
# Cross-file integrity
# ────────────────────────────────────────────────────────
def cross_check(themes, theme_ids, pos_person_ids, pos_theme_ids, contrib_person_ids):
    print_section("VÉRIFICATION CROISÉE")

    # Themes in positions but not in master
    orphan_themes = pos_theme_ids - theme_ids
    if orphan_themes:
        print_warn(f"Thèmes dans Positions mais pas dans Themes.csv: {orphan_themes}")
    else:
        print_ok("Tous les thèmes de Positions existent dans Themes.csv")

    # Persons in positions but not in contributions
    orphan_persons = pos_person_ids - contrib_person_ids
    if orphan_persons:
        print_warn(f"Personnes dans Positions mais pas dans Contributions: {len(orphan_persons)} (ex: {list(orphan_persons)[:10]})")
    else:
        print_ok("Toutes les personnes de Positions sont dans Contributions")

    # Persons in contributions but not in positions
    extra_persons = contrib_person_ids - pos_person_ids
    if extra_persons:
        print_info(f"Personnes dans Contributions mais pas dans Positions: {len(extra_persons)} (peuvent être non-positionnées)")

    # Unused themes
    unused_themes = theme_ids - pos_theme_ids
    if unused_themes:
        print_info(f"Thèmes sans aucun positionnement: {len(unused_themes)}/{len(theme_ids)} ({100*len(unused_themes)//len(theme_ids)}%)")

    # Coverage stats
    print_section("STATISTIQUES DE COUVERTURE")
    print_info(f"Personnes positionnées: {len(pos_person_ids)}")
    print_info(f"Personnes dans Contributions: {len(contrib_person_ids)}")
    all_persons = pos_person_ids | contrib_person_ids
    print_info(f"Personnes totales (union): {len(all_persons)}")
    print_info(f"Thèmes dans le référentiel: {len(theme_ids)}")
    print_info(f"Thèmes utilisés (positionnements): {len(pos_theme_ids)}")
    coverage = 100 * len(pos_theme_ids) / len(theme_ids) if theme_ids else 0
    print_info(f"Couverture thématique: {coverage:.1f}%")


# ────────────────────────────────────────────────────────
# File inventory
# ────────────────────────────────────────────────────────
def audit_file_inventory():
    print_section("INVENTAIRE DES FICHIERS")
    files = os.listdir(DATA_DIR)
    for f in sorted(files):
        fp = os.path.join(DATA_DIR, f)
        size = os.path.getsize(fp)
        enc = detect_encoding(fp) if f.endswith(".csv") else "N/A"
        print_info(f"{f:25s}  {size:>10,} octets  enc={enc}")

    # Flag duplicates
    if "theme.csv" in files and "Themes.csv" in files:
        print_warn("DOUBLON PROBABLE: theme.csv ET Themes.csv (2 formats du thésaurus)")
    if "postion.csv" in files:
        print_warn("TYPO: 'postion.csv' devrait être 'position.csv'")


# ────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────
def main():
    print("\n" + "="*60)
    print("  AUDIT DES DONNEES - PROTOTYPE CSR IRIT")
    print("="*60)

    audit_file_inventory()
    themes, theme_ids = audit_themes_csv()
    audit_theme_csv_old(theme_ids)
    pos_pids, pos_tids, pos_sids = audit_positions()
    contrib_pids = audit_contributions(theme_ids)
    cross_check(themes, theme_ids, pos_pids, pos_tids, contrib_pids)

    print("\n" + "═"*60)
    print("  AUDIT TERMINÉ")
    print("═"*60 + "\n")


if __name__ == "__main__":
    main()

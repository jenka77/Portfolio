#!/usr/bin/env python3
"""
Export portfolio.db -> projects.json (ecrase le fichier JSON).

Attention: si vous avez modifie projects.json a la main, n'utilisez PAS ce script
(sinon vos changements seront perdus). Utilisez plutot:
  python3 import_projects.py
"""
import json
import shutil
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"
OUT_PATH = BASE_DIR / "projects.json"


def _count_json_projects(path):
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return len(data) if isinstance(data, list) else 0
    except (json.JSONDecodeError, OSError):
        return 0


def export_projects_to_json(db_path=DB_PATH, out_path=OUT_PATH, force=False):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
        if "video_url" not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN video_url TEXT DEFAULT ''")
            conn.commit()
        rows = conn.execute(
            """
            SELECT id, title, description, link, demo_url, video_url, github_url,
                   image_src, image_data_url, uploaded_at
            FROM projects
            ORDER BY datetime(uploaded_at) DESC
            """
        ).fetchall()
        projects = [dict(row) for row in rows]
        db_count = len(projects)
    finally:
        conn.close()

    json_count = _count_json_projects(out_path)
    if not force and json_count > db_count:
        print(
            f"Abbruch: projects.json hat {json_count} Projekt(e), "
            f"portfolio.db nur {db_count}.\n"
            "Vos modifications sont probablement dans le JSON. Lancez:\n"
            "  python3 import_projects.py\n"
            "Ou forcez l'export (ecrase le JSON): python3 export_projects.py --force",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if out_path.is_file():
        shutil.copy2(out_path, out_path.with_suffix(".json.bak"))

    out_path.write_text(
        json.dumps(projects, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return len(projects)


def export_projects(force=False):
    count = export_projects_to_json(force=force)
    print(
        f"Exported {count} project(s) from portfolio.db to {OUT_PATH} "
        f"(ancien fichier sauve dans projects.json.bak si present)."
    )


if __name__ == "__main__":
    export_projects(force="--force" in sys.argv)

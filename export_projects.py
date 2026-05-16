#!/usr/bin/env python3
"""Export projects from portfolio.db to projects.json (for GitHub Pages)."""
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"
OUT_PATH = BASE_DIR / "projects.json"


def export_projects():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, title, description, link, demo_url, github_url,
                   image_src, image_data_url, uploaded_at
            FROM projects
            ORDER BY datetime(uploaded_at) DESC
            """
        ).fetchall()
        projects = [dict(row) for row in rows]
    finally:
        conn.close()

    OUT_PATH.write_text(
        json.dumps(projects, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Exported {len(projects)} project(s) to {OUT_PATH}")


if __name__ == "__main__":
    export_projects()

#!/usr/bin/env python3
"""Import projects from projects.json into portfolio.db (inverse of export)."""
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"
IN_PATH = BASE_DIR / "projects.json"


def import_projects_from_json(json_path=IN_PATH, db_path=DB_PATH):
    if not json_path.is_file():
        raise FileNotFoundError(f"{json_path} introuvable.")

    raw = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("projects.json doit etre un tableau JSON.")

    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
        if "video_url" not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN video_url TEXT DEFAULT ''")
        conn.execute("DELETE FROM projects")
        for project in raw:
            if not isinstance(project, dict):
                continue
            title = str(project.get("title", "")).strip()
            description = str(project.get("description", "")).strip()
            if not title or not description:
                continue
            conn.execute(
                """
                INSERT INTO projects (
                    title, description, link, demo_url, video_url, github_url,
                    image_src, image_data_url, uploaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    description,
                    str(project.get("link", "")).strip(),
                    str(project.get("demo_url", project.get("demoUrl", ""))).strip(),
                    str(project.get("video_url", project.get("videoUrl", ""))).strip(),
                    str(project.get("github_url", project.get("githubUrl", ""))).strip(),
                    str(project.get("image_src", project.get("imageSrc", ""))).strip(),
                    str(project.get("image_data_url", project.get("imageDataUrl", ""))).strip(),
                    str(
                        project.get("uploaded_at", project.get("uploadedAt", ""))
                    ).strip()
                    or "1970-01-01T00:00:00.000Z",
                ),
            )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    finally:
        conn.close()

    return count


def import_projects():
    count = import_projects_from_json()
    print(f"Imported {count} project(s) from {IN_PATH} into {DB_PATH}")


if __name__ == "__main__":
    import_projects()

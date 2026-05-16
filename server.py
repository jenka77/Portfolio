#!/usr/bin/env python3
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from export_projects import export_projects_to_json


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"
SESSION_COOKIE = "portfolio_session"
SESSION_TTL_SECONDS = 60 * 60 * 8
PORT = int(os.environ.get("PORT", "8000"))

ALLOWED_EMAILS = {
    "karelletchatchouang@gmail.com",
    "jenny.karelle.nanseu.tchatchouang@mni.thm.de",
}
ADMIN_PASSWORD = os.environ.get("PORTFOLIO_ADMIN_PASSWORD", "ChangeMeNow123!")

SESSIONS = {}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sync_projects_json():
    try:
        export_projects_to_json(force=True)
    except (OSError, SystemExit):
        pass


def init_db():
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                link TEXT DEFAULT '',
                demo_url TEXT DEFAULT '',
                github_url TEXT DEFAULT '',
                image_src TEXT DEFAULT '',
                image_data_url TEXT DEFAULT '',
                uploaded_at TEXT NOT NULL
            )
            """
        )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
        if "demo_url" not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN demo_url TEXT DEFAULT ''")
        if "github_url" not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN github_url TEXT DEFAULT ''")
        for wrong, fixed in (
            ("portofoliobild.jpeg", "webart.jpg"),
            (
                "WhatsApp Image 2026-05-09 at 09.23.21.jpeg",
                "Bildschirmfoto_vom_2026-05-10_13-27-18-removebg-preview.png",
            ),
        ):
            conn.execute(
                "UPDATE projects SET image_src = ? WHERE image_src = ?",
                (fixed, wrong),
            )
        count = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
        if count == 0:
            seed_projects = [
                (
                    "Projekt 01 - Portfolio Website",
                    "Eine responsive Website mit modernem Design zur Prasentation meiner Person und meiner Arbeiten.",
                    "",
                    "",
                    "",
                    "portofolio.jpeg",
                    "",
                    "2026-05-01T08:00:00.000Z",
                ),
                (
                    "Projekt 02 - Lernprojekt",
                    "Entwicklung eines kleinen Tools, um praktische Erfahrung in HTML, CSS und JavaScript zu vertiefen.",
                    "",
                    "",
                    "",
                    "webart.jpg",
                    "",
                    "2026-04-20T09:30:00.000Z",
                ),
                (
                    "Projekt 03 - Teamarbeit",
                    "Zusammenarbeit in einem kleinen Team mit Fokus auf Planung, Kommunikation und sauberer Umsetzung.",
                    "",
                    "",
                    "",
                    "Bildschirmfoto_vom_2026-05-10_13-27-18-removebg-preview.png",
                    "",
                    "2026-03-28T15:45:00.000Z",
                ),
            ]
            conn.executemany(
                """
                INSERT INTO projects (title, description, link, demo_url, github_url,
                                      image_src, image_data_url, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                seed_projects,
            )
        conn.commit()
    finally:
        conn.close()


class PortfolioHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _get_session_token(self):
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        jar = cookies.SimpleCookie()
        jar.load(cookie_header)
        entry = jar.get(SESSION_COOKIE)
        return entry.value if entry else None

    def _get_current_user(self):
        token = self._get_session_token()
        if not token:
            return None
        session = SESSIONS.get(token)
        if not session:
            return None
        if session["expires_at"] < time.time():
            SESSIONS.pop(token, None)
            return None
        return session["email"]

    def _set_session_cookie(self, token):
        jar = cookies.SimpleCookie()
        jar[SESSION_COOKIE] = token
        jar[SESSION_COOKIE]["path"] = "/"
        jar[SESSION_COOKIE]["httponly"] = True
        jar[SESSION_COOKIE]["samesite"] = "Lax"
        self.send_header("Set-Cookie", jar.output(header="").strip())

    def _clear_session_cookie(self):
        jar = cookies.SimpleCookie()
        jar[SESSION_COOKIE] = ""
        jar[SESSION_COOKIE]["path"] = "/"
        jar[SESSION_COOKIE]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        self.send_header("Set-Cookie", jar.output(header="").strip())

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/projects":
            conn = get_db()
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
                self._json(200, {"projects": projects})
            except sqlite3.Error as exc:
                self._json(500, {"error": "Datenbankfehler.", "detail": str(exc)})
            finally:
                conn.close()
            return

        if parsed.path == "/api/me":
            email = self._get_current_user()
            self._json(200, {"authenticated": bool(email), "email": email})
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/login":
            try:
                payload = self._read_json_body()
            except json.JSONDecodeError:
                self._json(400, {"error": "Ungultige JSON-Daten."})
                return

            email = str(payload.get("email", "")).strip().lower()
            password = str(payload.get("password", ""))

            if email not in ALLOWED_EMAILS:
                self._json(403, {"error": "Diese E-Mail ist nicht autorisiert."})
                return
            if password != ADMIN_PASSWORD:
                self._json(401, {"error": "Falsches Passwort."})
                return

            token = secrets.token_urlsafe(32)
            SESSIONS[token] = {
                "email": email,
                "expires_at": time.time() + SESSION_TTL_SECONDS,
            }

            self.send_response(200)
            self._set_session_cookie(token)
            body = json.dumps({"ok": True, "email": email}).encode("utf-8")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/logout":
            token = self._get_session_token()
            if token:
                SESSIONS.pop(token, None)
            self.send_response(200)
            self._clear_session_cookie()
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/projects":
            email = self._get_current_user()
            if not email:
                self._json(401, {"error": "Nicht angemeldet."})
                return
            try:
                payload = self._read_json_body()
            except json.JSONDecodeError:
                self._json(400, {"error": "Ungultige JSON-Daten."})
                return

            title = str(payload.get("title", "")).strip()
            description = str(payload.get("description", "")).strip()
            link = str(payload.get("link", "")).strip()
            demo_url = str(payload.get("demoUrl", "")).strip()
            github_url = str(payload.get("githubUrl", "")).strip()
            image_src = str(payload.get("imageSrc", "")).strip()
            image_data_url = str(payload.get("imageDataUrl", "")).strip()

            if not title or not description:
                self._json(400, {"error": "Titel und Beschreibung sind erforderlich."})
                return

            conn = get_db()
            try:
                conn.execute(
                    """
                    INSERT INTO projects (title, description, link, demo_url, github_url,
                                          image_src, image_data_url, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        description,
                        link,
                        demo_url,
                        github_url,
                        image_src,
                        image_data_url,
                        now_iso(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            sync_projects_json()
            self._json(201, {"ok": True})
            return

        self._json(404, {"error": "Not found"})
        return

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/projects":
            self.send_error(404, "Not Found")
            return
        email = self._get_current_user()
        if not email:
            self._json(401, {"error": "Nicht angemeldet."})
            return
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self._json(400, {"error": "Ungultige JSON-Daten."})
            return
        try:
            project_id = int(payload.get("id"))
        except (TypeError, ValueError):
            self._json(400, {"error": "Ungultige Projekt-ID."})
            return

        title = str(payload.get("title", "")).strip()
        description = str(payload.get("description", "")).strip()
        link = str(payload.get("link", "")).strip()
        demo_url = str(payload.get("demoUrl", "")).strip()
        github_url = str(payload.get("githubUrl", "")).strip()
        image_src = str(payload.get("imageSrc", "")).strip()
        image_data_url = str(payload.get("imageDataUrl", "")).strip()

        if not title or not description:
            self._json(400, {"error": "Titel und Beschreibung sind erforderlich."})
            return

        conn = get_db()
        try:
            cur = conn.execute(
                """
                UPDATE projects
                SET title = ?, description = ?, link = ?, demo_url = ?, github_url = ?,
                    image_src = ?, image_data_url = ?
                WHERE id = ?
                """,
                (
                    title,
                    description,
                    link,
                    demo_url,
                    github_url,
                    image_src,
                    image_data_url,
                    project_id,
                ),
            )
            if cur.rowcount == 0:
                self._json(404, {"error": "Projekt nicht gefunden."})
                return
            conn.commit()
        finally:
            conn.close()

        sync_projects_json()
        self._json(200, {"ok": True})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/projects":
            self.send_error(404, "Not Found")
            return
        email = self._get_current_user()
        if not email:
            self._json(401, {"error": "Nicht angemeldet."})
            return
        qs = parse_qs(parsed.query)
        id_raw = (qs.get("id") or [None])[0]
        try:
            project_id = int(id_raw)
        except (TypeError, ValueError):
            self._json(400, {"error": "Ungultige Projekt-ID."})
            return

        conn = get_db()
        try:
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            if cur.rowcount == 0:
                self._json(404, {"error": "Projekt nicht gefunden."})
                return
            conn.commit()
        finally:
            conn.close()

        sync_projects_json()
        self._json(200, {"ok": True})


if __name__ == "__main__":
    init_db()
    print(f"Portfolio server running on http://localhost:{PORT}")
    print("Set PORTFOLIO_ADMIN_PASSWORD env variable before start for production.")
    ThreadingHTTPServer(("0.0.0.0", PORT), PortfolioHandler).serve_forever()

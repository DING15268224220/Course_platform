from __future__ import annotations

import csv
import hashlib
import io
import json
import mimetypes
import os
import secrets
import sqlite3
import statistics
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template, request, send_file, session
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent           # backend/
PROJECT_ROOT = BASE_DIR.parent                       # 项目根目录
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
FRONTEND_DIR = RESOURCE_DIR / "frontend"
DATA_DIR = Path(os.environ.get("PLATFORM_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = BASE_DIR / "uploads"
if os.environ.get("PLATFORM_DATA_DIR"):
    UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "platform.db"
ALLOWED_EXTENSIONS = {"pdf", "zip", "mp4"}
ALLOWED_MIME_TYPES = {
    "pdf": {"application/pdf", "application/octet-stream"},
    "zip": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
    "mp4": {"video/mp4", "application/octet-stream"},
}
DEMO_PASSWORD = os.environ.get("PLATFORM_DEMO_PASSWORD", "123456")
PLATFORM_VERSION = "4.0.0"


def load_secret_key() -> str:
    configured = os.environ.get("PLATFORM_SECRET_KEY")
    if configured:
        return configured
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    secret_file = DATA_DIR / ".secret-key"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    value = secrets.token_hex(32)
    secret_file.write_text(value, encoding="utf-8")
    return value

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR),
    static_folder=str(FRONTEND_DIR),
    static_url_path="/static",
)
app.config.update(
    MAX_CONTENT_LENGTH=200 * 1024 * 1024,
    JSON_AS_ASCII=False,
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("PLATFORM_HTTPS", "0") == "1",
    DEMO_MODE=os.environ.get("PLATFORM_DEMO_MODE", "1") == "1",
)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def rows(query: str, params=()):
    return [dict(row) for row in get_db().execute(query, params).fetchall()]


def row(query: str, params=()):
    result = get_db().execute(query, params).fetchone()
    return dict(result) if result else None


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


class APIError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def current_user():
    user_id = session.get("user_id")
    if app.config.get("TESTING") and request.headers.get("X-User-Id"):
        user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise APIError("请先登录", 401)
    user = row("SELECT id,name,role,active FROM users WHERE id = ?", (user_id,))
    if not user or not user.get("active", 1):
        session.clear()
        raise APIError("登录状态已失效，请重新登录", 401)
    return user


def abort_json(message: str, status: int = 400):
    response = jsonify({"ok": False, "message": message})
    response.status_code = status
    return response


def require_role(*roles):
    user = current_user()
    if user["role"] not in roles:
        return None, abort_json("当前角色无权执行此操作", 403)
    return user, None


def selected_project(project_id: int, user=None):
    user = user or current_user()
    project = row(
        """SELECT p.*,c.name AS course_name,c.term,c.teacher_id
           FROM projects p JOIN courses c ON c.id=p.course_id WHERE p.id=?""",
        (project_id,),
    )
    if not project:
        raise APIError("项目不存在", 404)
    if user["role"] == "admin":
        allowed = True
    elif user["role"] == "teacher":
        allowed = project["teacher_id"] == user["id"]
    else:
        allowed = bool(row("SELECT 1 FROM course_members WHERE course_id=? AND user_id=?", (project["course_id"], user["id"])))
    if not allowed:
        raise APIError("无权访问该课程项目", 403)
    return project


def team_size(team_id: int) -> int:
    return int(row("SELECT COUNT(*) AS n FROM team_members WHERE team_id=?", (team_id,))["n"])


def ensure_team_ready(team_id: int):
    size = team_size(team_id)
    if size < 3 or size > 5:
        raise APIError(f"团队当前为 {size} 人，达到 3—5 人后才能执行此操作")


def parse_score(value, label="评分") -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        raise APIError(f"{label}必须是数字")
    if not 0 <= score <= 100:
        raise APIError(f"{label}应为 0—100")
    return score


PUBLIC_API_PATHS = {"/api/health", "/api/demo-users", "/api/login", "/api/session"}


@app.before_request
def protect_api():
    if not request.path.startswith("/api/") or request.path in PUBLIC_API_PATHS:
        return None
    current_user()
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if app.config.get("TESTING") and request.headers.get("X-User-Id"):
            return None
        if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session.get("csrf_token", "")):
            raise APIError("安全校验失败，请刷新页面后重试", 403)
    return None


def audit(user_id: str, action: str, entity: str, entity_id: str, detail: str, project_id=None):
    db = get_db()
    created_at = now_iso()
    previous = db.execute("SELECT entry_hash FROM audit_logs WHERE entry_hash IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    previous_hash = previous[0] if previous else "GENESIS"
    payload = "|".join(str(item) for item in (previous_hash, user_id, action, entity, entity_id, detail, created_at, project_id or ""))
    entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    db.execute(
        """INSERT INTO audit_logs(
               user_id,action,entity,entity_id,detail,created_at,project_id,previous_hash,entry_hash
           ) VALUES(?,?,?,?,?,?,?,?,?)""",
        (user_id, action, entity, str(entity_id), detail, created_at, project_id, previous_hash, entry_hash),
    )


def verify_audit_chain():
    entries = rows(
        """SELECT id,user_id,action,entity,entity_id,detail,created_at,project_id,previous_hash,entry_hash
           FROM audit_logs WHERE entry_hash IS NOT NULL ORDER BY id"""
    )
    previous_hash = "GENESIS"
    for entry in entries:
        if entry["previous_hash"] != previous_hash:
            return False, entry["id"]
        payload = "|".join(
            str(item)
            for item in (
                previous_hash, entry["user_id"], entry["action"], entry["entity"], entry["entity_id"],
                entry["detail"], entry["created_at"], entry["project_id"] or "",
            )
        )
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(expected, entry["entry_hash"]):
            return False, entry["id"]
        previous_hash = entry["entry_hash"]
    return True, None


def notify(user_id: str, title: str, content: str, kind="info", target_page="overview"):
    get_db().execute(
        "INSERT INTO notifications(user_id, title, content, is_read, created_at, kind, target_page) VALUES(?,?,?,?,?,?,?)",
        (user_id, title, content, 0, now_iso(), kind, target_page),
    )


def parse_deadline(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def file_matches_extension(path: Path, extension: str) -> bool:
    with path.open("rb") as handle:
        header = handle.read(16)
    if extension == "pdf":
        return header.startswith(b"%PDF-")
    if extension == "zip":
        return header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    if extension == "mp4":
        return len(header) >= 12 and header[4:8] == b"ftyp"
    return False


def ensure_column(db: sqlite3.Connection, table: str, name: str, definition: str):
    if name not in {item[1] for item in db.execute(f"PRAGMA table_info({table})").fetchall()}:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def active_publication(project_id: int):
    return row(
        "SELECT * FROM grade_publications WHERE project_id=? AND active=1 ORDER BY version DESC,id DESC LIMIT 1",
        (project_id,),
    )


def ensure_project_writable(project_id: int):
    project = row("SELECT grades_published FROM projects WHERE id=?", (project_id,))
    if not project:
        raise APIError("项目不存在", 404)
    if project["grades_published"]:
        raise APIError("成绩已发布，项目已进入只读归档状态", 403)


def notify_once(event_key: str, user_id: str, title: str, content: str, kind="info", target_page="overview"):
    db = get_db()
    inserted = db.execute(
        "INSERT OR IGNORE INTO notification_events(event_key,created_at) VALUES(?,?)",
        (event_key, now_iso()),
    )
    if inserted.rowcount:
        notify(user_id, title, content, kind, target_page)


def sync_deadline_notifications(user):
    if user["role"] == "admin":
        projects = rows("SELECT p.* FROM projects p WHERE p.status='published' AND p.grades_published=0")
    elif user["role"] == "teacher":
        projects = rows(
            """SELECT p.* FROM projects p JOIN courses c ON c.id=p.course_id
               WHERE c.teacher_id=? AND p.status='published' AND p.grades_published=0""",
            (user["id"],),
        )
    else:
        projects = rows(
            """SELECT p.* FROM projects p JOIN course_members cm ON cm.course_id=p.course_id
               WHERE cm.user_id=? AND p.status='published' AND p.grades_published=0""",
            (user["id"],),
        )
    now = datetime.now()
    for project in projects:
        deadlines = [
            ("team", "组队截止", project["team_deadline"], "teams"),
            ("review", "互评截止", project.get("review_deadline"), "reviews"),
            ("overall", "项目截止", project["overall_deadline"], "submissions"),
        ]
        for kind, label, value, page in deadlines:
            if not value:
                continue
            try:
                deadline = parse_deadline(value)
            except ValueError:
                continue
            remaining = deadline - now
            if timedelta(0) < remaining <= timedelta(hours=24):
                notify_once(
                    f"deadline:{project['id']}:{kind}:24h:{user['id']}", user["id"],
                    f"{label}即将到期", f"项目“{project['title']}”将在 24 小时内到达{label}时间。",
                    "warning", page,
                )
            elif remaining <= timedelta(0):
                notify_once(
                    f"deadline:{project['id']}:{kind}:expired:{user['id']}", user["id"],
                    f"{label}已到期", f"项目“{project['title']}”的{label}时间已到。",
                    "warning", page,
                )
    get_db().commit()


def visible_join_requests(project_id: int, user):
    if user["role"] in ("teacher", "admin"):
        return rows(
            """SELECT r.*,t.name AS team_name,u.name AS user_name FROM team_join_requests r
               JOIN teams t ON t.id=r.team_id JOIN users u ON u.id=r.user_id
               WHERE t.project_id=? ORDER BY r.id DESC""",
            (project_id,),
        )
    if user["role"] == "student":
        leader_team = row(
            """SELECT t.id FROM teams t JOIN team_members tm ON tm.team_id=t.id
               WHERE t.project_id=? AND tm.user_id=? AND tm.is_leader=1""",
            (project_id, user["id"]),
        )
        if leader_team:
            return rows(
                """SELECT r.*,t.name AS team_name,u.name AS user_name FROM team_join_requests r
                   JOIN teams t ON t.id=r.team_id JOIN users u ON u.id=r.user_id
                   WHERE r.team_id=? ORDER BY r.id DESC""",
                (leader_team["id"],),
            )
        return rows(
            """SELECT r.*,t.name AS team_name,u.name AS user_name FROM team_join_requests r
               JOIN teams t ON t.id=r.team_id JOIN users u ON u.id=r.user_id
               WHERE t.project_id=? AND r.user_id=? ORDER BY r.id DESC""",
            (project_id, user["id"]),
        )
    return []


def visible_member_tasks(project_id: int, user):
    base = """SELECT mt.*,i.name AS iteration_name,t.name AS team_name,u.name AS assignee_name
              FROM member_tasks mt JOIN iterations i ON i.id=mt.iteration_id
              JOIN teams t ON t.id=mt.team_id JOIN users u ON u.id=mt.assignee_id"""
    if user["role"] in ("teacher", "assistant", "admin"):
        return rows(base + " WHERE mt.project_id=? ORDER BY mt.due_at,mt.id", (project_id,))
    team = row(
        "SELECT t.id,tm.is_leader FROM teams t JOIN team_members tm ON tm.team_id=t.id WHERE t.project_id=? AND tm.user_id=?",
        (project_id, user["id"]),
    )
    if not team:
        return []
    if team["is_leader"]:
        return rows(base + " WHERE mt.project_id=? AND mt.team_id=? ORDER BY mt.due_at,mt.id", (project_id, team["id"]))
    return rows(base + " WHERE mt.project_id=? AND mt.assignee_id=? ORDER BY mt.due_at,mt.id", (project_id, user["id"]))


def visible_process_checks(project_id: int, user):
    base = """SELECT pc.*,i.name AS iteration_name,t.name AS team_name,u.name AS assistant_name
              FROM process_checks pc JOIN iterations i ON i.id=pc.iteration_id
              JOIN teams t ON t.id=pc.team_id JOIN users u ON u.id=pc.assistant_id"""
    if user["role"] in ("teacher", "assistant", "admin"):
        return rows(base + " WHERE pc.project_id=? ORDER BY pc.id DESC", (project_id,))
    team = row("SELECT t.id FROM teams t JOIN team_members tm ON tm.team_id=t.id WHERE t.project_id=? AND tm.user_id=?", (project_id, user["id"]))
    return rows(base + " WHERE pc.project_id=? AND pc.team_id=? ORDER BY pc.id DESC", (project_id, team["id"])) if team else []


def visible_grade_appeals(project_id: int, user):
    base = """SELECT ga.*,u.name AS user_name,r.name AS resolver_name FROM grade_appeals ga
              JOIN users u ON u.id=ga.user_id LEFT JOIN users r ON r.id=ga.resolved_by"""
    if user["role"] in ("teacher", "admin"):
        return rows(base + " WHERE ga.project_id=? ORDER BY ga.id DESC", (project_id,))
    if user["role"] == "student":
        return rows(base + " WHERE ga.project_id=? AND ga.user_id=? ORDER BY ga.id DESC", (project_id, user["id"]))
    return []


def refresh_process_score(project_id: int, team_id: int, assistant_id: str):
    scores = rows(
        "SELECT score FROM process_checks WHERE project_id=? AND team_id=? AND score IS NOT NULL AND action IN ('received','scored')",
        (project_id, team_id),
    )
    if not scores:
        return
    average = round(sum(float(item["score"]) for item in scores) / len(scores), 2)
    get_db().execute(
        """INSERT INTO process_scores(project_id,team_id,assistant_id,score,comment,updated_at)
           VALUES(?,?,?,?,?,?) ON CONFLICT(project_id,team_id) DO UPDATE SET
           assistant_id=excluded.assistant_id,score=excluded.score,comment=excluded.comment,updated_at=excluded.updated_at""",
        (project_id, team_id, assistant_id, average, f"按 {len(scores)} 次迭代过程检查取平均", now_iso()),
    )


def refresh_review_alert(project_id: int, target_team_id: int):
    scores = [
        float(item["score"])
        for item in rows(
            "SELECT score FROM peer_reviews WHERE project_id=? AND target_team_id=? AND status='submitted'",
            (project_id, target_team_id),
        )
    ]
    if len(scores) < 3:
        return
    deviation = statistics.pstdev(scores)
    if deviation <= 20:
        return
    if row(
        "SELECT 1 FROM review_alerts WHERE project_id=? AND target_team_id=? AND alert_type='high_deviation' AND status='open'",
        (project_id, target_team_id),
    ):
        return
    get_db().execute(
        """INSERT INTO review_alerts(project_id,target_team_id,alert_type,detail,status,created_at)
           VALUES(?,?, 'high_deviation',?, 'open',?)""",
        (project_id, target_team_id, f"互评分标准差为 {deviation:.2f}，疑似存在极端评分", now_iso()),
    )


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('teacher','assistant','student','admin')),
            password_hash TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT
        );
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            term TEXT NOT NULL,
            teacher_id TEXT NOT NULL REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS course_members (
            course_id INTEGER NOT NULL REFERENCES courses(id),
            user_id TEXT NOT NULL REFERENCES users(id),
            PRIMARY KEY(course_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL REFERENCES courses(id),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            team_deadline TEXT NOT NULL,
            overall_deadline TEXT NOT NULL,
            peer_weight REAL NOT NULL,
            process_weight REAL NOT NULL,
            final_weight REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'published',
            review_open INTEGER NOT NULL DEFAULT 0,
            grades_published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            review_deadline TEXT,
            published_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS iterations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            deadline TEXT NOT NULL,
            requirements TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'forming',
            created_at TEXT NOT NULL,
            UNIQUE(project_id, name)
        );
        CREATE TABLE IF NOT EXISTS team_members (
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id),
            is_leader INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(team_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            iteration_id INTEGER NOT NULL REFERENCES iterations(id) ON DELETE CASCADE,
            file_name TEXT NOT NULL,
            file_path TEXT,
            submitted_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'submitted',
            version INTEGER NOT NULL DEFAULT 1,
            lock_version INTEGER NOT NULL DEFAULT 1,
            returned_reason TEXT,
            received_at TEXT,
            received_by TEXT REFERENCES users(id),
            UNIQUE(team_id, iteration_id)
        );
        CREATE TABLE IF NOT EXISTS peer_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            reviewer_id TEXT NOT NULL REFERENCES users(id),
            target_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            completeness_score REAL,
            innovation_score REAL,
            documentation_score REAL,
            score REAL NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'submitted',
            UNIQUE(project_id, reviewer_id, target_team_id)
        );
        CREATE TABLE IF NOT EXISTS process_scores (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            assistant_id TEXT NOT NULL REFERENCES users(id),
            score REAL NOT NULL,
            comment TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(project_id, team_id)
        );
        CREATE TABLE IF NOT EXISTS final_scores (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            teacher_id TEXT NOT NULL REFERENCES users(id),
            score REAL NOT NULL,
            comment TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(project_id, team_id)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'info',
            target_page TEXT NOT NULL DEFAULT 'overview'
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL,
            project_id INTEGER REFERENCES projects(id),
            previous_hash TEXT,
            entry_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS submission_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT,
            submitted_at TEXT NOT NULL,
            UNIQUE(submission_id, version)
        );
        CREATE TABLE IF NOT EXISTS review_assignments (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            reviewer_id TEXT NOT NULL REFERENCES users(id),
            target_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            PRIMARY KEY(project_id, reviewer_id, target_team_id)
        );
        CREATE TABLE IF NOT EXISTS grade_publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            published_by TEXT NOT NULL REFERENCES users(id),
            published_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS individual_grade_adjustments (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id),
            coefficient REAL NOT NULL DEFAULT 1.0,
            manual_deduction REAL NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            updated_by TEXT NOT NULL REFERENCES users(id),
            updated_at TEXT NOT NULL,
            PRIMARY KEY(project_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS team_grade_snapshots (
            publication_id INTEGER NOT NULL REFERENCES grade_publications(id) ON DELETE CASCADE,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            team_name TEXT NOT NULL,
            peer_score REAL NOT NULL,
            peer_count INTEGER NOT NULL,
            process_score REAL NOT NULL,
            final_score REAL NOT NULL,
            total REAL NOT NULL,
            PRIMARY KEY(publication_id,team_id)
        );
        CREATE TABLE IF NOT EXISTS individual_grade_snapshots (
            publication_id INTEGER NOT NULL REFERENCES grade_publications(id) ON DELETE CASCADE,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            user_id TEXT NOT NULL REFERENCES users(id),
            user_name TEXT NOT NULL,
            peer_score REAL NOT NULL,
            coefficient REAL NOT NULL,
            manual_deduction REAL NOT NULL,
            missing_review_penalty REAL NOT NULL,
            final_score REAL NOT NULL,
            PRIMARY KEY(publication_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS team_join_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'pending',
            requested_at TEXT NOT NULL,
            decided_at TEXT,
            decided_by TEXT REFERENCES users(id),
            UNIQUE(team_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS member_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            iteration_id INTEGER NOT NULL REFERENCES iterations(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            assignee_id TEXT NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'todo',
            due_at TEXT NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS process_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            iteration_id INTEGER NOT NULL REFERENCES iterations(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            assistant_id TEXT NOT NULL REFERENCES users(id),
            action TEXT NOT NULL,
            score REAL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            target_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            alert_type TEXT NOT NULL,
            detail TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by TEXT REFERENCES users(id),
            resolution TEXT
        );
        CREATE TABLE IF NOT EXISTS grade_appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by TEXT REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS notification_events (
            event_key TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );
        """
    )
    ensure_column(db, "users", "password_hash", "TEXT")
    ensure_column(db, "users", "active", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(db, "users", "failed_attempts", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(db, "users", "locked_until", "TEXT")
    ensure_column(db, "projects", "review_deadline", "TEXT")
    ensure_column(db, "projects", "published_at", "TEXT")
    ensure_column(db, "projects", "updated_at", "TEXT")
    ensure_column(db, "notifications", "kind", "TEXT NOT NULL DEFAULT 'info'")
    ensure_column(db, "notifications", "target_page", "TEXT NOT NULL DEFAULT 'overview'")
    ensure_column(db, "audit_logs", "project_id", "INTEGER")
    ensure_column(db, "audit_logs", "previous_hash", "TEXT")
    ensure_column(db, "audit_logs", "entry_hash", "TEXT")
    ensure_column(db, "review_assignments", "assignment_key", "TEXT")
    ensure_column(db, "grade_publications", "active", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(db, "grade_publications", "withdrawn_at", "TEXT")
    ensure_column(db, "grade_publications", "withdrawn_by", "TEXT")
    ensure_column(db, "grade_publications", "withdrawal_reason", "TEXT")
    ensure_column(db, "submissions", "lock_version", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(db, "submissions", "returned_reason", "TEXT")
    ensure_column(db, "submissions", "received_at", "TEXT")
    ensure_column(db, "submissions", "received_by", "TEXT")
    ensure_column(db, "peer_reviews", "completeness_score", "REAL")
    ensure_column(db, "peer_reviews", "innovation_score", "REAL")
    ensure_column(db, "peer_reviews", "documentation_score", "REAL")
    ensure_column(db, "peer_reviews", "status", "TEXT NOT NULL DEFAULT 'submitted'")
    for assignment in db.execute(
        "SELECT project_id,reviewer_id,target_team_id FROM review_assignments WHERE assignment_key IS NULL OR assignment_key=''"
    ).fetchall():
        db.execute(
            "UPDATE review_assignments SET assignment_key=? WHERE project_id=? AND reviewer_id=? AND target_team_id=?",
            (uuid.uuid4().hex, assignment["project_id"], assignment["reviewer_id"], assignment["target_team_id"]),
        )
    db.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_teams_project ON teams(project_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_iteration ON submissions(iteration_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,is_read);
        CREATE INDEX IF NOT EXISTS idx_logs_project ON audit_logs(project_id,created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_review_assignment_key ON review_assignments(assignment_key);
        CREATE INDEX IF NOT EXISTS idx_grade_publications_active ON grade_publications(project_id,active,version);
        CREATE INDEX IF NOT EXISTS idx_join_requests_team ON team_join_requests(team_id,status);
        CREATE INDEX IF NOT EXISTS idx_member_tasks_assignee ON member_tasks(assignee_id,status,due_at);
        CREATE INDEX IF NOT EXISTS idx_process_checks_project ON process_checks(project_id,iteration_id,team_id);
        CREATE INDEX IF NOT EXISTS idx_review_alerts_project ON review_alerts(project_id,status);
        CREATE INDEX IF NOT EXISTS idx_grade_appeals_project ON grade_appeals(project_id,status);
        """
    )
    if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        seed_demo_data(db)
    demo_hash = generate_password_hash(DEMO_PASSWORD)
    db.execute("UPDATE users SET password_hash=? WHERE password_hash IS NULL OR password_hash=''", (demo_hash,))
    db.execute("UPDATE users SET active=1 WHERE active IS NULL")
    db.execute(
        """INSERT OR IGNORE INTO submission_versions(submission_id,version,file_name,file_path,submitted_at)
           SELECT id,version,file_name,file_path,submitted_at FROM submissions"""
    )
    db.execute(
        """INSERT OR IGNORE INTO review_assignments(project_id,reviewer_id,target_team_id,status,created_at,completed_at)
           SELECT project_id,reviewer_id,target_team_id,'completed',created_at,created_at FROM peer_reviews"""
    )
    if app.config.get("DEMO_MODE"):
        normalize_demo_teams(db)
    db.commit()


def normalize_demo_teams(db: sqlite3.Connection):
    project = db.execute("SELECT id,course_id FROM projects WHERE title=? ORDER BY id LIMIT 1", ("高校课程项目协作与评审平台",)).fetchone()
    if not project:
        return
    additions = [
        ("代码之神", "s9", "孙同学"),
        ("飞鹰队", "s10", "吴同学"),
        ("独角兽", "s11", "郑同学"),
        ("开拓者", "s12", "钱同学"),
    ]
    for team_name, user_id, user_name in additions:
        team = db.execute("SELECT id FROM teams WHERE project_id=? AND name=?", (project["id"], team_name)).fetchone()
        if not team:
            continue
        size = db.execute("SELECT COUNT(*) FROM team_members WHERE team_id=?", (team["id"],)).fetchone()[0]
        if size != 2:
            continue
        db.execute(
            "INSERT OR IGNORE INTO users(id,name,role,password_hash,active) VALUES(?,?, 'student',?,1)",
            (user_id, user_name, generate_password_hash(DEMO_PASSWORD)),
        )
        db.execute("INSERT OR IGNORE INTO course_members(course_id,user_id) VALUES(?,?)", (project["course_id"], user_id))
        db.execute("INSERT OR IGNORE INTO team_members(team_id,user_id,is_leader) VALUES(?,?,0)", (team["id"], user_id))


def seed_demo_data(db: sqlite3.Connection):
    demo_users = [
        ("a1", "教务管理员", "admin"),
        ("t1", "张老师", "teacher"),
        ("ta1", "王助教", "assistant"),
        ("s1", "丁沈昊", "student"),
        ("s2", "余容", "student"),
        ("s3", "蒋奇纯", "student"),
        ("s4", "李根", "student"),
        ("s5", "陈同学", "student"),
        ("s6", "刘同学", "student"),
        ("s7", "周同学", "student"),
        ("s8", "赵同学", "student"),
        ("s9", "孙同学", "student"),
        ("s10", "吴同学", "student"),
        ("s11", "郑同学", "student"),
        ("s12", "钱同学", "student"),
    ]
    db.executemany(
        "INSERT INTO users(id,name,role,password_hash,active) VALUES(?,?,?,?,1)",
        [(uid, name, role, generate_password_hash(DEMO_PASSWORD)) for uid, name, role in demo_users],
    )
    db.execute("INSERT INTO courses(name, term, teacher_id) VALUES(?,?,?)", ("软件工程", "2026 秋", "t1"))
    course_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.executemany(
        "INSERT INTO course_members(course_id, user_id) VALUES(?,?)",
        [(course_id, uid) for uid, _, role in demo_users if role in ("assistant", "student")],
    )
    db.execute(
        """INSERT INTO projects(course_id,title,description,team_deadline,overall_deadline,
           peer_weight,process_weight,final_weight,status,review_open,grades_published,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            course_id,
            "高校课程项目协作与评审平台",
            "完成需求分析、迭代成果提交、同伴互评与综合评分闭环。",
            "2026-11-05 23:59:00",
            "2026-12-20 23:59:00",
            0.25,
            0.25,
            0.50,
            "published",
            1,
            0,
            now_iso(),
        ),
    )
    project_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.executemany(
        "INSERT INTO iterations(project_id,name,deadline,requirements) VALUES(?,?,?,?)",
        [
            (project_id, "迭代 1：需求分析", "2026-11-15 23:59:00", "提交需求规格说明书与模型附件"),
            (project_id, "迭代 2：设计与实现", "2026-12-10 23:59:00", "提交设计文档、代码包与演示视频"),
        ],
    )
    iteration_id = db.execute("SELECT id FROM iterations WHERE project_id=? ORDER BY id LIMIT 1", (project_id,)).fetchone()[0]
    team_specs = [
        ("代码之神", ["s1", "s2", "s9"], 85, 90, 92),
        ("飞鹰队", ["s3", "s4", "s10"], 78, 82, 85),
        ("独角兽", ["s5", "s6", "s11"], 90, 88, 87),
        ("开拓者", ["s7", "s8", "s12"], 82, 79, 80),
    ]
    team_ids = []
    for name, members, peer, process, final in team_specs:
        db.execute(
            "INSERT INTO teams(project_id,name,status,created_at) VALUES(?,?,?,?)",
            (project_id, name, "active", now_iso()),
        )
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        team_ids.append(team_id)
        db.executemany(
            "INSERT INTO team_members(team_id,user_id,is_leader) VALUES(?,?,?)",
            [(team_id, uid, 1 if idx == 0 else 0) for idx, uid in enumerate(members)],
        )
        db.execute(
            "INSERT INTO submissions(team_id,iteration_id,file_name,file_path,submitted_at,status,version) VALUES(?,?,?,?,?,?,?)",
            (team_id, iteration_id, f"{name}-需求分析演示.pdf", None, now_iso(), "reviewing", 1),
        )
        db.execute(
            "INSERT INTO process_scores VALUES(?,?,?,?,?,?)",
            (project_id, team_id, "ta1", process, "演示过程分", now_iso()),
        )
        db.execute(
            "INSERT INTO final_scores VALUES(?,?,?,?,?,?)",
            (project_id, team_id, "t1", final, "演示终评分", now_iso()),
        )
        student_ids = [f"s{index}" for index in range(1, 13)]
    
    score_offsets = (-2, 0, 2)
    for student_id in student_ids:
        own_team_index = -1
        for i, (_, members, _, _, _) in enumerate(team_specs):
            if student_id in members:
                own_team_index = i
                break
        other_team_indices = [i for i in range(len(team_specs)) if i != own_team_index]
        for task_index, target_index in enumerate(other_team_indices):
            target_team_id = team_ids[target_index]
            target_team_name = team_specs[target_index][0]
            base_score = team_specs[target_index][2]
            score = base_score + score_offsets[(int(student_id[1:]) + task_index) % len(score_offsets)]
            score = max(0, min(100, score))
            db.execute(
                """INSERT INTO review_assignments(
                       project_id,reviewer_id,target_team_id,status,created_at,completed_at,assignment_key
                   ) VALUES(?,?,?,'completed',?,?,?)""",
                (project_id, student_id, target_team_id, now_iso(), now_iso(), uuid.uuid4().hex),
            )
            db.execute(
                "INSERT INTO peer_reviews(project_id,reviewer_id,target_team_id,score,comment,created_at) VALUES(?,?,?,?,?,?)",
                (project_id, student_id, target_team_id, score, f"评价 {target_team_name} 的成果，完成度不错，建议继续细化。", now_iso()),
            )
    for uid in student_ids:
        notify(uid, "互评已开启", "需求分析迭代已进入同伴互评阶段，请完成分配任务。", "review", "reviews")
        
    # 给教师和助教补充演示通知
    notify("t1", "系统提示", "欢迎使用课程项目协作平台，演示项目已初始化完毕。", "info", "overview")
    notify("t1", "成绩待发布", "各团队互评及评分已基本完成，请前往评分与成绩页面确认并发布。", "grade", "grades")
    notify("ta1", "过程分待录", "请及时查收各团队提交成果并录入过程分。", "grade", "grades")
    audit("t1", "publish", "project", str(project_id), "发布演示项目并设置默认权重 25%/25%/50%")


def live_gradebook(project_id: int):
    project = row("SELECT * FROM projects WHERE id=?", (project_id,))
    if not project:
        return []
    teams = rows("SELECT * FROM teams WHERE project_id=? ORDER BY id", (project_id,))
    result = []
    for team in teams:
        peer_rows = rows(
            "SELECT score FROM peer_reviews WHERE project_id=? AND target_team_id=? AND status='submitted' ORDER BY score ASC",
            (project_id, team["id"]),
        )
        scores = [r["score"] for r in peer_rows]
        count = len(scores)
        peer_warning = None
        if count >= 3:
            # 3 份及以上：去掉一个最高分、一个最低分后取算术平均（AC-04 极值剔除）
            valid_scores = scores[1:-1]
            peer_score = round(sum(valid_scores) / len(valid_scores), 1)
        elif count == 2:
            # 仅 2 份互评：样本不足无法剔除极值，直接取算术平均
            peer_score = round(sum(scores) / count, 1)
        else:
            # 有效互评不足 2 份：暂停互评分计算，标记数据异常，提示教师介入复核（BR-09）
            peer_score = None
            peer_warning = "有效互评不足2份，互评分暂缺，需教师介入复核"

        process = row("SELECT score FROM process_scores WHERE project_id=? AND team_id=?", (project_id, team["id"]))
        final = row("SELECT score FROM final_scores WHERE project_id=? AND team_id=?", (project_id, team["id"]))
        
        process_score = process["score"] if process else None
        final_score = final["score"] if final else None
        total = None
        if None not in (peer_score, process_score, final_score):
            total = round(
                peer_score * project["peer_weight"]
                + process_score * project["process_weight"]
                + final_score * project["final_weight"],
                2,
            )
        members = rows(
            """SELECT u.id AS user_id,u.name AS user_name FROM team_members tm
               JOIN users u ON u.id=tm.user_id WHERE tm.team_id=? ORDER BY u.id""",
            (team["id"],),
        )
        individuals = []
        for member in members:
            adjustment = row(
                """SELECT coefficient,manual_deduction,reason FROM individual_grade_adjustments
                   WHERE project_id=? AND user_id=?""",
                (project_id, member["user_id"]),
            ) or {"coefficient": 1.0, "manual_deduction": 0.0, "reason": "默认规则"}
            assignment_counts = row(
                """SELECT COUNT(*) AS assigned,
                          SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed
                   FROM review_assignments WHERE project_id=? AND reviewer_id=?""",
                (project_id, member["user_id"]),
            )
            assigned = int(assignment_counts["assigned"] or 0)
            completed = int(assignment_counts["completed"] or 0)
            missing_penalty = 10.0 if assigned > completed else 0.0
            manual_deduction = float(adjustment["manual_deduction"])
            coefficient = float(adjustment["coefficient"])
            individual_score = None if total is None else round(max(0, min(100, total * coefficient - manual_deduction - missing_penalty)), 2)
            individuals.append(
                {
                    **member,
                    "coefficient": coefficient,
                    "manual_deduction": manual_deduction,
                    "missing_review_penalty": missing_penalty,
                    "deduction": manual_deduction + missing_penalty,
                    "individual_score": individual_score,
                    "adjustment_reason": adjustment["reason"],
                }
            )
        result.append(
            {
                "team_id": team["id"],
                "team_name": team["name"],
                "peer_score": peer_score,
                "peer_count": count,
                "peer_warning": peer_warning,
                "process_score": process_score,
                "final_score": final_score,
                "total": total,
                "individuals": individuals,
            }
        )
    return result


def gradebook(project_id: int):
    publication = active_publication(project_id)
    if not publication:
        return live_gradebook(project_id)
    teams = rows(
        """SELECT team_id,team_name,peer_score,peer_count,process_score,final_score,total
           FROM team_grade_snapshots WHERE publication_id=? ORDER BY team_id""",
        (publication["id"],),
    )
    for team in teams:
        team["individuals"] = rows(
            """SELECT user_id,user_name,coefficient,manual_deduction,missing_review_penalty,
                      (manual_deduction+missing_review_penalty) AS deduction,final_score AS individual_score
               FROM individual_grade_snapshots WHERE publication_id=? AND team_id=? ORDER BY user_id""",
            (publication["id"], team["team_id"]),
        )
    return teams


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "course-project-platform", "version": PLATFORM_VERSION, "time": now_iso()})


@app.get("/api/demo-users")
def demo_users():
    if not app.config.get("DEMO_MODE"):
        return jsonify({"ok": True, "users": []})
    return jsonify(
        {
            "ok": True,
            "users": rows(
                "SELECT id,name,role FROM users WHERE active=1 ORDER BY CASE role WHEN 'admin' THEN 1 WHEN 'teacher' THEN 2 WHEN 'assistant' THEN 3 ELSE 4 END,id"
            ),
            "password_hint": "演示账号统一密码：123456" if DEMO_PASSWORD == "123456" else "请使用管理员配置的演示密码",
        }
    )


@app.get("/api/session")
def session_status():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": True, "authenticated": False})
    user = row("SELECT id,name,role,active FROM users WHERE id=?", (user_id,))
    if not user or not user["active"]:
        session.clear()
        return jsonify({"ok": True, "authenticated": False})
    return jsonify({"ok": True, "authenticated": True, "current_user": user, "csrf_token": session.get("csrf_token")})


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    password = str(data.get("password", ""))
    user = row("SELECT * FROM users WHERE id=?", (user_id,))
    if user and user.get("locked_until"):
        try:
            locked_until = parse_deadline(user["locked_until"])
        except ValueError:
            locked_until = datetime.min
        if locked_until > datetime.now():
            raise APIError(f"账号已临时锁定，请在 {locked_until.strftime('%H:%M')} 后重试", 423)
        get_db().execute("UPDATE users SET failed_attempts=0,locked_until=NULL WHERE id=?", (user_id,))
        get_db().commit()
        user["failed_attempts"] = 0
        user["locked_until"] = None
    if not user or not user.get("active", 1) or not check_password_hash(user.get("password_hash") or "", password):
        if user and user.get("active", 1):
            attempts = int(user.get("failed_attempts") or 0) + 1
            locked_until = (datetime.now() + timedelta(minutes=15)).replace(microsecond=0).isoformat(sep=" ") if attempts >= 5 else None
            db = get_db()
            db.execute("UPDATE users SET failed_attempts=?,locked_until=? WHERE id=?", (attempts, locked_until, user_id))
            audit(user_id, "login_failed", "user", user_id, f"登录失败第 {attempts} 次" + ("，账号锁定 15 分钟" if locked_until else ""))
            db.commit()
        raise APIError("账号或密码错误", 401)
    get_db().execute("UPDATE users SET failed_attempts=0,locked_until=NULL WHERE id=?", (user_id,))
    get_db().commit()
    session.clear()
    session["user_id"] = user["id"]
    session["csrf_token"] = secrets.token_urlsafe(24)
    return jsonify(
        {
            "ok": True,
            "message": "登录成功",
            "current_user": {key: user[key] for key in ("id", "name", "role")},
            "csrf_token": session["csrf_token"],
        }
    )


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True, "message": "已安全退出"})


@app.get("/api/bootstrap")
def bootstrap():
    user = current_user()
    sync_deadline_notifications(user)
    if user["role"] == "admin":
        courses = rows("SELECT id,name,term FROM courses ORDER BY id")
    elif user["role"] == "teacher":
        courses = rows("SELECT id,name,term FROM courses WHERE teacher_id=? ORDER BY id", (user["id"],))
    else:
        courses = rows(
            """SELECT c.id,c.name,c.term FROM courses c JOIN course_members cm ON cm.course_id=c.id
               WHERE cm.user_id=? ORDER BY c.id""",
            (user["id"],),
        )
    course_ids = [item["id"] for item in courses]
    if course_ids:
        placeholders = ",".join("?" for _ in course_ids)
        status_clause = "" if user["role"] in ("teacher", "admin") else " AND p.status='published'"
        projects = rows(
            f"""SELECT p.*,c.name AS course_name,c.term FROM projects p JOIN courses c ON c.id=p.course_id
                 WHERE p.course_id IN ({placeholders}) AND p.status<>'archived'{status_clause} ORDER BY p.id DESC""",
            course_ids,
        )
    else:
        projects = []
    requested_id = request.args.get("project_id", type=int)
    active = next((item for item in projects if item["id"] == requested_id), projects[0] if projects else None)
    for project in projects:
        project["iterations"] = rows("SELECT * FROM iterations WHERE project_id=? ORDER BY id", (project["id"],))
        project["gradebook"] = []
    teams, submissions, my_team, review_targets, visible_logs = [], [], None, [], []
    if active:
        active_id = active["id"]
        my_team = row(
            """SELECT t.*,tm.is_leader FROM teams t JOIN team_members tm ON tm.team_id=t.id
               WHERE t.project_id=? AND tm.user_id=?""",
            (active_id, user["id"]),
        )
        if user["role"] in ("teacher", "assistant", "admin") or my_team:
            team_scope = "" if user["role"] in ("teacher", "assistant", "admin") else " AND t.id=?"
            team_params = (active_id,) if not team_scope else (active_id, my_team["id"])
            teams = rows(
                f"""SELECT t.*,GROUP_CONCAT(u.name,'、') AS members,COUNT(tm.user_id) AS member_count,
                    MAX(CASE WHEN tm.is_leader=1 THEN u.name END) AS leader_name
                    FROM teams t LEFT JOIN team_members tm ON tm.team_id=t.id LEFT JOIN users u ON u.id=tm.user_id
                    WHERE t.project_id=?{team_scope} GROUP BY t.id ORDER BY t.id""",
                team_params,
            )
        elif user["role"] == "student" and not active["grades_published"]:
            teams = rows(
                """SELECT t.id,t.project_id,t.name,t.status,t.created_at,'' AS members,
                          COUNT(tm.user_id) AS member_count,'成员信息加入后可见' AS leader_name
                   FROM teams t LEFT JOIN team_members tm ON tm.team_id=t.id
                   WHERE t.project_id=? GROUP BY t.id ORDER BY t.id""",
                (active_id,),
            )
        for team in teams:
            if user["role"] in ("teacher", "assistant", "admin") or (my_team and team["id"] == my_team["id"]):
                team["member_details"] = rows(
                    """SELECT u.id,u.name,tm.is_leader FROM team_members tm JOIN users u ON u.id=tm.user_id
                       WHERE tm.team_id=? ORDER BY tm.is_leader DESC,u.id""",
                    (team["id"],),
                )
        if user["role"] in ("teacher", "assistant", "admin"):
            submissions = rows(
                """SELECT s.*,t.name AS team_name,i.name AS iteration_name,i.deadline,
                   (SELECT COUNT(*) FROM submission_versions sv WHERE sv.submission_id=s.id) AS version_count
                   FROM submissions s JOIN teams t ON t.id=s.team_id JOIN iterations i ON i.id=s.iteration_id
                   WHERE t.project_id=? ORDER BY s.submitted_at DESC""",
                (active_id,),
            )
        elif my_team:
            submissions = rows(
                """SELECT s.*,t.name AS team_name,i.name AS iteration_name,i.deadline,
                   (SELECT COUNT(*) FROM submission_versions sv WHERE sv.submission_id=s.id) AS version_count
                   FROM submissions s JOIN teams t ON t.id=s.team_id JOIN iterations i ON i.id=s.iteration_id
                   WHERE t.project_id=? AND t.id=? ORDER BY s.submitted_at DESC""",
                (active_id, my_team["id"]),
            )
        if user["role"] == "student":
            review_targets = rows(
                """SELECT ra.assignment_key AS assignment_id,ra.status,ra.completed_at,
                    pr.score AS current_score,pr.completeness_score,pr.innovation_score,pr.documentation_score,
                    pr.comment AS current_comment,pr.status AS review_status,
                    CASE WHEN pr.status='submitted' THEN 1 ELSE 0 END AS reviewed,
                   EXISTS(SELECT 1 FROM submissions s JOIN iterations i ON i.id=s.iteration_id
                          WHERE s.team_id=ra.target_team_id AND i.project_id=ra.project_id
                            AND s.status<>'withdrawn') AS has_submission
                   FROM review_assignments ra
                   LEFT JOIN peer_reviews pr ON pr.project_id=ra.project_id AND pr.reviewer_id=ra.reviewer_id
                        AND pr.target_team_id=ra.target_team_id
                   WHERE ra.project_id=? AND ra.reviewer_id=? ORDER BY ra.created_at,ra.assignment_key""",
                (active_id, user["id"]),
            )
            for index, target in enumerate(review_targets):
                target["name"] = f"匿名成果 {chr(65 + index)}"
        active_grades = gradebook(active_id)
        if user["role"] in ("teacher", "admin"):
            active["gradebook"] = active_grades
        elif user["role"] == "assistant":
            active["gradebook"] = [
                {
                    "team_id": item["team_id"],
                    "team_name": item["team_name"],
                    "peer_score": item["peer_score"],
                    "peer_count": item["peer_count"],
                    "process_score": item["process_score"],
                }
                for item in active_grades
            ]
        elif active["grades_published"] and my_team:
            own_team = next((item for item in active_grades if item["team_id"] == my_team["id"]), None)
            own_grade = next((item for item in (own_team or {}).get("individuals", []) if item["user_id"] == user["id"]), None)
            if own_team and own_grade:
                active["gradebook"] = [
                    {
                        "team_id": own_team["team_id"],
                        "team_name": own_team["team_name"],
                        "peer_score": own_team["peer_score"],
                        "individual_score": own_grade["individual_score"],
                    }
                ]
        if user["role"] in ("teacher", "assistant", "admin"):
            visible_logs = rows(
                """SELECT l.*,u.name AS user_name,u.role AS user_role FROM audit_logs l JOIN users u ON u.id=l.user_id
                   WHERE l.project_id=? OR (l.project_id IS NULL AND l.entity_id=?) ORDER BY l.id DESC LIMIT 100""",
                (active_id, str(active_id)),
            )
        elif user["role"] == "student":
            visible_logs = rows(
                """SELECT l.*,u.name AS user_name,u.role AS user_role FROM audit_logs l JOIN users u ON u.id=l.user_id
                   WHERE l.project_id=? AND l.user_id=? ORDER BY l.id DESC LIMIT 100""",
                (active_id, user["id"]),
            )
    visible_users = [{key: user[key] for key in ("id", "name", "role")}]
    if active and user["role"] in ("teacher", "admin"):
        visible_users = rows(
            """SELECT DISTINCT u.id,u.name,u.role FROM users u
               LEFT JOIN course_members cm ON cm.user_id=u.id
               WHERE cm.course_id=? OR u.id=(SELECT teacher_id FROM courses WHERE id=?) OR u.role='admin'
               ORDER BY CASE u.role WHEN 'admin' THEN 1 WHEN 'teacher' THEN 2 WHEN 'assistant' THEN 3 ELSE 4 END,u.id""",
            (active["course_id"], active["course_id"]),
        )
    return jsonify(
        {
            "ok": True,
            "csrf_token": session.get("csrf_token"),
            "courses": courses,
            "users": visible_users,
            "current_user": user,
            "projects": projects,
            "active_project_id": active["id"] if active else None,
            "teams": teams,
            "submissions": submissions,
            "my_team": my_team,
            "review_targets": review_targets,
            "notifications": rows("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 20", (user["id"],)),
            "logs": visible_logs,
            "join_requests": visible_join_requests(active["id"], user) if active else [],
            "member_tasks": visible_member_tasks(active["id"], user) if active else [],
            "process_checks": visible_process_checks(active["id"], user) if active else [],
            "review_alerts": rows("SELECT ra.*,t.name AS team_name FROM review_alerts ra JOIN teams t ON t.id=ra.target_team_id WHERE ra.project_id=? ORDER BY ra.id DESC", (active["id"],)) if active and user["role"] in ("teacher", "assistant", "admin") else [],
            "grade_appeals": visible_grade_appeals(active["id"], user) if active else [],
        }
    )


@app.post("/api/courses")
def create_course():
    user, error = require_role("teacher")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    term = str(data.get("term", "")).strip()
    if not name or not term:
        return abort_json("请填写课程名称和开课学期")
    db = get_db()
    db.execute("INSERT INTO courses(name,term,teacher_id) VALUES(?,?,?)", (name, term, user["id"]))
    course_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    audit(user["id"], "create", "course", course_id, f"创建课程：{name}（{term}）")
    db.commit()
    return jsonify({"ok": True, "message": "课程创建成功", "course_id": course_id})


@app.post("/api/projects")
def create_project():
    user, error = require_role("teacher")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    required = ["title", "description", "team_deadline", "overall_deadline"]
    if any(not str(data.get(key, "")).strip() for key in required):
        return abort_json("请填写项目名称、说明和截止时间")
    try:
        weights = [float(data.get("peer_weight", 25)), float(data.get("process_weight", 25)), float(data.get("final_weight", 50))]
    except (TypeError, ValueError):
        return abort_json("评分权重必须是数字")
    if any(value < 0 or value > 100 for value in weights):
        return abort_json("每项评分权重必须在 0—100% 之间")
    if abs(sum(weights) - 100) > 0.001:
        return abort_json("三项评分权重必须合计 100%")
    try:
        team_deadline = parse_deadline(data["team_deadline"])
        overall_deadline = parse_deadline(data["overall_deadline"])
        review_deadline = parse_deadline(data.get("review_deadline") or data["overall_deadline"])
    except (TypeError, ValueError):
        return abort_json("截止时间格式无效")
    if team_deadline >= overall_deadline or review_deadline > overall_deadline:
        return abort_json("组队截止时间必须早于总截止时间，互评截止时间不能晚于总截止时间")
    db = get_db()
    course_id = int(data.get("course_id") or 0)
    course = row("SELECT id FROM courses WHERE id=? AND teacher_id=?", (course_id, user["id"]))
    if not course:
        course = row("SELECT id FROM courses WHERE teacher_id=? ORDER BY id LIMIT 1", (user["id"],))
    if not course:
        return abort_json("当前教师尚未关联课程")
    course_id = course["id"]
    publish_now = not bool(data.get("save_as_draft"))
    project_status = "published" if publish_now else "draft"
    db.execute(
        """INSERT INTO projects(course_id,title,description,team_deadline,overall_deadline,
           peer_weight,process_weight,final_weight,status,review_open,grades_published,created_at,
           review_deadline,published_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            course_id,
            data["title"].strip(),
            data["description"].strip(),
            data["team_deadline"],
            data["overall_deadline"],
            weights[0] / 100,
            weights[1] / 100,
            weights[2] / 100,
            project_status,
            0,
            0,
            now_iso(),
            data.get("review_deadline") or data["overall_deadline"],
            now_iso() if publish_now else None,
            now_iso(),
        ),
    )
    project_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    iterations = data.get("iterations") or [
        {
            "name": "迭代 1",
            "deadline": data.get("iteration_deadline") or data["overall_deadline"],
            "requirements": data.get("requirements", "提交阶段成果"),
        }
    ]
    if not isinstance(iterations, list) or not iterations:
        return abort_json("至少需要一个迭代")
    for index, item in enumerate(iterations, 1):
        name = str(item.get("name") or f"迭代 {index}").strip()
        requirements = str(item.get("requirements") or "提交阶段成果").strip()
        deadline = str(item.get("deadline") or data["overall_deadline"])
        try:
            parsed = parse_deadline(deadline)
        except ValueError:
            return abort_json(f"第 {index} 个迭代截止时间无效")
        if parsed > overall_deadline:
            return abort_json(f"第 {index} 个迭代截止时间不能晚于项目总截止时间")
        db.execute(
            "INSERT INTO iterations(project_id,name,deadline,requirements) VALUES(?,?,?,?)",
            (project_id, name, deadline, requirements),
        )
    audit(
        user["id"], "publish" if publish_now else "draft", "project", project_id,
        ("发布项目：" if publish_now else "保存项目草稿：") + data["title"].strip(), project_id,
    )
    if publish_now:
        for member in rows("SELECT user_id FROM course_members WHERE course_id=?", (course_id,)):
            notify(member["user_id"], "新项目已发布", data["title"].strip(), "project", "projects")
    db.commit()
    return jsonify({"ok": True, "message": "项目发布成功" if publish_now else "项目草稿已保存", "project_id": project_id})


@app.post("/api/projects/<int:project_id>/publish")
def publish_project(project_id: int):
    user, error = require_role("teacher")
    if error:
        return error
    project = selected_project(project_id, user)
    if project["status"] == "published":
        return jsonify({"ok": True, "message": "项目已经发布"})
    if not rows("SELECT id FROM iterations WHERE project_id=?", (project_id,)):
        return abort_json("至少设置一个迭代后才能发布")
    db = get_db()
    db.execute("UPDATE projects SET status='published',published_at=?,updated_at=? WHERE id=?", (now_iso(), now_iso(), project_id))
    for member in rows("SELECT user_id FROM course_members WHERE course_id=?", (project["course_id"],)):
        notify(member["user_id"], "新项目已发布", project["title"], "project", "projects")
    audit(user["id"], "publish", "project", project_id, f"发布项目草稿：{project['title']}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "项目发布成功"})


@app.patch("/api/projects/<int:project_id>")
def update_project(project_id: int):
    user, error = require_role("teacher")
    if error:
        return error
    project = selected_project(project_id, user)
    if project["grades_published"]:
        return abort_json("成绩已发布，不能再修改项目规则")
    data = request.get_json(silent=True) or {}
    
    # 允许修改权重
    allowed = {"title", "description", "team_deadline", "overall_deadline", "review_deadline", "peer_weight", "process_weight", "final_weight"}
    updates = {key: str(data[key]).strip() for key in allowed if key in data and str(data[key]).strip()}
    
    if not updates:
        return abort_json("没有可保存的修改")
        
    # 校验权重逻辑
    if any(k in updates for k in ["peer_weight", "process_weight", "final_weight"]):
        try:
            p_w = float(updates.get("peer_weight", project["peer_weight"] * 100))
            pr_w = float(updates.get("process_weight", project["process_weight"] * 100))
            f_w = float(updates.get("final_weight", project["final_weight"] * 100))
            if any(v < 0 or v > 100 for v in (p_w, pr_w, f_w)) or abs(p_w + pr_w + f_w - 100) > 0.001:
                return abort_json("三项评分权重必须在 0—100% 之间，且合计 100%")
            updates["peer_weight"] = p_w / 100
            updates["process_weight"] = pr_w / 100
            updates["final_weight"] = f_w / 100
        except (ValueError, TypeError):
            return abort_json("权重必须是数字")

    merged = {**project, **updates}
    try:
        if parse_deadline(merged["team_deadline"]) >= parse_deadline(merged["overall_deadline"]):
            return abort_json("组队截止时间必须早于项目总截止时间")
    except ValueError:
        return abort_json("截止时间格式无效")
        
    assignments = ",".join(f"{key}=?" for key in updates)
    get_db().execute(f"UPDATE projects SET {assignments},updated_at=? WHERE id=?", (*updates.values(), now_iso(), project_id))
    audit(user["id"], "update", "project", project_id, "修改项目基本信息及权重", project_id)
    get_db().commit()
    return jsonify({"ok": True, "message": "项目已更新"})


@app.post("/api/projects/<int:project_id>/iterations")
def add_iteration(project_id: int):
    user, error = require_role("teacher")
    if error:
        return error
    project = selected_project(project_id, user)
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    requirements = str(data.get("requirements", "")).strip()
    deadline = str(data.get("deadline", "")).strip()
    if not name or not requirements or not deadline:
        return abort_json("请完整填写迭代名称、要求与截止时间")
    try:
        if parse_deadline(deadline) > parse_deadline(project["overall_deadline"]):
            return abort_json("迭代截止时间不能晚于项目总截止时间")
    except ValueError:
        return abort_json("迭代截止时间无效")
    db = get_db()
    db.execute("INSERT INTO iterations(project_id,name,deadline,requirements) VALUES(?,?,?,?)", (project_id, name, deadline, requirements))
    iteration_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    audit(user["id"], "create", "iteration", iteration_id, f"新增迭代：{name}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "迭代已添加"})


@app.post("/api/teams")
def create_team():
    user, error = require_role("student")
    if error:
        return error
    data = request.get_json(force=True)
    project_id = int(data.get("project_id", 0))
    name = str(data.get("name", "")).strip()
    project = row("SELECT * FROM projects WHERE id=?", (project_id,))
    if not project or not name:
        return abort_json("项目或团队名称无效")
    selected_project(project_id, user)
    try:
        ensure_project_writable(project_id)
    except APIError as exc:
        return abort_json(exc.message, exc.status)
    if row("SELECT 1 FROM team_members tm JOIN teams t ON t.id=tm.team_id WHERE tm.user_id=? AND t.project_id=?", (user["id"], project_id)):
        return abort_json("你已加入该项目的团队")
    if datetime.now() > parse_deadline(project["team_deadline"]):
        return abort_json("已超过组队截止时间")
    db = get_db()
    try:
        db.execute("INSERT INTO teams(project_id,name,status,created_at) VALUES(?,?,?,?)", (project_id, name, "forming", now_iso()))
        team_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO team_members VALUES(?,?,?)", (team_id, user["id"], 1))
        audit(user["id"], "create", "team", team_id, f"创建团队：{name}", project_id)
        db.commit()
    except sqlite3.IntegrityError:
        return abort_json("团队名称已存在")
    return jsonify({"ok": True, "message": "团队创建成功"})


@app.post("/api/teams/<int:team_id>/join")
def join_team(team_id: int):
    user, error = require_role("student")
    if error:
        return error
    team = row("SELECT t.*, p.team_deadline FROM teams t JOIN projects p ON p.id=t.project_id WHERE t.id=?", (team_id,))
    if not team:
        return abort_json("团队不存在", 404)
    try:
        ensure_project_writable(team["project_id"])
    except APIError as exc:
        return abort_json(exc.message, exc.status)
    if datetime.now() > parse_deadline(team["team_deadline"]):
        return abort_json("已超过组队截止时间")
    if row("SELECT 1 FROM team_members tm JOIN teams t ON t.id=tm.team_id WHERE tm.user_id=? AND t.project_id=?", (user["id"], team["project_id"])):
        return abort_json("你已加入该项目的团队")
    if row(
        """SELECT 1 FROM team_join_requests r JOIN teams t ON t.id=r.team_id
           WHERE r.user_id=? AND t.project_id=? AND r.status='pending'""",
        (user["id"], team["project_id"]),
    ):
        return abort_json("你已有一条待审核的入队申请")
    count = row("SELECT COUNT(*) AS n FROM team_members WHERE team_id=?", (team_id,))["n"]
    if count >= 5:
        return abort_json("团队已达到 5 人上限")
    selected_project(team["project_id"], user)
    db = get_db()
    db.execute(
        """INSERT INTO team_join_requests(team_id,user_id,status,requested_at)
           VALUES(?,?,'pending',?) ON CONFLICT(team_id,user_id) DO UPDATE SET
           status='pending',requested_at=excluded.requested_at,decided_at=NULL,decided_by=NULL""",
        (team_id, user["id"], now_iso()),
    )
    leader = row("SELECT user_id FROM team_members WHERE team_id=? AND is_leader=1", (team_id,))
    if leader:
        notify(leader["user_id"], "新的入队申请", f"{user['name']} 申请加入“{team['name']}”", "team", "teams")
    audit(user["id"], "request_join", "team", team_id, f"申请加入团队：{team['name']}", team["project_id"])
    db.commit()
    return jsonify({"ok": True, "message": "入队申请已提交，等待组长审核"})


@app.post("/api/team-join-requests/<int:request_id>/decision")
def decide_join_request(request_id: int):
    user, error = require_role("student")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "")).strip()
    if decision not in ("approved", "rejected"):
        return abort_json("审核结果必须为同意或拒绝")
    join_request = row(
        """SELECT r.*,t.project_id,t.name AS team_name,p.team_deadline FROM team_join_requests r
           JOIN teams t ON t.id=r.team_id JOIN projects p ON p.id=t.project_id WHERE r.id=?""",
        (request_id,),
    )
    if not join_request or join_request["status"] != "pending":
        return abort_json("入队申请不存在或已处理", 404)
    leader = row("SELECT 1 FROM team_members WHERE team_id=? AND user_id=? AND is_leader=1", (join_request["team_id"], user["id"]))
    if not leader:
        return abort_json("只有团队负责人可以审核入队申请", 403)
    if datetime.now() > parse_deadline(join_request["team_deadline"]):
        return abort_json("组队截止后不能审核新成员")
    db = get_db()
    if decision == "approved":
        if team_size(join_request["team_id"]) >= 5:
            return abort_json("团队已达到 5 人上限")
        if row(
            """SELECT 1 FROM team_members tm JOIN teams t ON t.id=tm.team_id
               WHERE tm.user_id=? AND t.project_id=?""",
            (join_request["user_id"], join_request["project_id"]),
        ):
            return abort_json("该学生已经加入本项目的其他团队")
        db.execute("INSERT INTO team_members(team_id,user_id,is_leader) VALUES(?,?,0)", (join_request["team_id"], join_request["user_id"]))
        db.execute(
            """UPDATE team_join_requests SET status='rejected',decided_at=?,decided_by=?
               WHERE user_id=? AND id<>? AND status='pending' AND team_id IN
               (SELECT id FROM teams WHERE project_id=?)""",
            (now_iso(), user["id"], join_request["user_id"], request_id, join_request["project_id"]),
        )
    db.execute(
        "UPDATE team_join_requests SET status=?,decided_at=?,decided_by=? WHERE id=?",
        (decision, now_iso(), user["id"], request_id),
    )
    notify(join_request["user_id"], "入队申请已处理", f"“{join_request['team_name']}”的申请结果：{'已同意' if decision == 'approved' else '已拒绝'}", "team", "teams")
    audit(user["id"], "decide_join", "team", join_request["team_id"], f"{'同意' if decision == 'approved' else '拒绝'}入队申请 #{request_id}", join_request["project_id"])
    db.commit()
    return jsonify({"ok": True, "message": "入队申请已处理"})


@app.post("/api/teams/<int:team_id>/members/adjust")
def adjust_team_member(team_id: int):
    user, error = require_role("teacher", "admin")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    action = str(data.get("action", "")).strip()
    target_user_id = str(data.get("user_id", "")).strip()
    reason = str(data.get("reason", "")).strip()
    if action not in ("add", "remove") or not target_user_id or not reason:
        return abort_json("请选择调整动作和学生，并填写调整理由")
    team = row("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        return abort_json("团队不存在", 404)
    project = selected_project(team["project_id"], user)
    student = row("SELECT id,name FROM users WHERE id=? AND role='student'", (target_user_id,))
    if not student:
        return abort_json("学生不存在")
    db = get_db()
    if action == "add":
        if team_size(team_id) >= 5:
            return abort_json("团队已达到 5 人上限")
        if row("SELECT 1 FROM team_members tm JOIN teams t ON t.id=tm.team_id WHERE tm.user_id=? AND t.project_id=?", (target_user_id, team["project_id"])):
            return abort_json("该学生已加入本项目团队")
        db.execute("INSERT INTO team_members(team_id,user_id,is_leader) VALUES(?,?,0)", (team_id, target_user_id))
    else:
        membership = row("SELECT is_leader FROM team_members WHERE team_id=? AND user_id=?", (team_id, target_user_id))
        if not membership:
            return abort_json("该学生不在此团队")
        if membership["is_leader"]:
            return abort_json("请先指定其他负责人，再移除当前组长")
        db.execute("DELETE FROM team_members WHERE team_id=? AND user_id=?", (team_id, target_user_id))
    audit(user["id"], "adjust_member", "team", team_id, f"教师例外{'加入' if action == 'add' else '移除'}成员 {student['name']}；理由：{reason}", project["id"])
    db.commit()
    return jsonify({"ok": True, "message": "团队成员已调整并留痕"})


@app.post("/api/teams/<int:team_id>/leave")
def leave_team(team_id: int):
    user, error = require_role("student")
    if error:
        return error
    membership = row(
        """SELECT tm.is_leader,t.project_id,t.name FROM team_members tm JOIN teams t ON t.id=tm.team_id
           WHERE tm.team_id=? AND tm.user_id=?""",
        (team_id, user["id"]),
    )
    if not membership:
        return abort_json("你不在该团队中", 404)
    project = selected_project(membership["project_id"], user)
    try:
        ensure_project_writable(membership["project_id"])
    except APIError as exc:
        return abort_json(exc.message, exc.status)
    if datetime.now() > parse_deadline(project["team_deadline"]):
        return abort_json("组队截止后不能退出团队")
    if row("SELECT 1 FROM submissions WHERE team_id=? AND status<>'withdrawn'", (team_id,)):
        return abort_json("团队已有提交记录，不能直接退出")
    db = get_db()
    if membership["is_leader"] and team_size(team_id) > 1:
        successor = row("SELECT user_id FROM team_members WHERE team_id=? AND user_id<>? ORDER BY user_id LIMIT 1", (team_id, user["id"]))
        db.execute("UPDATE team_members SET is_leader=1 WHERE team_id=? AND user_id=?", (team_id, successor["user_id"]))
    db.execute("DELETE FROM team_members WHERE team_id=? AND user_id=?", (team_id, user["id"]))
    if team_size(team_id) == 0:
        db.execute("DELETE FROM teams WHERE id=?", (team_id,))
    audit(user["id"], "leave", "team", team_id, f"退出团队：{membership['name']}", membership["project_id"])
    db.commit()
    return jsonify({"ok": True, "message": "已退出团队"})


@app.post("/api/member-tasks")
def create_member_task():
    user, error = require_role("student")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    project_id = int(data.get("project_id", 0))
    iteration_id = int(data.get("iteration_id", 0))
    assignee_id = str(data.get("assignee_id", "")).strip()
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    due_at = str(data.get("due_at", "")).strip()
    if not assignee_id or not title or not description or not due_at:
        return abort_json("请完整填写任务负责人、任务内容和截止时间")
    team = row(
        """SELECT t.id FROM teams t JOIN team_members tm ON tm.team_id=t.id
           WHERE t.project_id=? AND tm.user_id=? AND tm.is_leader=1""",
        (project_id, user["id"]),
    )
    if not team:
        return abort_json("只有团队负责人可以分配成员任务", 403)
    iteration = row("SELECT * FROM iterations WHERE id=? AND project_id=?", (iteration_id, project_id))
    if not iteration:
        return abort_json("迭代不存在")
    if not row("SELECT 1 FROM team_members WHERE team_id=? AND user_id=?", (team["id"], assignee_id)):
        return abort_json("负责人不属于当前团队")
    try:
        if parse_deadline(due_at) > parse_deadline(iteration["deadline"]):
            return abort_json("成员任务截止时间不能晚于迭代截止时间")
    except ValueError:
        return abort_json("截止时间格式无效")
    db = get_db()
    db.execute(
        """INSERT INTO member_tasks(project_id,iteration_id,team_id,assignee_id,title,description,status,due_at,created_by,created_at,updated_at)
           VALUES(?,?,?,?,?,?,'todo',?,?,?,?)""",
        (project_id, iteration_id, team["id"], assignee_id, title, description, due_at, user["id"], now_iso(), now_iso()),
    )
    task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    notify(assignee_id, "新的迭代任务", title, "task", "teams")
    audit(user["id"], "assign_task", "member_task", task_id, f"分配任务：{title}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "成员任务已分配"})


@app.patch("/api/member-tasks/<int:task_id>")
def update_member_task(task_id: int):
    user, error = require_role("student")
    if error:
        return error
    task = row("SELECT * FROM member_tasks WHERE id=?", (task_id,))
    if not task:
        return abort_json("任务不存在", 404)
    leader = row("SELECT 1 FROM team_members WHERE team_id=? AND user_id=? AND is_leader=1", (task["team_id"], user["id"]))
    if task["assignee_id"] != user["id"] and not leader:
        return abort_json("无权修改该成员任务", 403)
    status = str((request.get_json(silent=True) or {}).get("status", "")).strip()
    if status not in ("todo", "doing", "done"):
        return abort_json("任务状态无效")
    get_db().execute("UPDATE member_tasks SET status=?,updated_at=? WHERE id=?", (status, now_iso(), task_id))
    audit(user["id"], "update_task", "member_task", task_id, f"更新任务状态为 {status}", task["project_id"])
    get_db().commit()
    return jsonify({"ok": True, "message": "任务状态已更新"})


@app.post("/api/submissions/<int:iteration_id>")
def upload_submission(iteration_id: int):
    user, error = require_role("student")
    if error:
        return error
    iteration = row("SELECT * FROM iterations WHERE id=?", (iteration_id,))
    if not iteration:
        return abort_json("迭代不存在", 404)
        
    project_check = row("SELECT grades_published,review_open FROM projects WHERE id=?", (iteration["project_id"],))
    if project_check and project_check["grades_published"]:
        return abort_json("成绩已发布，不能上传或修改成果", 403)
    if project_check and project_check["review_open"]:
        return abort_json("互评已经开启，成果已冻结，不能继续修改", 403)

    membership = row(
        """SELECT t.id AS team_id, tm.is_leader FROM teams t JOIN team_members tm ON tm.team_id=t.id
           WHERE t.project_id=? AND tm.user_id=?""",
        (iteration["project_id"], user["id"]),
    )
    assigned = membership and row(
        """SELECT 1 FROM member_tasks WHERE project_id=? AND iteration_id=? AND team_id=?
           AND assignee_id=?""",
        (iteration["project_id"], iteration_id, membership["team_id"], user["id"]),
    )
    if not membership or (not membership["is_leader"] and not assigned):
        return abort_json("只有团队负责人或该迭代的指定成员可以上传成果", 403)
    selected_project(iteration["project_id"], user)
    try:
        ensure_team_ready(membership["team_id"])
    except APIError as exc:
        return abort_json(exc.message, exc.status)
    if datetime.now() > parse_deadline(iteration["deadline"]):
        return abort_json("已超过本轮迭代截止时间")
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return abort_json("请选择文件")
    extension = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        return abort_json("仅允许 PDF、ZIP、MP4 文件")
    if uploaded.mimetype and uploaded.mimetype not in ALLOWED_MIME_TYPES[extension]:
        return abort_json("文件类型与扩展名不匹配")
    safe_name = secure_filename(uploaded.filename) or f"submission.{extension}"
    stored_name = f"{uuid.uuid4().hex}-{safe_name}"
    target = UPLOAD_DIR / stored_name
    uploaded.save(target)
    if target.stat().st_size > app.config["MAX_CONTENT_LENGTH"]:
        target.unlink(missing_ok=True)
        return abort_json("单文件不能超过 200MB")
    if target.stat().st_size == 0 or not file_matches_extension(target, extension):
        target.unlink(missing_ok=True)
        return abort_json("文件内容与扩展名不匹配或文件已损坏")
    db = get_db()
    existing = row("SELECT * FROM submissions WHERE team_id=? AND iteration_id=?", (membership["team_id"], iteration_id))
    if existing:
        expected_lock = request.form.get("lock_version", type=int)
        if expected_lock is not None and expected_lock != int(existing.get("lock_version") or 1):
            target.unlink(missing_ok=True)
            return abort_json("数据已被其他成员修改，请刷新后重新提交", 409)
        db.execute(
            """UPDATE submissions SET file_name=?,file_path=?,submitted_at=?,status='submitted',
               version=version+1,lock_version=lock_version+1,returned_reason=NULL WHERE id=?""",
            (uploaded.filename, str(target), now_iso(), existing["id"]),
        )
        submission_id = existing["id"]
        new_version = existing["version"] + 1
    else:
        db.execute(
            "INSERT INTO submissions(team_id,iteration_id,file_name,file_path,submitted_at,status,version) VALUES(?,?,?,?,?,'submitted',1)",
            (membership["team_id"], iteration_id, uploaded.filename, str(target), now_iso()),
        )
        submission_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        new_version = 1
    db.execute(
        """INSERT INTO submission_versions(submission_id,version,file_name,file_path,submitted_at)
           VALUES(?,?,?,?,?)""",
        (submission_id, new_version, uploaded.filename, str(target), now_iso()),
    )
    db.execute("UPDATE teams SET status='active' WHERE id=?", (membership["team_id"],))
    audit(user["id"], "submit", "submission", submission_id, f"上传成果 v{new_version}：{uploaded.filename}", iteration["project_id"])
    db.commit()
    return jsonify({"ok": True, "message": "成果提交成功"})

@app.post("/api/submissions/<int:submission_id>/withdraw")
def withdraw_submission(submission_id: int):
    user, error = require_role("student")
    if error:
        return error
    submission = row(
        """SELECT s.*, i.deadline, tm.user_id, tm.is_leader FROM submissions s
           JOIN iterations i ON i.id=s.iteration_id JOIN team_members tm ON tm.team_id=s.team_id
           WHERE s.id=? AND tm.user_id=?""",
        (submission_id, user["id"]),
    )
    if not submission or not submission["is_leader"]:
        return abort_json("只有团队负责人可以撤回", 403)
        
    team_proj = row("SELECT project_id FROM teams WHERE id=?", (submission["team_id"],))
    project_check = row("SELECT grades_published,review_open FROM projects WHERE id=?", (team_proj["project_id"],))
    if project_check and project_check["grades_published"]:
        return abort_json("成绩已发布，不能撤回提交", 403)
    if project_check and project_check["review_open"]:
        return abort_json("互评已经开启，成果已冻结，不能撤回", 403)

    if datetime.now() > parse_deadline(submission["deadline"]):
        return abort_json("截止后不可撤回")
    db = get_db()
    db.execute("UPDATE submissions SET status='withdrawn' WHERE id=?", (submission_id,))
    project_id = row("SELECT project_id FROM teams WHERE id=?", (submission["team_id"],))["project_id"]
    audit(user["id"], "withdraw", "submission", submission_id, "撤回成果，保留历史版本", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "已撤回，可重新提交"})


@app.get("/api/submissions/<int:submission_id>/download")
def download_submission(submission_id: int):
    user = current_user()
    submission = row(
        """SELECT s.*,t.project_id FROM submissions s JOIN teams t ON t.id=s.team_id WHERE s.id=?""",
        (submission_id,),
    )
    if not submission or not submission["file_path"] or not Path(submission["file_path"]).exists():
        return abort_json("演示数据没有实体文件，请上传新文件后再下载", 404)
    selected_project(submission["project_id"], user)
    allowed = user["role"] in ("teacher", "assistant")
    if user["role"] == "student":
        allowed = bool(row("SELECT 1 FROM team_members WHERE team_id=? AND user_id=?", (submission["team_id"], user["id"])))
    if not allowed:
        return abort_json("请通过匿名互评任务下载被分配成果", 403)
    return send_file(submission["file_path"], as_attachment=True, download_name=submission["file_name"])


@app.get("/api/review-assignments/<assignment_key>/download")
def download_assigned_submission(assignment_key: str):
    user, error = require_role("student")
    if error:
        return error
    assignment = row(
        """SELECT ra.project_id,ra.target_team_id,p.review_open,p.grades_published
           FROM review_assignments ra JOIN projects p ON p.id=ra.project_id
           WHERE ra.assignment_key=? AND ra.reviewer_id=?""",
        (assignment_key, user["id"]),
    )
    if not assignment:
        return abort_json("互评任务不存在", 404)
    if not assignment["review_open"] or assignment["grades_published"]:
        return abort_json("互评通道当前不可用", 403)
    submission = row(
        """SELECT s.file_path,s.file_name FROM submissions s
           JOIN iterations i ON i.id=s.iteration_id
           WHERE s.team_id=? AND i.project_id=? AND s.status<>'withdrawn'
           ORDER BY s.submitted_at DESC,s.id DESC LIMIT 1""",
        (assignment["target_team_id"], assignment["project_id"]),
    )
    if not submission or not submission["file_path"] or not Path(submission["file_path"]).exists():
        return abort_json("该匿名成果暂无可下载文件", 404)
    extension = Path(submission["file_name"]).suffix.lower()
    anonymous_name = f"anonymous-submission{extension}" if extension else "anonymous-submission"
    return send_file(submission["file_path"], as_attachment=True, download_name=anonymous_name)


@app.get("/api/submissions/<int:submission_id>/versions")
def submission_versions(submission_id: int):
    user = current_user()
    submission = row("SELECT s.*,t.project_id FROM submissions s JOIN teams t ON t.id=s.team_id WHERE s.id=?", (submission_id,))
    if not submission:
        return abort_json("提交记录不存在", 404)
    selected_project(submission["project_id"], user)
    if user["role"] == "student" and not row("SELECT 1 FROM team_members WHERE team_id=? AND user_id=?", (submission["team_id"], user["id"])):
        return abort_json("只有本团队成员可查看版本历史", 403)
    return jsonify(
        {
            "ok": True,
            "versions": rows(
                "SELECT id,version,file_name,submitted_at FROM submission_versions WHERE submission_id=? ORDER BY version DESC",
                (submission_id,),
            ),
        }
    )


@app.post("/api/process-checks")
def create_process_check():
    user, error = require_role("assistant")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    project_id = int(data.get("project_id", 0))
    team_id = int(data.get("team_id", 0))
    iteration_id = int(data.get("iteration_id", 0))
    action = str(data.get("action", "")).strip()
    comment = str(data.get("comment", "")).strip()
    if action not in ("returned", "received", "scored") or not comment:
        return abort_json("请选择查收、退回或评分，并填写检查说明")
    project = selected_project(project_id, user)
    if project["grades_published"]:
        return abort_json("成绩已发布，过程检查已锁定", 403)
    submission = row(
        """SELECT s.id FROM submissions s JOIN iterations i ON i.id=s.iteration_id
           WHERE s.team_id=? AND s.iteration_id=? AND i.project_id=? AND s.status<>'withdrawn'""",
        (team_id, iteration_id, project_id),
    )
    if not submission:
        return abort_json("该团队在当前迭代没有有效提交")
    score = None
    if action in ("received", "scored"):
        try:
            score = parse_score(data.get("score"), "过程检查分")
        except APIError as exc:
            return abort_json(exc.message, exc.status)
    db = get_db()
    db.execute(
        """INSERT INTO process_checks(project_id,iteration_id,team_id,assistant_id,action,score,comment,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (project_id, iteration_id, team_id, user["id"], action, score, comment, now_iso()),
    )
    if action == "returned":
        db.execute("UPDATE submissions SET status='returned',returned_reason=?,lock_version=lock_version+1 WHERE id=?", (comment, submission["id"]))
    else:
        db.execute(
            """UPDATE submissions SET status='received',received_at=?,received_by=?,returned_reason=NULL,
               lock_version=lock_version+1 WHERE id=?""",
            (now_iso(), user["id"], submission["id"]),
        )
        refresh_process_score(project_id, team_id, user["id"])
    for member in rows("SELECT user_id FROM team_members WHERE team_id=?", (team_id,)):
        notify(
            member["user_id"], "成果检查结果",
            "成果已退回修改：" + comment if action == "returned" else f"成果已查收，过程检查分 {score}",
            "warning" if action == "returned" else "grade", "submissions",
        )
    audit(user["id"], "process_check", "submission", submission["id"], f"{action}：{comment}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "过程检查已记录"})


@app.post("/api/projects/<int:project_id>/remind-missing")
def remind_missing_submissions(project_id: int):
    user, error = require_role("assistant", "teacher")
    if error:
        return error
    selected_project(project_id, user)
    data = request.get_json(silent=True) or {}
    iteration_id = int(data.get("iteration_id", 0))
    iteration = row("SELECT * FROM iterations WHERE id=? AND project_id=?", (iteration_id, project_id))
    if not iteration:
        return abort_json("请选择有效迭代")
    missing = rows(
        """SELECT t.id,t.name FROM teams t WHERE t.project_id=? AND NOT EXISTS(
               SELECT 1 FROM submissions s WHERE s.team_id=t.id AND s.iteration_id=? AND s.status NOT IN ('withdrawn','returned')
           ) ORDER BY t.id""",
        (project_id, iteration_id),
    )
    for team in missing:
        for member in rows("SELECT user_id FROM team_members WHERE team_id=?", (team["id"],)):
            notify(member["user_id"], "成果催交通知", f"团队“{team['name']}”尚未提交“{iteration['name']}”成果，请及时处理。", "warning", "submissions")
    audit(user["id"], "remind", "iteration", iteration_id, f"批量催交 {len(missing)} 个团队", project_id)
    get_db().commit()
    return jsonify({"ok": True, "message": f"已向 {len(missing)} 个未提交团队发送提醒", "teams": missing})


@app.post("/api/reviews")
def submit_review():
    user, error = require_role("student")
    if error:
        return error
    data = request.get_json(force=True)
    project_id = int(data.get("project_id", 0))
    assignment_key = str(data.get("assignment_id", "")).strip()
    save_as_draft = str(data.get("status", "submitted")) == "draft"
    dimension_values = []
    for key, label in (
        ("completeness_score", "完成度"),
        ("innovation_score", "创新性"),
        ("documentation_score", "文档质量"),
    ):
        if key in data and data.get(key) not in (None, ""):
            try:
                dimension_values.append((key, parse_score(data.get(key), label)))
            except APIError as exc:
                return abort_json(exc.message, exc.status)
    if dimension_values and len(dimension_values) != 3:
        return abort_json("请完整填写完成度、创新性和文档质量三个评分维度")
    if dimension_values:
        score = round(sum(value for _, value in dimension_values) / 3, 2)
    else:
        try:
            score = float(data.get("score", -1))
        except (TypeError, ValueError):
            return abort_json("评分必须是数字")
    comment = str(data.get("comment", "")).strip()
    project = row("SELECT * FROM projects WHERE id=?", (project_id,))
    if not project:
        return abort_json("项目不存在", 404)
    if project.get("grades_published"):
        return abort_json("成绩已发布，互评已冻结", 403)
    if not project["review_open"]:
        return abort_json("互评尚未开启")

    selected_project(project_id, user)
    if project.get("review_deadline") and datetime.now() > parse_deadline(project["review_deadline"]):
        return abort_json("互评已截止")
    if score < 0 or score > 100 or (not save_as_draft and not comment):
        return abort_json("评分应为 0—100，正式提交时必须填写评语")
    assignment = row(
        "SELECT * FROM review_assignments WHERE project_id=? AND reviewer_id=? AND assignment_key=?",
        (project_id, user["id"], assignment_key),
    )
    if not assignment:
        return abort_json("该团队不在你的互评分配任务中", 403)
    target_team_id = assignment["target_team_id"]
    own = row("SELECT t.id FROM teams t JOIN team_members tm ON tm.team_id=t.id WHERE t.project_id=? AND tm.user_id=?", (project_id, user["id"]))
    if own and own["id"] == target_team_id:
        return abort_json("不能评审自己的团队")
    db = get_db()
    dimensions = dict(dimension_values)
    db.execute(
        """INSERT INTO peer_reviews(
               project_id,reviewer_id,target_team_id,completeness_score,innovation_score,
               documentation_score,score,comment,created_at,status
           ) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(project_id,reviewer_id,target_team_id)
           DO UPDATE SET completeness_score=excluded.completeness_score,
               innovation_score=excluded.innovation_score,documentation_score=excluded.documentation_score,
               score=excluded.score,comment=excluded.comment,created_at=excluded.created_at,status=excluded.status""",
        (
            project_id, user["id"], target_team_id,
            dimensions.get("completeness_score"), dimensions.get("innovation_score"),
            dimensions.get("documentation_score"), score, comment, now_iso(),
            "draft" if save_as_draft else "submitted",
        ),
    )
    db.execute(
        "UPDATE review_assignments SET status=?,completed_at=? WHERE project_id=? AND reviewer_id=? AND target_team_id=?",
        ("pending" if save_as_draft else "completed", None if save_as_draft else now_iso(), project_id, user["id"], target_team_id),
    )
    if not save_as_draft:
        refresh_review_alert(project_id, target_team_id)
    audit(user["id"], "review_draft" if save_as_draft else "review", "team", target_team_id, f"{'保存草稿' if save_as_draft else '提交互评'}：{score}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "互评草稿已保存" if save_as_draft else "互评已提交", "score": score})


@app.post("/api/projects/<int:project_id>/toggle-review")
def toggle_review(project_id: int):
    user, error = require_role("teacher")
    if error:
        return error
    project = selected_project(project_id, user)
    if project["grades_published"]:
        return abort_json("成绩已发布，不能再变更互评状态", 403)
    new_state = 0 if project["review_open"] else 1
    db = get_db()
    if new_state:
        teams = rows("SELECT id FROM teams WHERE project_id=? ORDER BY id", (project_id,))
        eligible_teams = rows(
            """SELECT DISTINCT t.id FROM teams t JOIN submissions s ON s.team_id=t.id
               JOIN iterations i ON i.id=s.iteration_id
               WHERE t.project_id=? AND i.project_id=? AND s.status NOT IN ('withdrawn','returned') ORDER BY t.id""",
            (project_id, project_id),
        )
        if len(eligible_teams) < 2:
            return abort_json("至少需要两个团队才能开启互评")
        for team in eligible_teams:
            try:
                ensure_team_ready(team["id"])
            except APIError as exc:
                return abort_json(f"团队 {team['id']}：{exc.message}")
        team_ids = [item["id"] for item in eligible_teams]
        members = rows(
            """SELECT tm.user_id,tm.team_id FROM team_members tm JOIN teams t ON t.id=tm.team_id
               WHERE t.project_id=? ORDER BY tm.user_id""",
            (project_id,),
        )
        for index, member in enumerate(members):
            candidates = [team_id for team_id in team_ids if team_id != member["team_id"]]
            if candidates:
                offset = index % len(candidates)
                candidates = candidates[offset:] + candidates[:offset]
            for target_team_id in candidates[:3]:
                inserted = db.execute(
                    """INSERT OR IGNORE INTO review_assignments(
                           project_id,reviewer_id,target_team_id,status,created_at,assignment_key
                       ) VALUES(?,?,?,'pending',?,?)""",
                    (project_id, member["user_id"], target_team_id, now_iso(), uuid.uuid4().hex),
                )
                if inserted.rowcount:
                    notify(member["user_id"], "新的互评任务", "请在截止时间前完成分配的团队互评。", "review", "reviews")
        placeholders = ",".join("?" for _ in team_ids)
        db.execute(
            f"""UPDATE submissions SET status='reviewing',lock_version=lock_version+1
                WHERE team_id IN ({placeholders}) AND status IN ('submitted','received')""",
            team_ids,
        )
    else:
        db.execute("UPDATE submissions SET status='received' WHERE status='reviewing' AND team_id IN (SELECT id FROM teams WHERE project_id=?)", (project_id,))
    db.execute("UPDATE projects SET review_open=? WHERE id=?", (new_state, project_id))
    audit(user["id"], "toggle_review", "project", project_id, "开启互评" if new_state else "关闭互评", project_id)
    db.commit()
    message = "互评已开启" if new_state else "互评已关闭"
    if new_state and len(team_ids) < 4:
        message += f"；当前仅 {len(team_ids)} 个可评团队，已按实际数量降级轮转分配"
    return jsonify({"ok": True, "message": message})


@app.post("/api/review-alerts/<int:alert_id>/resolve")
def resolve_review_alert(alert_id: int):
    user, error = require_role("teacher", "assistant")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    resolution = str(data.get("resolution", "")).strip()
    if not resolution:
        return abort_json("请填写复核结论")
    alert = row("SELECT * FROM review_alerts WHERE id=?", (alert_id,))
    if not alert:
        return abort_json("预警不存在", 404)
    selected_project(alert["project_id"], user)
    get_db().execute(
        "UPDATE review_alerts SET status='resolved',resolved_at=?,resolved_by=?,resolution=? WHERE id=?",
        (now_iso(), user["id"], resolution, alert_id),
    )
    audit(user["id"], "resolve_alert", "review_alert", alert_id, f"异常互评复核：{resolution}", alert["project_id"])
    get_db().commit()
    return jsonify({"ok": True, "message": "异常互评预警已处理"})


def upsert_score(kind: str):
    roles = ("assistant",) if kind == "process" else ("teacher",)
    user, error = require_role(*roles)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    project_id = int(data.get("project_id", 0))
    team_id = int(data.get("team_id", 0))
    try:
        score = float(data.get("score", -1))
    except (TypeError, ValueError):
        return abort_json("评分必须是数字")
    comment = str(data.get("comment", "")).strip() or "无"
    if score < 0 or score > 100:
        return abort_json("评分应为 0—100")
    project = selected_project(project_id, user)
    if project["grades_published"]:
        return abort_json("成绩已经发布，评分已锁定")
    if not row("SELECT 1 FROM teams WHERE id=? AND project_id=?", (team_id, project_id)):
        return abort_json("团队不属于当前项目", 400)
    table = "process_scores" if kind == "process" else "final_scores"
    actor_column = "assistant_id" if kind == "process" else "teacher_id"
    db = get_db()
    db.execute(
        f"""INSERT INTO {table}(project_id,team_id,{actor_column},score,comment,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(project_id,team_id)
            DO UPDATE SET {actor_column}=excluded.{actor_column},score=excluded.score,
                          comment=excluded.comment,updated_at=excluded.updated_at""",
        (project_id, team_id, user["id"], score, comment, now_iso()),
    )
    audit(user["id"], "score", "team", team_id, f"记录{'过程' if kind == 'process' else '终评'}分：{score}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "评分已保存"})


@app.post("/api/scores/process")
def process_score():
    return upsert_score("process")


@app.post("/api/scores/final")
def final_score():
    return upsert_score("final")


@app.post("/api/individual-adjustments")
def save_individual_adjustment():
    user, error = require_role("teacher")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    project_id = int(data.get("project_id", 0))
    user_id = str(data.get("user_id", "")).strip()
    reason = str(data.get("reason", "")).strip()
    try:
        coefficient = float(data.get("coefficient", 1))
        manual_deduction = float(data.get("manual_deduction", 0))
    except (TypeError, ValueError):
        return abort_json("折算系数和扣分必须是数字")
    project = selected_project(project_id, user)
    if project["grades_published"]:
        return abort_json("成绩已发布，个人成绩核定已锁定", 403)
    if not 0 <= coefficient <= 1:
        return abort_json("个人折算系数必须在 0—1 之间")
    if not 0 <= manual_deduction <= 100:
        return abort_json("个人扣分必须在 0—100 之间")
    if not reason:
        return abort_json("调整个人成绩必须填写理由")
    member = row(
        """SELECT tm.team_id,u.name FROM team_members tm JOIN teams t ON t.id=tm.team_id
           JOIN users u ON u.id=tm.user_id WHERE t.project_id=? AND tm.user_id=?""",
        (project_id, user_id),
    )
    if not member:
        return abort_json("该学生不属于当前项目", 400)
    db = get_db()
    db.execute(
        """INSERT INTO individual_grade_adjustments(
               project_id,team_id,user_id,coefficient,manual_deduction,reason,updated_by,updated_at
           ) VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(project_id,user_id) DO UPDATE SET
               team_id=excluded.team_id,coefficient=excluded.coefficient,
               manual_deduction=excluded.manual_deduction,reason=excluded.reason,
               updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
        (project_id, member["team_id"], user_id, coefficient, manual_deduction, reason, user["id"], now_iso()),
    )
    audit(
        user["id"], "adjust_grade", "user", user_id,
        f"核定个人成绩：系数 {coefficient}，人工扣分 {manual_deduction}，理由：{reason}", project_id,
    )
    db.commit()
    return jsonify({"ok": True, "message": "个人成绩核定已保存"})


@app.post("/api/projects/<int:project_id>/publish-grades")
def publish_grades(project_id: int):
    user, error = require_role("teacher")
    if error:
        return error
    project = selected_project(project_id, user)
    if project["grades_published"]:
        return jsonify({"ok": True, "message": "成绩已经发布，无需重复操作"})
    if row("SELECT 1 FROM review_alerts WHERE project_id=? AND status='open'", (project_id,)):
        return abort_json("仍有异常互评分预警未复核，暂不能发布成绩", 409)
    if row("SELECT 1 FROM grade_appeals WHERE project_id=? AND status='pending'", (project_id,)):
        return abort_json("仍有成绩申诉未处理，暂不能重新发布成绩", 409)
    for team in rows("SELECT id FROM teams WHERE project_id=?", (project_id,)):
        try:
            ensure_team_ready(team["id"])
        except APIError as exc:
            return abort_json(f"团队 {team['id']}：{exc.message}")
    grades = live_gradebook(project_id)
    if not grades or any(item["total"] is None or any(person["individual_score"] is None for person in item["individuals"]) for item in grades):
        return abort_json("仍有团队缺少互评、过程分或终评分，暂不能发布")
    db = get_db()
    version = row("SELECT COALESCE(MAX(version),0)+1 AS version FROM grade_publications WHERE project_id=?", (project_id,))["version"]
    db.execute("UPDATE grade_publications SET active=0 WHERE project_id=?", (project_id,))
    db.execute(
        "INSERT INTO grade_publications(project_id,published_by,published_at,version,active) VALUES(?,?,?,?,1)",
        (project_id, user["id"], now_iso(), version),
    )
    publication_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    for grade in grades:
        db.execute(
            """INSERT INTO team_grade_snapshots(
                   publication_id,project_id,team_id,team_name,peer_score,peer_count,process_score,final_score,total
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                publication_id, project_id, grade["team_id"], grade["team_name"], grade["peer_score"],
                grade["peer_count"], grade["process_score"], grade["final_score"], grade["total"],
            ),
        )
        for person in grade["individuals"]:
            db.execute(
                """INSERT INTO individual_grade_snapshots(
                       publication_id,project_id,team_id,user_id,user_name,peer_score,coefficient,
                       manual_deduction,missing_review_penalty,final_score
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    publication_id, project_id, grade["team_id"], person["user_id"], person["user_name"],
                    grade["peer_score"], person["coefficient"], person["manual_deduction"],
                    person["missing_review_penalty"], person["individual_score"],
                ),
            )
    db.execute("UPDATE projects SET grades_published=1,review_open=0 WHERE id=?", (project_id,))
    db.execute("UPDATE teams SET status='completed' WHERE project_id=?", (project_id,))
    db.execute(
        """UPDATE submissions SET status='archived' WHERE team_id IN
           (SELECT id FROM teams WHERE project_id=?) AND status<>'withdrawn'""",
        (project_id,),
    )
    for team in rows("SELECT id FROM teams WHERE project_id=?", (project_id,)):
        for member in rows("SELECT user_id FROM team_members WHERE team_id=?", (team["id"],)):
            notify(member["user_id"], "成绩已发布", "项目综合成绩已发布，请进入成绩页面查看。", "grade", "grades")
    audit(user["id"], "publish", "grades", project_id, f"发布项目成绩 v{version} 并生成不可变快照", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "成绩已发布", "version": version})


@app.post("/api/projects/<int:project_id>/unpublish-grades")
def unpublish_grades(project_id: int):
    user, error = require_role("teacher", "admin")
    if error:
        return error
    project = selected_project(project_id, user)
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason", "")).strip()
    if not project["grades_published"]:
        return abort_json("当前成绩尚未发布")
    if not reason:
        return abort_json("撤回发布必须填写理由")
    publication = active_publication(project_id)
    if not publication:
        return abort_json("未找到当前发布版本", 409)
    db = get_db()
    db.execute(
        """UPDATE grade_publications SET active=0,withdrawn_at=?,withdrawn_by=?,withdrawal_reason=?
           WHERE id=?""",
        (now_iso(), user["id"], reason, publication["id"]),
    )
    db.execute("UPDATE projects SET grades_published=0 WHERE id=?", (project_id,))
    db.execute("UPDATE teams SET status='active' WHERE project_id=?", (project_id,))
    db.execute(
        """UPDATE submissions SET status='submitted' WHERE team_id IN
           (SELECT id FROM teams WHERE project_id=?) AND status='archived'""",
        (project_id,),
    )
    audit(user["id"], "unpublish", "grades", project_id, f"撤回成绩 v{publication['version']}：{reason}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "成绩发布已撤回，历史快照已保留"})


@app.get("/api/projects/<int:project_id>/grades.csv")
def export_grades(project_id: int):
    user, error = require_role("teacher", "admin")
    if error:
        return error
    project = selected_project(project_id, user)
    if not project["grades_published"] or not active_publication(project_id):
        return abort_json("请先发布成绩，再导出归档表", 409)
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["团队", "互评分", "过程分", "终评分", "总分"])
    for item in gradebook(project_id):
        writer.writerow([item["team_name"], item["peer_score"], item["process_score"], item["final_score"], item["total"]])
    audit(user["id"], "export", "grades", project_id, "导出 CSV 成绩表", project_id)
    get_db().commit()
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=project-{project_id}-grades.csv"},
    )


@app.get("/api/projects/<int:project_id>/grades.xlsx")
def export_grades_xlsx(project_id: int):
    user, error = require_role("teacher", "admin")
    if error:
        return error
    project = selected_project(project_id, user)
    publication = active_publication(project_id)
    if not project["grades_published"] or not publication:
        return abort_json("请先发布成绩，再导出归档表", 409)
    grades = gradebook(project_id)
    workbook = Workbook()
    summary = workbook.active
    summary.title = "团队汇总"
    summary.append(["团队", "成员名单", "互评分", "过程分", "教师终评", "团队总分"])
    detail = workbook.create_sheet("个人明细")
    detail.append(["团队", "学号", "姓名", "互评分", "折算系数", "人工扣分", "缺评扣分", "个人最终分"])
    metadata = workbook.create_sheet("发布信息")
    metadata.append(["项目", project["title"]])
    metadata.append(["成绩版本", publication["version"]])
    metadata.append(["发布时间", publication["published_at"]])
    metadata.append(["发布人", user["name"]])
    metadata.append(["计算公式", "团队总分×个人折算系数-人工扣分-缺评扣分，结果限制在0-100"])
    for grade in grades:
        member_names = "、".join(person["user_name"] for person in grade["individuals"])
        summary.append([grade["team_name"], member_names, grade["peer_score"], grade["process_score"], grade["final_score"], grade["total"]])
        for person in grade["individuals"]:
            detail.append(
                [
                    grade["team_name"], person["user_id"], person["user_name"], grade["peer_score"],
                    person["coefficient"], person["manual_deduction"], person["missing_review_penalty"],
                    person["individual_score"],
                ]
            )
    for sheet in (summary, detail, metadata):
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="3457D5")
            cell.alignment = Alignment(horizontal="center")
        for column in sheet.columns:
            width = min(40, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
            sheet.column_dimensions[column[0].column_letter].width = width
    output = io.BytesIO()
    workbook.save(output)
    content = output.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    audit(user["id"], "export", "grades", project_id, f"导出 Excel 成绩归档 v{publication['version']}，SHA-256 {digest}", project_id)
    get_db().commit()
    filename = f"project-{project_id}-grades-v{publication['version']}.xlsx"
    return Response(
        content,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}", "X-Content-SHA256": digest},
    )


@app.get("/api/projects/<int:project_id>/grades.pdf")
def export_grades_pdf(project_id: int):
    user, error = require_role("teacher", "admin")
    if error:
        return error
    project = selected_project(project_id, user)
    publication = active_publication(project_id)
    if not project["grades_published"] or not publication:
        return abort_json("请先发布成绩，再导出 PDF 归档表", 409)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.fontName = "STSong-Light"
    normal_style = styles["BodyText"]
    normal_style.fontName = "STSong-Light"
    story = [
        Paragraph(f"{project['title']} - 成绩归档表", title_style),
        Paragraph(f"成绩版本：V{publication['version']}　发布时间：{publication['published_at']}", normal_style),
        Spacer(1, 6 * mm),
    ]
    data = [["团队", "成员", "互评分", "过程分", "教师终评", "团队总分", "个人成绩明细"]]
    for grade in gradebook(project_id):
        members = "、".join(person["user_name"] for person in grade["individuals"])
        individuals = "；".join(f"{person['user_name']} {person['individual_score']}" for person in grade["individuals"])
        data.append([
            grade["team_name"], members, grade["peer_score"], grade["process_score"],
            grade["final_score"], grade["total"], individuals,
        ])
    table = Table(data, repeatRows=1, colWidths=[32 * mm, 50 * mm, 22 * mm, 22 * mm, 24 * mm, 24 * mm, 75 * mm])
    table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3457D5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 1), (5, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(table)
    document.build(story)
    content = output.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    audit(user["id"], "export", "grades", project_id, f"导出 PDF 成绩归档 v{publication['version']}，SHA-256 {digest}", project_id)
    get_db().commit()
    return Response(
        content,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=project-{project_id}-grades-v{publication['version']}.pdf", "X-Content-SHA256": digest},
    )


@app.post("/api/grade-appeals")
def create_grade_appeal():
    user, error = require_role("student")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    project_id = int(data.get("project_id", 0))
    reason = str(data.get("reason", "")).strip()
    project = selected_project(project_id, user)
    if not project["grades_published"]:
        return abort_json("成绩发布后才能申请复核")
    if not reason:
        return abort_json("请填写具体复核理由")
    if row("SELECT 1 FROM grade_appeals WHERE project_id=? AND user_id=? AND status='pending'", (project_id, user["id"])):
        return abort_json("你已有一条待处理的成绩复核申请")
    db = get_db()
    db.execute(
        "INSERT INTO grade_appeals(project_id,user_id,reason,status,created_at) VALUES(?,?,?,'pending',?)",
        (project_id, user["id"], reason, now_iso()),
    )
    appeal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    recipients = rows(
        """SELECT c.teacher_id AS user_id FROM courses c JOIN projects p ON p.course_id=c.id WHERE p.id=?
           UNION SELECT id AS user_id FROM users WHERE role='admin' AND active=1""",
        (project_id,),
    )
    for recipient in recipients:
        notify(recipient["user_id"], "新的成绩复核申请", f"{user['name']} 提交了成绩复核申请。", "warning", "grades")
    audit(user["id"], "appeal", "grade", appeal_id, f"申请成绩复核：{reason}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "成绩复核申请已提交"})


@app.post("/api/grade-appeals/<int:appeal_id>/resolve")
def resolve_grade_appeal(appeal_id: int):
    user, error = require_role("teacher", "admin")
    if error:
        return error
    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "")).strip()
    result = str(data.get("result", "")).strip()
    if decision not in ("approved", "rejected") or not result:
        return abort_json("请选择处理结果并填写复核结论")
    appeal = row("SELECT * FROM grade_appeals WHERE id=?", (appeal_id,))
    if not appeal or appeal["status"] != "pending":
        return abort_json("复核申请不存在或已处理", 404)
    selected_project(appeal["project_id"], user)
    get_db().execute(
        """UPDATE grade_appeals SET status=?,result=?,resolved_at=?,resolved_by=? WHERE id=?""",
        (decision, result, now_iso(), user["id"], appeal_id),
    )
    notify(appeal["user_id"], "成绩复核已处理", result, "grade", "grades")
    audit(user["id"], "resolve_appeal", "grade_appeal", appeal_id, f"{decision}：{result}", appeal["project_id"])
    get_db().commit()
    return jsonify({"ok": True, "message": "成绩复核已处理"})


@app.post("/api/notifications/<int:notification_id>/read")
def mark_notification_read(notification_id: int):
    user = current_user()
    db = get_db()
    result = db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notification_id, user["id"]))
    db.commit()
    if result.rowcount == 0:
        return abort_json("通知不存在", 404)
    return jsonify({"ok": True, "message": "通知已读"})


@app.get("/api/audit/verify")
def verify_audit_log():
    user, error = require_role("admin")
    if error:
        return error
    valid, broken_id = verify_audit_chain()
    return jsonify({"ok": True, "valid": valid, "broken_log_id": broken_id, "message": "审计链完整" if valid else f"审计链在日志 #{broken_id} 处校验失败"})


@app.post("/api/admin/backup")
def create_database_backup():
    user, error = require_role("admin")
    if error:
        return error
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"platform-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    audit(user["id"], "backup", "database", backup_path.name, "创建数据库全量备份")
    get_db().commit()
    target = sqlite3.connect(backup_path)
    try:
        get_db().backup(target)
    finally:
        target.close()
    return jsonify({"ok": True, "message": "数据库备份已完成", "file": str(backup_path), "size": backup_path.stat().st_size})


@app.post("/api/notifications/read-all")
def mark_all_notifications_read():
    user = current_user()
    get_db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user["id"],))
    get_db().commit()
    return jsonify({"ok": True, "message": "已全部标为已读"})


@app.errorhandler(413)
def too_large(_error):
    return abort_json("上传文件超过 200MB 限制", 413)


@app.errorhandler(APIError)
def api_error(error):
    return abort_json(error.message, error.status)


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return abort_json("接口或数据不存在", 404)
    return render_template("index.html"), 404


@app.errorhandler(Exception)
def unexpected_error(error):
    if app.config.get("TESTING"):
        raise error
    app.logger.exception("Unhandled error")
    if request.path.startswith("/api/"):
        return abort_json("服务器处理失败，请稍后重试", 500)
    return "Internal Server Error", 500


with app.app_context():
    init_db()


if __name__ == "__main__":
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", "5000"))
    if os.environ.get("PLATFORM_DESKTOP") == "1":
        try:
            from waitress import serve

            serve(app, host=host, port=port, threads=6)
        except ImportError:
            app.run(host=host, port=port, debug=False, threaded=True)
    else:
        app.run(host=host, port=port, debug=False, threaded=True)


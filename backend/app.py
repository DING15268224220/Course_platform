from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import secrets
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template, request, send_file, session
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
    SESSION_COOKIE_SECURE=False,
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
    if user["role"] == "teacher":
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
    get_db().execute(
        "INSERT INTO audit_logs(user_id, action, entity, entity_id, detail, created_at, project_id) VALUES(?,?,?,?,?,?,?)",
        (user_id, action, entity, str(entity_id), detail, now_iso(), project_id),
    )


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


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('teacher','assistant','student')),
            password_hash TEXT,
            active INTEGER NOT NULL DEFAULT 1
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
            UNIQUE(team_id, iteration_id)
        );
        CREATE TABLE IF NOT EXISTS peer_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            reviewer_id TEXT NOT NULL REFERENCES users(id),
            target_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            score REAL NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL,
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
            project_id INTEGER REFERENCES projects(id)
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
        """
    )
    ensure_column(db, "users", "password_hash", "TEXT")
    ensure_column(db, "users", "active", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(db, "projects", "review_deadline", "TEXT")
    ensure_column(db, "projects", "published_at", "TEXT")
    ensure_column(db, "projects", "updated_at", "TEXT")
    ensure_column(db, "notifications", "kind", "TEXT NOT NULL DEFAULT 'info'")
    ensure_column(db, "notifications", "target_page", "TEXT NOT NULL DEFAULT 'overview'")
    ensure_column(db, "audit_logs", "project_id", "INTEGER")
    db.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_teams_project ON teams(project_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_iteration ON submissions(iteration_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,is_read);
        CREATE INDEX IF NOT EXISTS idx_logs_project ON audit_logs(project_id,created_at);
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
        [(course_id, uid) for uid, _, _ in demo_users if uid != "t1"],
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
    
    # 遍历每一个学生，给他们分配 3 个其他团队的任务并预设分值
    for student_id in student_ids:
        # 找到这个学生自己的团队索引
        own_team_index = -1
        for i, (_, members, _, _, _) in enumerate(team_specs):
            if student_id in members:
                own_team_index = i
                break
        
        # 找到其他 3 个团队
        other_team_indices = [i for i in range(len(team_specs)) if i != own_team_index]
        
        # 给该学生分配 3 个任务
        for target_index in other_team_indices:
            target_team_id = team_ids[target_index]
            target_team_name = team_specs[target_index][0]
            
            # 预设分值：使用该团队原本的基准分，随机浮动 -3 到 +3 分，让数据更真实
            import random
            base_score = team_specs[target_index][2]
            score = base_score + random.randint(-3, 3)
            score = max(0, min(100, score))
            
            # 写入互评分配表
            db.execute(
                "INSERT INTO review_assignments(project_id,reviewer_id,target_team_id,status,created_at,completed_at) VALUES(?,?,?,'completed',?,?)",
                (project_id, student_id, target_team_id, now_iso(), now_iso())
            )
            # 写入互评分数表
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


def gradebook(project_id: int):
    project = row("SELECT * FROM projects WHERE id=?", (project_id,))
    if not project:
        return []
    teams = rows("SELECT * FROM teams WHERE project_id=? ORDER BY id", (project_id,))
    result = []
    for team in teams:
        # 【修改部分】获取该团队所有互评分数
        peer_rows = rows("SELECT score FROM peer_reviews WHERE project_id=? AND target_team_id=? ORDER BY score ASC", (project_id, team["id"]))
        scores = [r["score"] for r in peer_rows]
        count = len(scores)
        
        # 剔除最高最低分
        if count >= 3:
            valid_scores = scores[1:-1]
            peer_score = round(sum(valid_scores) / len(valid_scores), 2)
        elif count > 0:
            peer_score = round(sum(scores) / count, 2)
        else:
            peer_score = None

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
        result.append(
            {
                "team_id": team["id"],
                "team_name": team["name"],
                "peer_score": peer_score,
                "peer_count": count,
                "process_score": process_score,
                "final_score": final_score,
                "total": total,
            }
        )
    return result


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "course-project-platform", "time": now_iso()})


@app.get("/api/demo-users")
def demo_users():
    if not app.config.get("DEMO_MODE"):
        return jsonify({"ok": True, "users": []})
    return jsonify(
        {
            "ok": True,
            "users": rows(
                "SELECT id,name,role FROM users WHERE active=1 ORDER BY CASE role WHEN 'teacher' THEN 1 WHEN 'assistant' THEN 2 ELSE 3 END,id"
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
    if not user or not user.get("active", 1) or not check_password_hash(user.get("password_hash") or "", password):
        raise APIError("账号或密码错误", 401)
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
    if user["role"] == "teacher":
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
        projects = rows(
            f"""SELECT p.*,c.name AS course_name,c.term FROM projects p JOIN courses c ON c.id=p.course_id
                 WHERE p.course_id IN ({placeholders}) AND p.status<>'archived' ORDER BY p.id DESC""",
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
        teams = rows(
            """SELECT t.*,GROUP_CONCAT(u.name,'、') AS members,COUNT(tm.user_id) AS member_count,
               MAX(CASE WHEN tm.is_leader=1 THEN u.name END) AS leader_name
               FROM teams t LEFT JOIN team_members tm ON tm.team_id=t.id LEFT JOIN users u ON u.id=tm.user_id
               WHERE t.project_id=? GROUP BY t.id ORDER BY t.id""",
            (active_id,),
        )
        my_team = row(
            """SELECT t.*,tm.is_leader FROM teams t JOIN team_members tm ON tm.team_id=t.id
               WHERE t.project_id=? AND tm.user_id=?""",
            (active_id, user["id"]),
        )
        if user["role"] in ("teacher", "assistant"):
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
            # 修改：返回 '匿名团队' AS name
            review_targets = rows(
                """SELECT t.id, '匿名团队' AS name, ra.status, ra.completed_at, pr.score AS current_average,
                   CASE WHEN pr.id IS NULL THEN 0 ELSE 1 END AS reviewed
                   FROM review_assignments ra JOIN teams t ON t.id=ra.target_team_id
                   LEFT JOIN peer_reviews pr ON pr.project_id=ra.project_id AND pr.reviewer_id=ra.reviewer_id
                        AND pr.target_team_id=ra.target_team_id
                   WHERE ra.project_id=? AND ra.reviewer_id=? ORDER BY t.id""",
                (active_id, user["id"]),
            )
        active_grades = gradebook(active_id)
        if user["role"] in ("teacher", "assistant"):
            active["gradebook"] = active_grades
        elif active["grades_published"] and my_team:
            active["gradebook"] = [item for item in active_grades if item["team_id"] == my_team["id"]]
        if user["role"] in ("teacher", "assistant"):
            visible_logs = rows(
                """SELECT l.*,u.name AS user_name,u.role AS user_role FROM audit_logs l JOIN users u ON u.id=l.user_id
                   WHERE l.project_id=? OR (l.project_id IS NULL AND l.entity_id=?) ORDER BY l.id DESC LIMIT 100""",
                (active_id, str(active_id)),
            )
    return jsonify(
        {
            "ok": True,
            "csrf_token": session.get("csrf_token"),
            "courses": courses,
            "users": [{key: user[key] for key in ("id", "name", "role")}],
            "current_user": user,
            "projects": projects,
            "active_project_id": active["id"] if active else None,
            "teams": teams,
            "submissions": submissions,
            "my_team": my_team,
            "review_targets": review_targets,
            "notifications": rows("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 20", (user["id"],)),
            "logs": visible_logs,
        }
    )


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
            "published",
            0,
            0,
            now_iso(),
            data.get("review_deadline") or data["overall_deadline"],
            now_iso(),
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
    audit(user["id"], "publish", "project", project_id, f"发布项目：{data['title'].strip()}", project_id)
    for member in rows("SELECT user_id FROM course_members WHERE course_id=?", (course_id,)):
        notify(member["user_id"], "新项目已发布", data["title"].strip(), "project", "projects")
    db.commit()
    return jsonify({"ok": True, "message": "项目发布成功", "project_id": project_id})


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
    if datetime.now() > parse_deadline(team["team_deadline"]):
        return abort_json("已超过组队截止时间")
    if row("SELECT 1 FROM team_members tm JOIN teams t ON t.id=tm.team_id WHERE tm.user_id=? AND t.project_id=?", (user["id"], team["project_id"])):
        return abort_json("你已加入该项目的团队")
    count = row("SELECT COUNT(*) AS n FROM team_members WHERE team_id=?", (team_id,))["n"]
    if count >= 5:
        return abort_json("团队已达到 5 人上限")
    db = get_db()
    db.execute("INSERT INTO team_members VALUES(?,?,0)", (team_id, user["id"]))
    selected_project(team["project_id"], user)
    audit(user["id"], "join", "team", team_id, f"加入团队：{team['name']}", team["project_id"])
    db.commit()
    return jsonify({"ok": True, "message": "已加入团队"})


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


@app.post("/api/submissions/<int:iteration_id>")
def upload_submission(iteration_id: int):
    user, error = require_role("student")
    if error:
        return error
    iteration = row("SELECT * FROM iterations WHERE id=?", (iteration_id,))
    if not iteration:
        return abort_json("迭代不存在", 404)
        
    # 新增：成绩发布后禁止上传
    project_check = row("SELECT grades_published FROM projects WHERE id=?", (iteration["project_id"],))
    if project_check and project_check["grades_published"]:
        return abort_json("成绩已发布，不能上传或修改成果", 403)

    membership = row(
        """SELECT t.id AS team_id, tm.is_leader FROM teams t JOIN team_members tm ON tm.team_id=t.id
           WHERE t.project_id=? AND tm.user_id=?""",
        (iteration["project_id"], user["id"]),
    )
    if not membership or not membership["is_leader"]:
        return abort_json("只有团队负责人可以上传成果", 403)
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
        db.execute(
            "UPDATE submissions SET file_name=?,file_path=?,submitted_at=?,status='submitted',version=version+1 WHERE id=?",
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
        
    # 新增：成绩发布后禁止撤回
    team_proj = row("SELECT project_id FROM teams WHERE id=?", (submission["team_id"],))
    project_check = row("SELECT grades_published FROM projects WHERE id=?", (team_proj["project_id"],))
    if project_check and project_check["grades_published"]:
        return abort_json("成绩已发布，不能撤回提交", 403)

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
            allowed = bool(
                row(
                    """SELECT 1 FROM review_assignments ra JOIN projects p ON p.id=ra.project_id
                       WHERE ra.project_id=? AND ra.reviewer_id=? AND ra.target_team_id=? AND p.review_open=1""",
                    (submission["project_id"], user["id"], submission["team_id"]),
                )
            )
    if not allowed:
        return abort_json("你无权下载该团队文件", 403)
    return send_file(submission["file_path"], as_attachment=True, download_name=submission["file_name"])


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


@app.post("/api/reviews")
def submit_review():
    user, error = require_role("student")
    if error:
        return error
    data = request.get_json(force=True)
    project_id = int(data.get("project_id", 0))
    target_team_id = int(data.get("target_team_id", 0))
    try:
        score = float(data.get("score", -1))
    except (TypeError, ValueError):
        return abort_json("评分必须是数字")
    comment = str(data.get("comment", "")).strip()
    project = row("SELECT * FROM projects WHERE id=?", (project_id,))
    if not project or not project["review_open"]:
        return abort_json("互评尚未开启")
        
    # 新增：成绩发布后禁止互评
    if project.get("grades_published"):
        return abort_json("成绩已发布，互评已冻结", 403)

    selected_project(project_id, user)
    if project.get("review_deadline") and datetime.now() > parse_deadline(project["review_deadline"]):
        return abort_json("互评已截止")
    if score < 0 or score > 100 or not comment:
        return abort_json("评分应为 0—100，且必须填写评语")
    own = row("SELECT t.id FROM teams t JOIN team_members tm ON tm.team_id=t.id WHERE t.project_id=? AND tm.user_id=?", (project_id, user["id"]))
    if own and own["id"] == target_team_id:
        return abort_json("不能评审自己的团队")
    assignment = row(
        "SELECT * FROM review_assignments WHERE project_id=? AND reviewer_id=? AND target_team_id=?",
        (project_id, user["id"], target_team_id),
    )
    if not assignment:
        return abort_json("该团队不在你的互评分配任务中", 403)
    db = get_db()
    db.execute(
        """INSERT INTO peer_reviews(project_id,reviewer_id,target_team_id,score,comment,created_at)
           VALUES(?,?,?,?,?,?) ON CONFLICT(project_id,reviewer_id,target_team_id)
           DO UPDATE SET score=excluded.score,comment=excluded.comment,created_at=excluded.created_at""",
        (project_id, user["id"], target_team_id, score, comment, now_iso()),
    )
    db.execute(
        "UPDATE review_assignments SET status='completed',completed_at=? WHERE project_id=? AND reviewer_id=? AND target_team_id=?",
        (now_iso(), project_id, user["id"], target_team_id),
    )
    audit(user["id"], "review", "team", target_team_id, f"提交互评分：{score}", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "互评已提交"})


@app.post("/api/projects/<int:project_id>/toggle-review")
def toggle_review(project_id: int):
    user, error = require_role("teacher")
    if error:
        return error
    project = selected_project(project_id, user)
    new_state = 0 if project["review_open"] else 1
    db = get_db()
    if new_state:
        teams = rows("SELECT id FROM teams WHERE project_id=? ORDER BY id", (project_id,))
        if len(teams) < 2:
            return abort_json("至少需要两个团队才能开启互评")
        for team in teams:
            try:
                ensure_team_ready(team["id"])
            except APIError as exc:
                return abort_json(f"团队 {team['id']}：{exc.message}")
            if not row(
                """SELECT 1 FROM submissions s JOIN iterations i ON i.id=s.iteration_id
                   WHERE s.team_id=? AND i.project_id=? AND s.status<>'withdrawn'""",
                (team["id"], project_id),
            ):
                return abort_json("所有团队至少提交一份有效成果后才能开启互评")
        team_ids = [item["id"] for item in teams]
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
                    """INSERT OR IGNORE INTO review_assignments(project_id,reviewer_id,target_team_id,status,created_at)
                       VALUES(?,?,?,'pending',?)""",
                    (project_id, member["user_id"], target_team_id, now_iso()),
                )
                if inserted.rowcount:
                    notify(member["user_id"], "新的互评任务", "请在截止时间前完成分配的团队互评。", "review", "reviews")
    db.execute("UPDATE projects SET review_open=? WHERE id=?", (new_state, project_id))
    audit(user["id"], "toggle_review", "project", project_id, "开启互评" if new_state else "关闭互评", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "互评已开启" if new_state else "互评已关闭"})


def upsert_score(kind: str):
    roles = ("assistant", "teacher") if kind == "process" else ("teacher",)
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


@app.post("/api/projects/<int:project_id>/publish-grades")
def publish_grades(project_id: int):
    user, error = require_role("teacher")
    if error:
        return error
    project = selected_project(project_id, user)
    if project["grades_published"]:
        return jsonify({"ok": True, "message": "成绩已经发布，无需重复操作"})
    for team in rows("SELECT id FROM teams WHERE project_id=?", (project_id,)):
        try:
            ensure_team_ready(team["id"])
        except APIError as exc:
            return abort_json(f"团队 {team['id']}：{exc.message}")
    grades = gradebook(project_id)
    if not grades or any(item["total"] is None for item in grades):
        return abort_json("仍有团队缺少互评、过程分或终评分，暂不能发布")
    db = get_db()
    db.execute("UPDATE projects SET grades_published=1 WHERE id=?", (project_id,))
    version = row("SELECT COALESCE(MAX(version),0)+1 AS version FROM grade_publications WHERE project_id=?", (project_id,))["version"]
    db.execute(
        "INSERT INTO grade_publications(project_id,published_by,published_at,version) VALUES(?,?,?,?)",
        (project_id, user["id"], now_iso(), version),
    )
    db.execute("UPDATE teams SET status='completed' WHERE project_id=?", (project_id,))
    for team in rows("SELECT id FROM teams WHERE project_id=?", (project_id,)):
        for member in rows("SELECT user_id FROM team_members WHERE team_id=?", (team["id"],)):
            notify(member["user_id"], "成绩已发布", "项目综合成绩已发布，请进入成绩页面查看。", "grade", "grades")
    audit(user["id"], "publish", "grades", project_id, "发布项目成绩", project_id)
    db.commit()
    return jsonify({"ok": True, "message": "成绩已发布"})


@app.get("/api/projects/<int:project_id>/grades.csv")
def export_grades(project_id: int):
    user, error = require_role("teacher")
    if error:
        return error
    selected_project(project_id, user)
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


@app.post("/api/notifications/<int:notification_id>/read")
def mark_notification_read(notification_id: int):
    user = current_user()
    db = get_db()
    result = db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notification_id, user["id"]))
    db.commit()
    if result.rowcount == 0:
        return abort_json("通知不存在", 404)
    return jsonify({"ok": True, "message": "通知已读"})


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


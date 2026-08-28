"""SQLite data access for the SkillBridge hackathon experience."""
import json
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "skillbridge.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"
LEGACY_MOCK_DATA_PATH = BASE_DIR / "data" / "mock_data.json"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_column_if_missing(conn, table, column, definition):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    # Smooth upgrade path for databases created by the earlier student-only build.
    _add_column_if_missing(conn, "students", "headline", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "students", "bio", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "opportunities", "location", "TEXT DEFAULT 'Remote / Hybrid'")
    _add_column_if_missing(conn, "opportunities", "duration", "TEXT DEFAULT 'Flexible'")
    _add_column_if_missing(conn, "opportunities", "posted_by_account_id", "INTEGER")
    _add_column_if_missing(conn, "opportunities", "created_at", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "applications", "status", "TEXT DEFAULT 'Submitted'")
    _add_column_if_missing(conn, "applications", "updated_at", "TEXT DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_opportunities_poster ON opportunities(posted_by_account_id)")
    _normalise_existing_skills(conn)
    conn.commit()
    if not conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]:
        _seed_data(conn)
    conn.close()


def _normalise_skill_name(name):
    """Use one internal spelling for skills so 'graphic design' and
    'graphic-design' always match across student profiles and job postings."""
    return "-".join(name.strip().lower().replace("_", " ").split())


def _normalise_existing_skills(conn):
    """Upgrade earlier demo data that may contain space-separated skill names."""
    for row in conn.execute("SELECT id, name FROM skills").fetchall():
        clean = _normalise_skill_name(row["name"])
        if clean == row["name"]:
            continue
        canonical = conn.execute("SELECT id FROM skills WHERE name=?", (clean,)).fetchone()
        if canonical:
            canonical_id, old_id = canonical["id"], row["id"]
            conn.execute("INSERT OR IGNORE INTO student_skills SELECT student_id, ? FROM student_skills WHERE skill_id=?", (canonical_id, old_id))
            conn.execute("INSERT OR IGNORE INTO opportunity_skills SELECT opportunity_id, ?, weight_type FROM opportunity_skills WHERE skill_id=?", (canonical_id, old_id))
            conn.execute("INSERT OR REPLACE INTO student_skill_levels SELECT student_id, ?, level, score FROM student_skill_levels WHERE skill_id=?", (canonical_id, old_id))
            conn.execute("DELETE FROM student_skills WHERE skill_id=?", (old_id,))
            conn.execute("DELETE FROM opportunity_skills WHERE skill_id=?", (old_id,))
            conn.execute("DELETE FROM student_skill_levels WHERE skill_id=?", (old_id,))
            conn.execute("DELETE FROM skills WHERE id=?", (old_id,))
        else:
            conn.execute("UPDATE skills SET name=? WHERE id=?", (clean, row["id"]))


def _skill(conn, name, category="General"):
    clean = _normalise_skill_name(name)
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (clean,)).fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO skills(name, category) VALUES (?, ?)", (clean, category)).lastrowid


def _seed_data(conn):
    opportunities = []
    if LEGACY_MOCK_DATA_PATH.exists():
        legacy = json.loads(LEGACY_MOCK_DATA_PATH.read_text(encoding="utf-8"))
        opportunities = legacy.get("opportunities", [])
    opportunities += [
        {"title": "UI/UX Design Intern", "company": "PixelForge Studio", "type": "Internship", "description": "Turn user research into accessible interfaces alongside a product design team.", "location": "Bengaluru / Hybrid", "duration": "3 months", "required_skills": ["graphic-design", "figma"], "preferred_skills": ["html", "css"]},
        {"title": "Biology Research Assistant", "company": "GreenLeaf Labs", "type": "Research", "description": "Support lab experiments, data capture, and evidence-led reporting on a live research project.", "location": "Pune / On-site", "duration": "6 months", "required_skills": ["lab-safety", "microscopy", "data-recording"], "preferred_skills": ["statistics", "report-writing"]},
        {"title": "Marketing & Content Intern", "company": "Northwind Media", "type": "Internship", "description": "Plan campaign content, interpret audience signals, and build a portfolio of published work.", "location": "Remote", "duration": "3 months", "required_skills": ["content-writing", "social-media"], "preferred_skills": ["seo", "graphic-design"]},
        {"title": "Data Analytics Apprentice", "company": "InsightForge", "type": "Apprenticeship", "description": "Learn to turn real operational data into dashboards and clear business decisions.", "location": "Remote / Hybrid", "duration": "4 months", "required_skills": ["python", "sql", "data-analysis"], "preferred_skills": ["statistics", "excel"]},
    ]
    for item in opportunities:
        if conn.execute("SELECT 1 FROM opportunities WHERE title=? AND company=?", (item.get("title"), item.get("company"))).fetchone():
            continue
        opp_id = conn.execute("""INSERT INTO opportunities(title, company, type, description, location, duration)
            VALUES (?, ?, ?, ?, ?, ?)""", (item.get("title", "Untitled"), item.get("company", "N/A"), item.get("type", "Internship"), item.get("description", ""), item.get("location", "Remote / Hybrid"), item.get("duration", "Flexible"))).lastrowid
        for name in item.get("required_skills", []):
            conn.execute("INSERT OR IGNORE INTO opportunity_skills VALUES (?, ?, 'required')", (opp_id, _skill(conn, name)))
        for name in item.get("preferred_skills", []):
            conn.execute("INSERT OR IGNORE INTO opportunity_skills VALUES (?, ?, 'preferred')", (opp_id, _skill(conn, name)))
    conn.commit()


def student_by_username(conn, username): return conn.execute("SELECT * FROM students WHERE username=?", (username,)).fetchone()
def student_by_id(conn, student_id): return conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
def account_by_username(conn, username): return conn.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()
def account_by_id(conn, account_id): return conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
def username_taken(conn, username): return bool(student_by_username(conn, username) or account_by_username(conn, username))


def create_student(conn, name, username, password_hash):
    ident = conn.execute("INSERT INTO students(name, username, password_hash) VALUES (?, ?, ?)", (name, username, password_hash)).lastrowid
    conn.commit(); return ident


def create_account(conn, role, name, username, password_hash, organisation, email):
    ident = conn.execute("INSERT INTO accounts(role, name, username, password_hash, organisation, email) VALUES (?, ?, ?, ?, ?, ?)", (role, name, username, password_hash, organisation, email)).lastrowid
    conn.commit(); return ident


def student_skills(conn, student_id, include_levels=False):
    rows = conn.execute("""SELECT skills.name, COALESCE(student_skill_levels.level, 'Beginner') level,
        COALESCE(student_skill_levels.score, 0) score FROM student_skills JOIN skills ON skills.id=student_skills.skill_id
        LEFT JOIN student_skill_levels ON student_skill_levels.student_id=student_skills.student_id AND student_skill_levels.skill_id=skills.id
        WHERE student_skills.student_id=? ORDER BY skills.name""", (student_id,)).fetchall()
    return [dict(row) for row in rows] if include_levels else [row["name"] for row in rows]


def set_student_skills(conn, student_id, names, score=0, level="Beginner", results=None):
    conn.execute("DELETE FROM student_skills WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM student_skill_levels WHERE student_id=?", (student_id,))
    for name in {s.strip().lower() for s in names if s and s.strip()}:
        skill_id = _skill(conn, name)
        result = (results or {}).get(name, {})
        skill_level = result.get("level", level)
        skill_score = result.get("score", score)
        conn.execute("INSERT OR IGNORE INTO student_skills VALUES (?, ?)", (student_id, skill_id))
        conn.execute("INSERT OR REPLACE INTO student_skill_levels VALUES (?, ?, ?, ?)", (student_id, skill_id, skill_level, skill_score))
    conn.commit()


def opportunities_with_skills(conn, poster_id=None):
    sql = "SELECT o.*, a.organisation poster_organisation FROM opportunities o LEFT JOIN accounts a ON a.id=o.posted_by_account_id"
    args = []
    if poster_id:
        sql += " WHERE o.posted_by_account_id=?"; args.append(poster_id)
    sql += " ORDER BY o.created_at DESC, o.id DESC"
    result = []
    for opp in conn.execute(sql, args).fetchall():
        grouped = {"required": [], "preferred": []}
        for row in conn.execute("""SELECT skills.name, opportunity_skills.weight_type FROM opportunity_skills
            JOIN skills ON skills.id=opportunity_skills.skill_id WHERE opportunity_id=?""", (opp["id"],)):
            grouped[row["weight_type"]].append(row["name"])
        data = dict(opp); data.update(required_skills=grouped["required"], preferred_skills=grouped["preferred"]); result.append(data)
    return result


def create_opportunity(conn, account_id, company, data):
    opp_id = conn.execute("""INSERT INTO opportunities(title, company, type, description, location, duration, posted_by_account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)""", (data["title"], company, data["type"], data["description"], data["location"], data["duration"], account_id)).lastrowid
    for weight, key in (("required", "required_skills"), ("preferred", "preferred_skills")):
        for name in data.get(key, []): conn.execute("INSERT OR IGNORE INTO opportunity_skills VALUES (?, ?, ?)", (opp_id, _skill(conn, name), weight))
    conn.commit(); return opp_id


def applications_for_student(conn, student_id):
    return [dict(row) for row in conn.execute("""SELECT ap.*, o.title, o.company, o.type, o.location FROM applications ap
        JOIN opportunities o ON o.id=ap.opportunity_id WHERE ap.student_id=? ORDER BY ap.updated_at DESC""", (student_id,)).fetchall()]


def applications_for_industry(conn, account_id):
    return [dict(row) for row in conn.execute("""SELECT ap.*, s.name, s.username, s.headline, o.title, o.company,
        (SELECT COUNT(*) FROM student_skills ss WHERE ss.student_id=s.id) skill_count
        FROM applications ap JOIN opportunities o ON o.id=ap.opportunity_id JOIN students s ON s.id=ap.student_id
        WHERE o.posted_by_account_id=? ORDER BY ap.updated_at DESC""", (account_id,)).fetchall()]


def portfolio_for_student(conn, student_id): return [dict(row) for row in conn.execute("SELECT * FROM portfolio_items WHERE student_id=? ORDER BY created_at DESC", (student_id,)).fetchall()]

def dashboard_stats(conn, role, ident):
    if role == "student":
        return {"applications": conn.execute("SELECT COUNT(*) FROM applications WHERE student_id=?", (ident,)).fetchone()[0], "portfolio": conn.execute("SELECT COUNT(*) FROM portfolio_items WHERE student_id=?", (ident,)).fetchone()[0], "skills": conn.execute("SELECT COUNT(*) FROM student_skills WHERE student_id=?", (ident,)).fetchone()[0]}
    if role == "industry":
        return {"opportunities": conn.execute("SELECT COUNT(*) FROM opportunities WHERE posted_by_account_id=?", (ident,)).fetchone()[0], "applications": conn.execute("SELECT COUNT(*) FROM applications ap JOIN opportunities o ON o.id=ap.opportunity_id WHERE o.posted_by_account_id=?", (ident,)).fetchone()[0], "shortlisted": conn.execute("SELECT COUNT(*) FROM applications ap JOIN opportunities o ON o.id=ap.opportunity_id WHERE o.posted_by_account_id=? AND ap.status IN ('Shortlisted','Interview','Selected')", (ident,)).fetchone()[0]}
    return {"students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0], "opportunities": conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0], "industry_partners": conn.execute("SELECT COUNT(*) FROM accounts WHERE role='industry'").fetchone()[0]}

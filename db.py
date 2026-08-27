"""
db.py — SQLite data access layer for SkillBridge.

Why SQLite (and what to swap in for production)
-------------------------------------------------
For a hackathon build, SQLite is the right call: it's a single file
(`data/skillbridge.db`), needs zero setup/server, ships in Python's stdlib,
and is more than fast enough for a few hundred students/opportunities.

For a real deployment you'd swap this for a client-server database:
  * PostgreSQL — best general-purpose choice. Handles concurrent writes from
    many students/industry users at once (SQLite locks the whole file per
    write), has proper user roles for the "students / academicians /
    industry / institution" access levels the problem statement asks for,
    and JSON columns if you still want flexible skill metadata.
  * MySQL / MariaDB — similar profile to Postgres, fine alternative if your
    hosting stack already standardizes on it.
  * MongoDB — worth considering if opportunity postings become very
    unstructured (custom fields per company); less natural fit for the
    many-to-many skill matching this app does, which is relational by nature.

Because this module only talks to the database through plain SQL, migrating
means: standing up a Postgres instance, pointing DATABASE_URL at it, and
swapping sqlite3.connect() below for something like SQLAlchemy/psycopg2 —
the schema.sql structure (students / skills / opportunities / applications)
carries over almost unchanged.
"""

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


def init_db():
    """Create tables if they don't exist yet, then seed from mock_data.json
    the first time the app runs (so existing hackathon demo data isn't lost)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()

    already_seeded = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0] > 0
    if not already_seeded:
        _seed_from_legacy_json(conn)
    conn.close()


def _get_or_create_skill(conn, name, category="General"):
    name = name.strip().lower()
    row = conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO skills (name, category) VALUES (?, ?)", (name, category))
    return cur.lastrowid


def _seed_from_legacy_json(conn):
    """One-time migration: read the old flat-file mock_data.json (if present)
    and load it into the relational schema. Also tops up a few non-tech
    opportunities/skills so the matcher demonstrably works outside CS."""
    students, opportunities = [], []
    if LEGACY_MOCK_DATA_PATH.exists():
        with open(LEGACY_MOCK_DATA_PATH, "r") as f:
            legacy = json.load(f)
        students = legacy.get("students", [])
        if "student" in legacy and not students:
            students = [legacy["student"]]
        opportunities = legacy.get("opportunities", [])

    # Seed students (default password "changeme123" — demo only; they should
    # register their own account via /register instead of relying on this).
    for s in students:
        username = f"student{s.get('id')}"
        exists = conn.execute("SELECT id FROM students WHERE username = ?", (username,)).fetchone()
        if exists:
            continue
        cur = conn.execute(
            "INSERT INTO students (name, username, password_hash) VALUES (?, ?, ?)",
            (s.get("name", "Unnamed"), username, generate_password_hash("changeme123")),
        )
        student_id = cur.lastrowid
        for skill in s.get("skills", []):
            skill_id = _get_or_create_skill(conn, skill)
            conn.execute(
                "INSERT OR IGNORE INTO student_skills (student_id, skill_id) VALUES (?, ?)",
                (student_id, skill_id),
            )

    # Seed opportunities from legacy file
    for o in opportunities:
        cur = conn.execute(
            "INSERT INTO opportunities (title, company, type, description) VALUES (?, ?, ?, ?)",
            (o.get("title", "Untitled"), o.get("company", "N/A"), o.get("type", "Internship"), ""),
        )
        opp_id = cur.lastrowid
        for skill in o.get("required_skills", []):
            skill_id = _get_or_create_skill(conn, skill)
            conn.execute(
                "INSERT OR IGNORE INTO opportunity_skills (opportunity_id, skill_id, weight_type) VALUES (?, ?, 'required')",
                (opp_id, skill_id),
            )
        for skill in o.get("preferred_skills", []):
            skill_id = _get_or_create_skill(conn, skill)
            conn.execute(
                "INSERT OR IGNORE INTO opportunity_skills (opportunity_id, skill_id, weight_type) VALUES (?, ?, 'preferred')",
                (opp_id, skill_id),
            )

    # Extra seed opportunities spanning non-tech domains, so the platform
    # visibly supports "sciences or anything", not just software roles.
    extra_opportunities = [
        {
            "title": "Biology Research Assistant",
            "company": "GreenLeaf Labs",
            "type": "Research",
            "required": ["lab-safety", "microscopy", "data-recording"],
            "preferred": ["statistics", "report-writing"],
        },
        {
            "title": "Marketing & Content Intern",
            "company": "Northwind Media",
            "type": "Internship",
            "required": ["content-writing", "social-media"],
            "preferred": ["seo", "graphic-design"],
        },
        {
            "title": "Chemistry Lab Technician",
            "company": "Aravalli Chemworks",
            "type": "Internship",
            "required": ["lab-safety", "titration", "chemical-analysis"],
            "preferred": ["report-writing"],
        },
        {
            "title": "UI/UX Design Intern",
            "company": "PixelForge Studio",
            "type": "Internship",
            "required": ["graphic-design", "figma"],
            "preferred": ["html", "css"],
        },
        {
            "title": "Financial Analyst Trainee",
            "company": "Meridian Capital",
            "type": "Full-Time",
            "required": ["excel", "financial-modeling"],
            "preferred": ["statistics", "presentation-skills"],
        },
    ]
    for o in extra_opportunities:
        exists = conn.execute("SELECT id FROM opportunities WHERE title = ?", (o["title"],)).fetchone()
        if exists:
            continue
        cur = conn.execute(
            "INSERT INTO opportunities (title, company, type, description) VALUES (?, ?, ?, ?)",
            (o["title"], o["company"], o["type"], ""),
        )
        opp_id = cur.lastrowid
        for skill in o["required"]:
            skill_id = _get_or_create_skill(conn, skill)
            conn.execute(
                "INSERT OR IGNORE INTO opportunity_skills (opportunity_id, skill_id, weight_type) VALUES (?, ?, 'required')",
                (opp_id, skill_id),
            )
        for skill in o["preferred"]:
            skill_id = _get_or_create_skill(conn, skill)
            conn.execute(
                "INSERT OR IGNORE INTO opportunity_skills (opportunity_id, skill_id, weight_type) VALUES (?, ?, 'preferred')",
                (opp_id, skill_id),
            )

    conn.commit()


# ---------------------------------------------------------------------------
# Query helpers used by app.py
# ---------------------------------------------------------------------------

def get_student_by_username(conn, username):
    return conn.execute("SELECT * FROM students WHERE username = ?", (username,)).fetchone()


def get_student_by_id(conn, student_id):
    return conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()


def get_student_skills(conn, student_id):
    rows = conn.execute(
        """SELECT skills.name FROM skills
           JOIN student_skills ON student_skills.skill_id = skills.id
           WHERE student_skills.student_id = ?""",
        (student_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def set_student_skills(conn, student_id, skill_names):
    conn.execute("DELETE FROM student_skills WHERE student_id = ?", (student_id,))
    for skill in skill_names:
        skill = skill.strip()
        if not skill:
            continue
        skill_id = _get_or_create_skill(conn, skill)
        conn.execute(
            "INSERT OR IGNORE INTO student_skills (student_id, skill_id) VALUES (?, ?)",
            (student_id, skill_id),
        )
    conn.commit()


def get_all_opportunities_with_skills(conn):
    opportunities = conn.execute("SELECT * FROM opportunities").fetchall()
    result = []
    for opp in opportunities:
        required = conn.execute(
            """SELECT skills.name FROM skills
               JOIN opportunity_skills ON opportunity_skills.skill_id = skills.id
               WHERE opportunity_skills.opportunity_id = ? AND opportunity_skills.weight_type = 'required'""",
            (opp["id"],),
        ).fetchall()
        preferred = conn.execute(
            """SELECT skills.name FROM skills
               JOIN opportunity_skills ON opportunity_skills.skill_id = skills.id
               WHERE opportunity_skills.opportunity_id = ? AND opportunity_skills.weight_type = 'preferred'""",
            (opp["id"],),
        ).fetchall()
        result.append({
            "id": opp["id"],
            "title": opp["title"],
            "company": opp["company"],
            "type": opp["type"],
            "required_skills": [r["name"] for r in required],
            "preferred_skills": [r["name"] for r in preferred],
        })
    return result


def create_student(conn, name, username, password_hash):
    cur = conn.execute(
        "INSERT INTO students (name, username, password_hash) VALUES (?, ?, ?)",
        (name, username, password_hash),
    )
    conn.commit()
    return cur.lastrowid

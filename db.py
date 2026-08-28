"""
Supabase/PostgreSQL data access for the SkillBridge hackathon experience.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor


# =========================================================
# Environment
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# =========================================================
# PostgreSQL compatibility helpers
# =========================================================

class CompatRow(dict):
    """
    Dictionary-like database row that also supports row[0],
    just like the old sqlite3.Row used by the original app.
    """

    def __init__(self, data):
        super().__init__(data)
        self._values = list(data.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class CompatCursor:
    """
    Wrapper so the existing Flask app can continue using
    conn.execute(...) and SQLite-style ? placeholders.
    """

    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        query = self._convert_query(query)

        if params is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query, params)

        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        return CompatRow(row) if row is not None else None

    def fetchall(self):
        return [CompatRow(row) for row in self.cursor.fetchall()]

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @staticmethod
    def _convert_query(query):
        # SQLite ? placeholders -> PostgreSQL %s
        query = query.replace("?", "%s")

        # SQLite INSERT OR IGNORE -> PostgreSQL INSERT
        query = query.replace(
            "INSERT OR IGNORE INTO",
            "INSERT INTO"
        )

        return query


class CompatConnection:
    """
    Connection wrapper exposing the old conn.execute(...)
    interface while actually using PostgreSQL/Supabase.
    """

    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        cursor = self.connection.cursor(
            cursor_factory=RealDictCursor
        )

        wrapped = CompatCursor(cursor)
        wrapped.execute(query, params)

        return wrapped

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


# =========================================================
# Connection
# =========================================================

def get_connection():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL was not found in the .env file."
        )

    connection = psycopg2.connect(database_url)

    return CompatConnection(connection)


# =========================================================
# Database initialisation
# =========================================================

def init_db():
    """
    Initialise the Supabase database.

    Tables must already exist because they are created using
    supabase_schema.sql in Supabase SQL Editor.

    If opportunities is empty, insert the built-in opportunities.
    """

    conn = get_connection()

    try:
        result = conn.execute(
            "SELECT COUNT(*) AS count FROM opportunities"
        )

        count = result.fetchone()["count"]

        if count == 0:
            _seed_data(conn)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# =========================================================
# Skill helpers
# =========================================================

def _normalise_skill_name(name):
    """
    Use one consistent spelling for skills.
    """

    return "-".join(
        name.strip().lower().replace("_", " ").split()
    )


def _normalise_existing_skills(conn):
    """
    Normalise existing skill names.
    """

    rows = conn.execute(
        "SELECT id, name FROM skills"
    ).fetchall()

    for row in rows:

        clean = _normalise_skill_name(row["name"])

        if clean == row["name"]:
            continue

        canonical = conn.execute(
            "SELECT id FROM skills WHERE name = ?",
            (clean,)
        ).fetchone()

        if canonical:

            canonical_id = canonical["id"]
            old_id = row["id"]

            conn.execute(
                """
                INSERT INTO student_skills(
                    student_id,
                    skill_id
                )
                SELECT
                    student_id,
                    ?
                FROM student_skills
                WHERE skill_id = ?
                ON CONFLICT DO NOTHING
                """,
                (canonical_id, old_id)
            )

            conn.execute(
                """
                INSERT INTO opportunity_skills(
                    opportunity_id,
                    skill_id,
                    weight_type
                )
                SELECT
                    opportunity_id,
                    ?,
                    weight_type
                FROM opportunity_skills
                WHERE skill_id = ?
                ON CONFLICT DO NOTHING
                """,
                (canonical_id, old_id)
            )

            conn.execute(
                """
                INSERT INTO student_skill_levels(
                    student_id,
                    skill_id,
                    level,
                    score
                )
                SELECT
                    student_id,
                    ?,
                    level,
                    score
                FROM student_skill_levels
                WHERE skill_id = ?
                ON CONFLICT (student_id, skill_id)
                DO UPDATE SET
                    level = EXCLUDED.level,
                    score = EXCLUDED.score
                """,
                (canonical_id, old_id)
            )

            conn.execute(
                "DELETE FROM student_skills WHERE skill_id = ?",
                (old_id,)
            )

            conn.execute(
                "DELETE FROM opportunity_skills WHERE skill_id = ?",
                (old_id,)
            )

            conn.execute(
                "DELETE FROM student_skill_levels WHERE skill_id = ?",
                (old_id,)
            )

            conn.execute(
                "DELETE FROM skills WHERE id = ?",
                (old_id,)
            )

        else:

            conn.execute(
                "UPDATE skills SET name = ? WHERE id = ?",
                (clean, row["id"])
            )


def _skill(conn, name, category="General"):

    clean = _normalise_skill_name(name)

    row = conn.execute(
        "SELECT id FROM skills WHERE name = ?",
        (clean,)
    ).fetchone()

    if row:
        return row["id"]

    result = conn.execute(
        """
        INSERT INTO skills(
            name,
            category
        )
        VALUES (?, ?)
        ON CONFLICT (name)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (clean, category)
    )

    return result.fetchone()["id"]


# =========================================================
# Seed data
# =========================================================

def _seed_data(conn):

    opportunities = [

        {
            "title": "UI/UX Design Intern",
            "company": "PixelForge Studio",
            "type": "Internship",
            "description": (
                "Turn user research into accessible interfaces "
                "alongside a product design team."
            ),
            "location": "Bengaluru / Hybrid",
            "duration": "3 months",
            "required_skills": [
                "graphic-design",
                "figma"
            ],
            "preferred_skills": [
                "html",
                "css"
            ]
        },

        {
            "title": "Biology Research Assistant",
            "company": "GreenLeaf Labs",
            "type": "Research",
            "description": (
                "Support lab experiments, data capture, and "
                "evidence-led reporting on a live research project."
            ),
            "location": "Pune / On-site",
            "duration": "6 months",
            "required_skills": [
                "lab-safety",
                "microscopy",
                "data-recording"
            ],
            "preferred_skills": [
                "statistics",
                "report-writing"
            ]
        },

        {
            "title": "Marketing & Content Intern",
            "company": "Northwind Media",
            "type": "Internship",
            "description": (
                "Plan campaign content, interpret audience signals, "
                "and build a portfolio of published work."
            ),
            "location": "Remote",
            "duration": "3 months",
            "required_skills": [
                "content-writing",
                "social-media"
            ],
            "preferred_skills": [
                "seo",
                "graphic-design"
            ]
        },

        {
            "title": "Data Analytics Apprentice",
            "company": "InsightForge",
            "type": "Apprenticeship",
            "description": (
                "Learn to turn real operational data into dashboards "
                "and clear business decisions."
            ),
            "location": "Remote / Hybrid",
            "duration": "4 months",
            "required_skills": [
                "python",
                "sql",
                "data-analysis"
            ],
            "preferred_skills": [
                "statistics",
                "excel"
            ]
        }
    ]

    for item in opportunities:

        existing = conn.execute(
            """
            SELECT 1
            FROM opportunities
            WHERE title = ? AND company = ?
            """,
            (
                item["title"],
                item["company"]
            )
        ).fetchone()

        if existing:
            continue

        result = conn.execute(
            """
            INSERT INTO opportunities(
                title,
                company,
                type,
                description,
                location,
                duration
            )
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                item["title"],
                item["company"],
                item["type"],
                item["description"],
                item["location"],
                item["duration"]
            )
        )

        opp_id = result.fetchone()["id"]

        for name in item["required_skills"]:

            skill_id = _skill(conn, name)

            conn.execute(
                """
                INSERT INTO opportunity_skills(
                    opportunity_id,
                    skill_id,
                    weight_type
                )
                VALUES (?, ?, 'required')
                ON CONFLICT DO NOTHING
                """,
                (opp_id, skill_id)
            )

        for name in item["preferred_skills"]:

            skill_id = _skill(conn, name)

            conn.execute(
                """
                INSERT INTO opportunity_skills(
                    opportunity_id,
                    skill_id,
                    weight_type
                )
                VALUES (?, ?, 'preferred')
                ON CONFLICT DO NOTHING
                """,
                (opp_id, skill_id)
            )

    conn.commit()


# =========================================================
# Students / accounts
# =========================================================

def student_by_username(conn, username):

    return conn.execute(
        """
        SELECT *
        FROM students
        WHERE username = ?
        """,
        (username,)
    ).fetchone()


def student_by_id(conn, student_id):

    return conn.execute(
        """
        SELECT *
        FROM students
        WHERE id = ?
        """,
        (student_id,)
    ).fetchone()


def account_by_username(conn, username):

    return conn.execute(
        """
        SELECT *
        FROM accounts
        WHERE username = ?
        """,
        (username,)
    ).fetchone()


def account_by_id(conn, account_id):

    return conn.execute(
        """
        SELECT *
        FROM accounts
        WHERE id = ?
        """,
        (account_id,)
    ).fetchone()


def username_taken(conn, username):

    return bool(
        student_by_username(conn, username)
        or account_by_username(conn, username)
    )


def create_student(
    conn,
    name,
    username,
    password_hash
):

    result = conn.execute(
        """
        INSERT INTO students(
            name,
            username,
            password_hash
        )
        VALUES (?, ?, ?)
        RETURNING id
        """,
        (
            name,
            username,
            password_hash
        )
    )

    ident = result.fetchone()["id"]

    conn.commit()

    return ident


def create_account(
    conn,
    role,
    name,
    username,
    password_hash,
    organisation,
    email
):

    result = conn.execute(
        """
        INSERT INTO accounts(
            role,
            name,
            username,
            password_hash,
            organisation,
            email
        )
        VALUES (?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (
            role,
            name,
            username,
            password_hash,
            organisation,
            email
        )
    )

    ident = result.fetchone()["id"]

    conn.commit()

    return ident


# =========================================================
# Student skills
# =========================================================

def student_skills(
    conn,
    student_id,
    include_levels=False
):

    rows = conn.execute(
        """
        SELECT
            skills.name,
            COALESCE(
                student_skill_levels.level,
                'Beginner'
            ) AS level,
            COALESCE(
                student_skill_levels.score,
                0
            ) AS score

        FROM student_skills

        JOIN skills
            ON skills.id = student_skills.skill_id

        LEFT JOIN student_skill_levels
            ON student_skill_levels.student_id =
                student_skills.student_id
            AND student_skill_levels.skill_id =
                skills.id

        WHERE student_skills.student_id = ?

        ORDER BY skills.name
        """,
        (student_id,)
    ).fetchall()

    if include_levels:
        return [dict(row) for row in rows]

    return [row["name"] for row in rows]


def set_student_skills(
    conn,
    student_id,
    names,
    score=0,
    level="Beginner",
    results=None
):

    conn.execute(
        """
        DELETE FROM student_skills
        WHERE student_id = ?
        """,
        (student_id,)
    )

    conn.execute(
        """
        DELETE FROM student_skill_levels
        WHERE student_id = ?
        """,
        (student_id,)
    )

    for name in {
        s.strip().lower()
        for s in names
        if s and s.strip()
    }:

        skill_id = _skill(conn, name)

        result = (results or {}).get(
            name,
            {}
        )

        skill_level = result.get(
            "level",
            level
        )

        skill_score = result.get(
            "score",
            score
        )

        conn.execute(
            """
            INSERT INTO student_skills(
                student_id,
                skill_id
            )
            VALUES (?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                student_id,
                skill_id
            )
        )

        conn.execute(
            """
            INSERT INTO student_skill_levels(
                student_id,
                skill_id,
                level,
                score
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT (student_id, skill_id)
            DO UPDATE SET
                level = EXCLUDED.level,
                score = EXCLUDED.score
            """,
            (
                student_id,
                skill_id,
                skill_level,
                skill_score
            )
        )

    conn.commit()


# =========================================================
# Opportunities
# =========================================================

def opportunities_with_skills(
    conn,
    poster_id=None
):

    sql = """
        SELECT
            o.*,
            a.organisation AS poster_organisation

        FROM opportunities o

        LEFT JOIN accounts a
            ON a.id = o.posted_by_account_id
    """

    args = []

    if poster_id:

        sql += """
            WHERE o.posted_by_account_id = ?
        """

        args.append(poster_id)

    sql += """
        ORDER BY
            o.created_at DESC,
            o.id DESC
    """

    result = []

    for opp in conn.execute(
        sql,
        args
    ).fetchall():

        grouped = {
            "required": [],
            "preferred": []
        }

        rows = conn.execute(
            """
            SELECT
                skills.name,
                opportunity_skills.weight_type

            FROM opportunity_skills

            JOIN skills
                ON skills.id =
                    opportunity_skills.skill_id

            WHERE opportunity_id = ?
            """,
            (opp["id"],)
        ).fetchall()

        for row in rows:

            grouped[
                row["weight_type"]
            ].append(
                row["name"]
            )

        data = dict(opp)

        data.update(
            required_skills=grouped["required"],
            preferred_skills=grouped["preferred"]
        )

        result.append(data)

    return result


def create_opportunity(
    conn,
    account_id,
    company,
    data
):

    result = conn.execute(
        """
        INSERT INTO opportunities(
            title,
            company,
            type,
            description,
            location,
            duration,
            posted_by_account_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (
            data["title"],
            company,
            data["type"],
            data["description"],
            data["location"],
            data["duration"],
            account_id
        )
    )

    opp_id = result.fetchone()["id"]

    for weight, key in (
        ("required", "required_skills"),
        ("preferred", "preferred_skills")
    ):

        for name in data.get(key, []):

            skill_id = _skill(
                conn,
                name
            )

            conn.execute(
                """
                INSERT INTO opportunity_skills(
                    opportunity_id,
                    skill_id,
                    weight_type
                )
                VALUES (?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    opp_id,
                    skill_id,
                    weight
                )
            )

    conn.commit()

    return opp_id


# =========================================================
# Applications
# =========================================================

def applications_for_student(
    conn,
    student_id
):

    return [
        dict(row)

        for row in conn.execute(
            """
            SELECT
                ap.*,
                o.title,
                o.company,
                o.type,
                o.location

            FROM applications ap

            JOIN opportunities o
                ON o.id = ap.opportunity_id

            WHERE ap.student_id = ?

            ORDER BY
                ap.updated_at DESC
            """,
            (student_id,)
        ).fetchall()
    ]


def applications_for_industry(
    conn,
    account_id
):

    return [
        dict(row)

        for row in conn.execute(
            """
            SELECT
                ap.*,
                s.name,
                s.username,
                s.headline,
                o.title,
                o.company,

                (
                    SELECT COUNT(*)
                    FROM student_skills ss
                    WHERE ss.student_id = s.id
                ) AS skill_count

            FROM applications ap

            JOIN opportunities o
                ON o.id = ap.opportunity_id

            JOIN students s
                ON s.id = ap.student_id

            WHERE o.posted_by_account_id = ?

            ORDER BY
                ap.updated_at DESC
            """,
            (account_id,)
        ).fetchall()
    ]


# =========================================================
# Portfolio
# =========================================================

def portfolio_for_student(
    conn,
    student_id
):

    return [
        dict(row)

        for row in conn.execute(
            """
            SELECT *
            FROM portfolio_items
            WHERE student_id = ?
            ORDER BY created_at DESC
            """,
            (student_id,)
        ).fetchall()
    ]


# =========================================================
# Dashboard
# =========================================================

def dashboard_stats(
    conn,
    role,
    ident
):

    if role == "student":

        return {

            "applications": conn.execute(
                """
                SELECT COUNT(*)
                FROM applications
                WHERE student_id = ?
                """,
                (ident,)
            ).fetchone()[0],

            "portfolio": conn.execute(
                """
                SELECT COUNT(*)
                FROM portfolio_items
                WHERE student_id = ?
                """,
                (ident,)
            ).fetchone()[0],

            "skills": conn.execute(
                """
                SELECT COUNT(*)
                FROM student_skills
                WHERE student_id = ?
                """,
                (ident,)
            ).fetchone()[0]
        }

    if role == "industry":

        return {

            "opportunities": conn.execute(
                """
                SELECT COUNT(*)
                FROM opportunities
                WHERE posted_by_account_id = ?
                """,
                (ident,)
            ).fetchone()[0],

            "applications": conn.execute(
                """
                SELECT COUNT(*)
                FROM applications ap

                JOIN opportunities o
                    ON o.id = ap.opportunity_id

                WHERE o.posted_by_account_id = ?
                """,
                (ident,)
            ).fetchone()[0],

            "shortlisted": conn.execute(
                """
                SELECT COUNT(*)
                FROM applications ap

                JOIN opportunities o
                    ON o.id = ap.opportunity_id

                WHERE
                    o.posted_by_account_id = ?

                    AND ap.status IN (
                        'Shortlisted',
                        'Interview',
                        'Selected'
                    )
                """,
                (ident,)
            ).fetchone()[0]
        }

    return {

        "students": conn.execute(
            """
            SELECT COUNT(*)
            FROM students
            """
        ).fetchone()[0],

        "opportunities": conn.execute(
            """
            SELECT COUNT(*)
            FROM opportunities
            """
        ).fetchone()[0],

        "industry_partners": conn.execute(
            """
            SELECT COUNT(*)
            FROM accounts
            WHERE role = 'industry'
            """
        ).fetchone()[0]
    }
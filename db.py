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

        # Seeding is idempotent, so a new domain-relevant demo catalogue can
        # safely be added to an existing development database as well.
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
            "title": "Ayurvedic Pharma QA Intern",
            "company": "AryaVeda Pharmaceuticals",
            "type": "Internship",
            "description": (
                "Support GMP documentation, batch-record review, and quality "
                "checks for classical Ayurvedic formulations."
            ),
            "location": "Haridwar / On-site",
            "duration": "3 months",
            "required_skills": [
                "pharmacognosy",
                "quality-assurance"
            ],
            "preferred_skills": [
                "medical-documentation",
                "clinical-practice"
            ]
        },

        {
            "title": "Panchakarma Research Assistant",
            "company": "Swasthya Research Hospital",
            "type": "Research",
            "description": (
                "Document clinical outcomes and support evidence-led research "
                "on integrative Panchakarma care pathways."
            ),
            "location": "New Delhi / On-site",
            "duration": "6 months",
            "required_skills": [
                "panchakarma",
                "clinical-practice",
                "clinical-research"
            ],
            "preferred_skills": [
                "biostatistics",
                "medical-documentation"
            ]
        },

        {
            "title": "Yoga Therapy Programme Intern",
            "company": "Prana Integrative Care",
            "type": "Internship",
            "description": (
                "Assist yoga therapists with patient education, session records, "
                "and community wellness programme design."
            ),
            "location": "Bengaluru / Hybrid",
            "duration": "3 months",
            "required_skills": [
                "yoga-therapy",
                "patient-counselling"
            ],
            "preferred_skills": [
                "medical-documentation",
                "wellness-program-design"
            ]
        },

        {
            "title": "Ayush Hospital Operations Apprentice",
            "company": "Arogya Ayush Hospital",
            "type": "Apprenticeship",
            "description": (
                "Build service dashboards and improve patient flow within an "
                "Ayush hospital care-delivery team."
            ),
            "location": "Chennai / Hybrid",
            "duration": "4 months",
            "required_skills": [
                "hospital-administration",
                "medical-documentation",
                "biostatistics"
            ],
            "preferred_skills": [
                "patient-counselling",
                "quality-assurance"
            ]
        },
        {
            "title": "Sanskrit Texts & Clinical Knowledge Intern",
            "company": "Veda Knowledge Centre",
            "type": "Internship",
            "description": "Help map classical Sanskrit references to structured clinical learning resources for students and practitioners.",
            "location": "Remote / New Delhi",
            "duration": "3 months",
            "required_skills": ["sanskrit-texts", "clinical-practice"],
            "preferred_skills": ["medical-documentation", "research-ethics"]
        },
        {
            "title": "Herbal Pharmacognosy Lab Trainee",
            "company": "Bharat Botanicals Research Lab",
            "type": "Research",
            "description": "Support authenticated raw-material review and evidence capture for Ayurvedic herbal formulations.",
            "location": "Pune / On-site",
            "duration": "4 months",
            "required_skills": ["pharmacognosy", "quality-assurance"],
            "preferred_skills": ["clinical-research", "medical-documentation"]
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
    password_hash,
    email
):

    result = conn.execute(
        """
        INSERT INTO students(
            name,
            username,
            password_hash,
            email
        )
        VALUES (?, ?, ?, ?)
        RETURNING id
        """,
        (
            name,
            username,
            password_hash,
            email
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

    # Retire the original generic hackathon placeholders from all visible
    # workspaces. Existing user-created postings remain untouched.
    sql += """
        WHERE o.company NOT IN (
            'PixelForge Studio', 'GreenLeaf Labs', 'Northwind Media', 'InsightForge'
        )
    """

    if poster_id:

        sql += """
            AND o.posted_by_account_id = ?
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
    applications = [dict(row) for row in conn.execute(
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
    for application in applications:
        skills = set(student_skills(conn, application["student_id"]))
        requirements = conn.execute(
            """
            SELECT s.name, os.weight_type
            FROM opportunity_skills os
            JOIN skills s ON s.id = os.skill_id
            WHERE os.opportunity_id = ?
            """, (application["opportunity_id"],)
        ).fetchall()
        required = {row["name"] for row in requirements if row["weight_type"] == "required"}
        preferred = {row["name"] for row in requirements if row["weight_type"] == "preferred"}
        matched_required = sorted(skills & required)
        matched_preferred = sorted(skills & preferred)
        required_weight = 70 if preferred else 100
        score = (len(matched_required) / len(required) * required_weight) if required else required_weight
        if preferred:
            score += len(matched_preferred) / len(preferred) * 30
        application["compatibility"] = round(min(score, 100))
        application["matched_skills"] = matched_required + matched_preferred
        application["missing_skills"] = sorted(required - skills)
    return sorted(applications, key=lambda item: (-item["compatibility"], item["name"].lower()))


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

# =========================================================
# Email verification (OTP)
# =========================================================

def set_verification_code(conn, account_id, code, expires_at):

    conn.execute(
        """
        UPDATE accounts
        SET verification_code = ?,
            verification_expires = ?
        WHERE id = ?
        """,
        (code, expires_at, account_id)
    )

    conn.commit()


def get_verification(conn, account_id):

    return conn.execute(
        """
        SELECT verification_code, verification_expires
        FROM accounts
        WHERE id = ?
        """,
        (account_id,)
    ).fetchone()


def clear_verification_code(conn, account_id):

    conn.execute(
        """
        UPDATE accounts
        SET verified = TRUE,
            verification_code = NULL,
            verification_expires = NULL
        WHERE id = ?
        """,
        (account_id,)
    )

    conn.commit()


# =========================================================
# Opportunities: delete
# =========================================================

def delete_opportunity(conn, opportunity_id, account_id):
    """
    Deletes an opportunity only if it belongs to the requesting
    industry account. Returns the number of rows deleted (0 or 1).
    opportunity_skills and applications cascade-delete via the
    foreign keys defined in supabase_schema.sql.
    """

    result = conn.execute(
        """
        DELETE FROM opportunities
        WHERE id = ?
          AND posted_by_account_id = ?
        """,
        (opportunity_id, account_id)
    )

    conn.commit()

    return result.rowcount


# =========================================================
# Academician: student directory & industry partners
# =========================================================

def all_students_summary(conn):
    """
    Every student profile visible to academicians, including
    their verified skill levels (reuses student_skills()).
    """

    rows = conn.execute(
        """
        SELECT id, name, username, headline
        FROM students
        ORDER BY name
        """
    ).fetchall()

    students = []

    for row in rows:
        data = dict(row)
        data["skills"] = student_skills(conn, row["id"], include_levels=True)
        students.append(data)

    return students


def industry_partners(conn):

    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT id, name, organisation
            FROM accounts
            WHERE role = 'industry'
            ORDER BY organisation
            """
        ).fetchall()
    ]


# =========================================================
# Collaboration requests (academician <-> industry)
# =========================================================

def create_collaboration_request(conn, academician_id, industry_account_id, opportunity_id, message):

    result = conn.execute(
        """
        INSERT INTO collaboration_requests(
            academician_id,
            industry_account_id,
            opportunity_id,
            message
        )
        VALUES (?, ?, ?, ?)
        RETURNING id
        """,
        (academician_id, industry_account_id, opportunity_id, message)
    )

    ident = result.fetchone()["id"]

    conn.commit()

    return ident


def collaboration_requests_for_academician(conn, academician_id):

    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                cr.*,
                a.organisation AS industry_organisation,
                a.name AS industry_name

            FROM collaboration_requests cr

            JOIN accounts a
                ON a.id = cr.industry_account_id

            WHERE cr.academician_id = ?

            ORDER BY cr.created_at DESC
            """,
            (academician_id,)
        ).fetchall()
    ]


def collaboration_requests_for_industry(conn, industry_account_id):

    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                cr.*,
                a.name AS academician_name,
                a.organisation AS academician_organisation

            FROM collaboration_requests cr

            JOIN accounts a
                ON a.id = cr.academician_id

            WHERE cr.industry_account_id = ?

            ORDER BY cr.created_at DESC
            """,
            (industry_account_id,)
        ).fetchall()
    ]


def update_collaboration_request_status(conn, request_id, industry_account_id, status):
    """
    Only the industry account the request was sent to can accept/decline it.
    Returns the number of rows updated (0 or 1).
    """

    result = conn.execute(
        """
        UPDATE collaboration_requests
        SET status = ?
        WHERE id = ?
          AND industry_account_id = ?
        """,
        (status, request_id, industry_account_id)
    )

    conn.commit()

    return result.rowcount


# =========================================================
# Industry learning programmes & student registrations
# =========================================================

def learning_programs(conn):
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT lp.*, COALESCE(a.organisation, a.name, lp.publisher_name) AS provider
            FROM learning_programs lp
            LEFT JOIN accounts a ON a.id = lp.publisher_account_id
            ORDER BY lp.created_at DESC, lp.id DESC
            """
        ).fetchall()]


def create_learning_program(conn, account_id, data):
    result = conn.execute(
        """
        INSERT INTO learning_programs(
            publisher_account_id, publisher_name, title, format, mode, duration, skills, audience, description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (
            account_id, data["publisher_name"], data["title"], data["format"], data.get("mode", "Online"),
            data["duration"], data["skills"], data.get("audience", "Students"), data["description"]
        )
    )


def email_taken(conn, email):
    return bool(conn.execute(
        """
        SELECT 1 FROM students WHERE lower(email) = lower(?)
        UNION ALL
        SELECT 1 FROM accounts WHERE lower(email) = lower(?)
        LIMIT 1
        """, (email, email)
    ).fetchone())
    ident = result.fetchone()["id"]
    conn.commit()
    return ident


def register_for_learning_program(conn, student_id, program_id):
    program = conn.execute(
        """
        SELECT lp.*, COALESCE(a.organisation, a.name, lp.publisher_name) AS provider
        FROM learning_programs lp
        LEFT JOIN accounts a ON a.id = lp.publisher_account_id
        WHERE lp.id = ?
        """,
        (program_id,)
    ).fetchone()
    student = conn.execute("SELECT name, email FROM students WHERE id = ?", (student_id,)).fetchone()
    if not program or not student:
        return None, False
    if not student["email"]:
        return {"program": dict(program), "student": dict(student)}, None
    created = conn.execute(
        """
        INSERT INTO programme_registrations(student_id, learning_program_id)
        VALUES (?, ?)
        ON CONFLICT (student_id, learning_program_id) DO NOTHING
        RETURNING id
        """,
        (student_id, program_id)
    ).fetchone()
    conn.commit()
    return {"program": dict(program), "student": dict(student)}, bool(created)


def registered_learning_program_ids(conn, student_id):
    return {
        row["learning_program_id"]
        for row in conn.execute(
            "SELECT learning_program_id FROM programme_registrations WHERE student_id = ?",
            (student_id,)
        ).fetchall()
    }


def programme_registrations_for_publisher(conn, publisher_id):
    rows = conn.execute(
        """
        SELECT pr.registered_at, lp.id AS program_id, lp.title AS program_title,
               s.id AS student_id, s.name, s.email, s.headline
        FROM programme_registrations pr
        JOIN learning_programs lp ON lp.id = pr.learning_program_id
        JOIN students s ON s.id = pr.student_id
        WHERE lp.publisher_account_id = ?
        """, (publisher_id,)
    ).fetchall()
    registrations = []
    for row in rows:
        registrations.append({
            "program_id": row["program_id"], "program_title": row["program_title"],
            "name": row["name"], "email": row["email"], "headline": row["headline"],
            "registered_at": row["registered_at"],
        })
    return sorted(registrations, key=lambda item: (item["program_title"].lower(), str(item["registered_at"])), reverse=True)


def registered_learning_programs_for_student(conn, student_id):
    return [dict(row) for row in conn.execute(
        """
        SELECT lp.*, COALESCE(a.organisation, a.name, lp.publisher_name) AS provider,
               pr.status, pr.registered_at
        FROM programme_registrations pr
        JOIN learning_programs lp ON lp.id = pr.learning_program_id
        LEFT JOIN accounts a ON a.id = lp.publisher_account_id
        WHERE pr.student_id = ?
        ORDER BY pr.registered_at DESC
        """, (student_id,)).fetchall()]


# =========================================================
# Publisher announcements
# =========================================================

def create_announcement(conn, publisher_id, target_type, target_id, subject, message):
    if target_type == "opportunity":
        target = conn.execute(
            "SELECT id, title FROM opportunities WHERE id = ? AND posted_by_account_id = ?",
            (target_id, publisher_id)
        ).fetchone()
        recipient_query = "SELECT student_id FROM applications WHERE opportunity_id = ?"
        column = "opportunity_id"
    else:
        target = conn.execute(
            "SELECT id, title FROM learning_programs WHERE id = ? AND publisher_account_id = ?",
            (target_id, publisher_id)
        ).fetchone()
        recipient_query = "SELECT student_id FROM programme_registrations WHERE learning_program_id = ?"
        column = "learning_program_id"
    if not target:
        return None, 0
    recipient_ids = [row["student_id"] for row in conn.execute(recipient_query, (target_id,)).fetchall()]
    if not recipient_ids:
        return {"target": dict(target)}, 0
    announcement_id = conn.execute(
        f"""
        INSERT INTO announcements(publisher_account_id, {column}, subject, message)
        VALUES (?, ?, ?, ?)
        RETURNING id
        """,
        (publisher_id, target_id, subject, message)
    ).fetchone()["id"]
    for student_id in recipient_ids:
        conn.execute(
            "INSERT INTO announcement_recipients(announcement_id, student_id) VALUES (?, ?)",
            (announcement_id, student_id)
        )
    conn.commit()
    return {"target": dict(target), "announcement_id": announcement_id}, len(recipient_ids)


def announcements_for_student(conn, student_id):
    return [dict(row) for row in conn.execute(
        """
        SELECT an.*, COALESCE(a.organisation, a.name) AS publisher,
               COALESCE(o.title, lp.title) AS target_title
        FROM announcement_recipients ar
        JOIN announcements an ON an.id = ar.announcement_id
        LEFT JOIN accounts a ON a.id = an.publisher_account_id
        LEFT JOIN opportunities o ON o.id = an.opportunity_id
        LEFT JOIN learning_programs lp ON lp.id = an.learning_program_id
        WHERE ar.student_id = ?
        ORDER BY an.created_at DESC
        """, (student_id,)).fetchall()]


def announcements_for_academician(conn):
    return [dict(row) for row in conn.execute(
        """
        SELECT an.*, COALESCE(a.organisation, a.name) AS publisher,
               COALESCE(o.title, lp.title) AS target_title
        FROM announcements an
        LEFT JOIN accounts a ON a.id = an.publisher_account_id
        LEFT JOIN opportunities o ON o.id = an.opportunity_id
        LEFT JOIN learning_programs lp ON lp.id = an.learning_program_id
        ORDER BY an.created_at DESC
        LIMIT 30
        """).fetchall()]

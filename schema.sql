-- SkillBridge database schema (SQLite)
-- Run automatically by app.py on first launch (see init_db() in db.py).
--
-- Design notes:
--   * Skills are domain-agnostic on purpose -- "python", "organic-chemistry",
--     "public-speaking" and "adobe-illustrator" are all just rows in `skills`.
--     Nothing in the schema or matching logic assumes "tech skills".
--   * `student_skills` / `opportunity_skills` are many-to-many join tables so
--     a skill can be reused across many students/opportunities without
--     duplicating strings everywhere (the old mock_data.json approach).
--   * Passwords are stored as salted hashes (werkzeug.security), never plain text.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skills (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,      -- stored lowercase, e.g. "microscopy"
    category TEXT DEFAULT 'General'     -- e.g. Programming, Science, Design, Business, Other
);

CREATE TABLE IF NOT EXISTS student_skills (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    skill_id   INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (student_id, skill_id)
);

CREATE TABLE IF NOT EXISTS opportunities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    company     TEXT DEFAULT 'N/A',
    type        TEXT DEFAULT 'Internship',   -- Internship / Full-Time / Research / Training
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS opportunity_skills (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    skill_id       INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    weight_type    TEXT NOT NULL CHECK (weight_type IN ('required', 'preferred')),
    PRIMARY KEY (opportunity_id, skill_id, weight_type)
);

CREATE TABLE IF NOT EXISTS applications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    applied_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (student_id, opportunity_id)
);

CREATE INDEX IF NOT EXISTS idx_student_skills_student ON student_skills(student_id);
CREATE INDEX IF NOT EXISTS idx_opportunity_skills_opp ON opportunity_skills(opportunity_id);

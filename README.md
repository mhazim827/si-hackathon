# SkillBridge

Academia–industry collaboration platform: students assess their skills,
get ranked internship/opportunity recommendations, and apply — all backed
by a real database and login system instead of a static JSON file.

## What changed from the original build

1. **Login system.** `/register` and `/login` create/authenticate a
   student account (`werkzeug` password hashing, Flask session cookies).
   Every page and API route that touches personal data (`/`, `/assessment`,
   `/api/opportunities`, `/api/assess`, `/api/apply`) requires a logged-in
   session and always operates on *that* student — no more manually typing
   in a student ID.
2. **Database instead of `mock_data.json`.** Data now lives in
   `data/skillbridge.db`, a SQLite database created from `schema.sql` the
   first time the app runs. See "Why SQLite / where a real DB fits" below.
3. **Domain-agnostic skill matching.** `matcher.py`'s scoring logic never
   changed — it was always just set intersection over strings — but it's
   now exercised across multiple domains on purpose. Seed data includes
   opportunities in biology, chemistry, marketing, design, and finance, not
   just software roles, to demonstrate matching for "sciences or anything."
4. **Dynamic, multi-domain skill assessment.** The old assessment hard-coded
   three programming questions as single-choice radio buttons. It's now
   generated at runtime from `/api/skills-catalog`, uses checkboxes
   (multi-select — a student can have several skills per category), spans
   five categories (Programming, Data & Analytics, Science & Lab Skills,
   Design & Creative, Business & Communication), and has a free-text field
   for anything not listed, so no field is locked out.
5. **Dynamic pages.** The dashboard shows the logged-in student's name and
   pulls live, ranked recommendations from the database on every load;
   "Apply Now" actually records an application (`applications` table)
   instead of just showing an alert.

## Project structure

```
si-hackathon/
├── app.py                 # Flask routes: pages, auth API, opportunities/assess/apply API
├── db.py                  # SQLite connection, schema init, seed migration, query helpers
├── matcher.py              # Skill-matching/scoring engine (unchanged logic)
├── schema.sql              # Table definitions
├── requirements.txt
├── data/
│   ├── mock_data.json      # Legacy fixture — used once to seed the DB on first run
│   └── skillbridge.db      # Created automatically, not committed (see .gitignore)
├── static/
│   ├── css/style.css
│   └── js/{login,assessment,integration}.js
└── templates/
    ├── login.html / register.html
    ├── index.html
    └── assessment.html
```

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`. First visit redirects to `/login`;
click through to `/register` to create an account, or log in as one of the
three students migrated from the old `mock_data.json`
(`student1` / `student2` / `student374`, password `changeme123` for all —
demo credentials only, meant to be replaced by real registrations).

## Why SQLite, and where a real database fits

SQLite was chosen here because it needs no server, ships with Python, and
is plenty fast for a hackathon demo's data volume — the whole database is
one file (`data/skillbridge.db`).

For an actual deployment (matching the "secure, scalable" platform the
problem statement asks for), the natural next step is a client-server
relational database:

- **PostgreSQL** is the strongest general fit. It supports many
  simultaneous writers (SQLite locks the whole file per write, which won't
  scale once students, academicians, and industry users are all writing at
  once), has real user roles/permissions to back the role-based access
  (student / academician / industry / institution) described in the
  problem statement, and has JSON columns if opportunity postings need
  flexible extra fields per company.
- **MySQL/MariaDB** is a reasonable alternative with a similar profile,
  if your hosting stack already standardizes on it.
- **MongoDB** is worth considering only if opportunity postings become
  highly unstructured (arbitrary custom fields per company) — the core
  student/skill/opportunity matching here is inherently relational
  (many-to-many joins), which Postgres/MySQL model more naturally than a
  document store.

Because `db.py` is the only place that talks SQL, migrating means: standing
up the new database, translating `schema.sql` (nearly 1:1 — SQLite's types
map directly onto Postgres/MySQL types), and swapping `sqlite3.connect()`
for a driver like `psycopg2`/SQLAlchemy. `app.py` and `matcher.py` don't
need to change at all.

## Still worth adding (out of scope for this pass)

- Role-based accounts for academicians and industry users (currently only
  students can log in); industry-side posting of new opportunities through
  the UI instead of seed data.
- Password reset / email verification.
- Digital portfolio (certifications, projects) and analytics dashboards
  mentioned in the problem statement.

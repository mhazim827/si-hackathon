# SkillBridge

SkillBridge is an Ayush-focused academia–industry collaboration platform built for the SI Hackathon. It connects students, industry partners, and academic institutions through verified skills, opportunity matching, learning programmes, recruitment workflows, and collaboration requests.

## What it does

- **Students** assess Ayush and health-science skills, receive ranked opportunities, apply, register for learning programmes, build a digital portfolio, and receive targeted announcements.
- **Industry partners** publish opportunities and learning programmes, review applicants ranked by skill compatibility, update candidate stages, send announcements, and manage collaboration requests.
- **Academicians** view institution signals, faculty-facing opportunities, industry partners, and collaboration pathways.

The demo data uses domain-relevant areas such as Panchakarma, pharmacognosy, clinical research, quality assurance, yoga therapy, hospital administration, and biostatistics.

## Technology

- Python + Flask
- SQLite (a local file database)
- Vanilla HTML, CSS, and JavaScript

## Quick start

### 1. Clone and create an environment

```bash
git clone <your-repository-url>
cd si-hackathon
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Optional environment variables

Copy `.env.example` to `.env` if you want a custom session secret or real email delivery.

```env
SKILLBRIDGE_SECRET_KEY=replace-with-a-random-secret
SMTP_EMAIL=your-sending-address@example.com
SMTP_PASSWORD=your-app-password
```

`SMTP_EMAIL` and `SMTP_PASSWORD` are optional for local UI testing. Without them, outgoing messages are printed in the server console instead of sent.

### 4. Start the app

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

On its first launch, SkillBridge automatically creates `data/skillbridge.db` with the database tables and Ayush-themed demo opportunities and learning programmes. No Supabase project, SQL editor, or database configuration is required.

## Main workflows

| Role | Key workflows |
| --- | --- |
| Student | Skill assessment, opportunity browse/filter, compatibility explanation, apply once, portfolio evidence, programme registration, personalised announcements |
| Industry | Post opportunities/programmes, rank opportunity applicants, manage statuses, email candidates, review programme registrants, publish announcements, accept/reject collaborations |
| Academician | View student/industry signals, browse faculty development opportunities, request collaboration, track request status |

## Matching logic

Opportunity matching compares a student’s verified skills with required and preferred skills:

- Required skills contribute **70%** of the result when preferred skills exist; otherwise they contribute **100%**.
- Preferred skills contribute the remaining **30%**.
- Every opportunity card explains the match and highlights a suggested learning path for missing core skills.

Industry applicant lists are ranked from highest to lowest compatibility. Learning-programme registrants are intentionally shown as a plain registration list, not ranked.

## Email notifications

When SMTP is configured, SkillBridge emails students when they:

- register for a learning programme;
- are moved to Under Review, Shortlisted, Interview, Selected, or Not Selected;
- receive a publisher announcement; and
- have a collaboration request accepted (academician account).

The sending address and password must remain in `.env`; never commit them.

## Repository layout

```text
app.py                                  Flask routes and email workflows
db.py                                   SQLite schema, seed data, and queries
matcher.py                              Skill-compatibility engine
templates/                              Flask templates
static/css/                             Dashboard styling
static/js/                              Role-specific dashboard interactions
data/skillbridge.db                     Created locally at first run (not committed)
docs/DEPLOYMENT.md                      Local database and email notes
```

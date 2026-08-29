import os
import re
import random
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from functools import wraps
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import db as db_sqlite_backup
from matcher import get_recommendations

app = Flask(__name__)
app.secret_key = os.environ.get("SKILLBRIDGE_SECRET_KEY", "dev-secret-key-change-me")
db_sqlite_backup.init_db()

SKILL_CATALOG = {
    "Ayurveda & Health Sciences": ["clinical-practice", "panchakarma", "pharmacognosy", "sanskrit-texts", "dravyaguna", "roga-nidana"],
    "Research, Evidence & Care Delivery": ["biostatistics", "clinical-research", "medical-documentation", "hospital-administration", "research-ethics", "quality-assurance"],
    "Yoga & Integrative Care": ["yoga-therapy", "patient-counselling", "wellness-program-design"],
    "Programming & Development": ["python", "java", "cpp", "javascript", "html", "css", "flask", "react", "sql"],
    "Data & Analytics": ["data-analysis", "statistics", "excel", "financial-modeling", "mongodb"],
    "Science & Lab Skills": ["lab-safety", "microscopy", "titration", "chemical-analysis", "data-recording", "report-writing"],
    "Design & Creative": ["graphic-design", "figma", "video-editing", "photography"],
    "Business & Communication": ["content-writing", "social-media", "seo", "presentation-skills", "public-speaking", "project-management"],
}

# The demo data is intentionally labelled and domain-specific. It keeps every
# workspace populated even before a team connects its Supabase instance or
# creates live accounts.
LEARNING_PROGRAMS = [
    {"id": 1, "title": "GMP & Ayurvedic Pharma Quality Essentials", "provider": "AryaVeda Pharmaceuticals", "format": "Certification", "mode": "Hybrid · New Delhi", "duration": "4 weeks", "skills": ["quality-assurance", "pharmacognosy", "medical-documentation"], "audience": "Students & recent graduates"},
    {"id": 2, "title": "Evidence-Based Panchakarma Practice", "provider": "Swasthya Research Hospital", "format": "Workshop", "mode": "On-site · Delhi", "duration": "2 days", "skills": ["panchakarma", "clinical-practice", "research-ethics"], "audience": "Students & faculty"},
    {"id": 3, "title": "Yoga Therapy Case Documentation", "provider": "Prana Integrative Care", "format": "Mentorship", "mode": "Online", "duration": "6 weeks", "skills": ["yoga-therapy", "medical-documentation", "patient-counselling"], "audience": "Students"},
]

FACULTY_PROGRAMS = [
    {"title": "Faculty Development Programme: Integrative Clinical Research", "company": "National Ayurveda Research Network", "type": "Faculty Development", "location": "New Delhi / Hybrid", "duration": "5 days", "description": "Faculty immersion in trial design, ethics and outcome measurement for Ayurveda research.", "required_skills": ["clinical-research", "biostatistics"], "preferred_skills": ["research-ethics", "sanskrit-texts"]},
    {"title": "Ayurvedic Formulation Innovation – Faculty Internship", "company": "AryaVeda Pharmaceuticals", "type": "Faculty Internship", "location": "Haridwar / On-site", "duration": "4 weeks", "description": "Work with formulation and QA teams to bring current practice into the classroom.", "required_skills": ["pharmacognosy", "quality-assurance"], "preferred_skills": ["hospital-administration"]},
    {"title": "Clinical Outcomes Research Collaboration", "company": "Swasthya Research Hospital", "type": "Research Collaboration", "location": "New Delhi / Hybrid", "duration": "6 months", "description": "Co-develop an outcomes study around Panchakarma care pathways.", "required_skills": ["clinical-research", "panchakarma"], "preferred_skills": ["biostatistics", "research-ethics"]},
]

DEMO_PIPELINE = [
    {"id": "demo-1", "name": "Ananya Sharma", "headline": "BAMS student · Pharmacognosy & QA", "title": "Ayurvedic Pharma QA Intern", "company": "AryaVeda Pharmaceuticals", "skill_count": 5, "compatibility": 92, "matched_skills": ["pharmacognosy", "quality-assurance", "medical-documentation"], "missing_skills": ["GMP auditing"], "status": "Shortlisted"},
    {"id": "demo-2", "name": "Rohan Iyer", "headline": "Panchakarma clinical trainee", "title": "Panchakarma Research Assistant", "company": "Swasthya Research Hospital", "skill_count": 4, "compatibility": 84, "matched_skills": ["panchakarma", "clinical-practice"], "missing_skills": ["biostatistics"], "status": "Under Review"},
    {"id": "demo-3", "name": "Meera Nair", "headline": "Yoga therapy & patient counselling", "title": "Yoga Therapy Programme Intern", "company": "Prana Integrative Care", "skill_count": 4, "compatibility": 76, "matched_skills": ["yoga-therapy", "patient-counselling"], "missing_skills": ["medical-documentation"], "status": "Submitted"},
]

def readiness_breakdown(skills, portfolio_count, applications):
    verified = min(len(skills) * 10, 50)
    evidence = min(portfolio_count * 10, 25)
    exposure = min(applications * 5, 15)
    return {"score": min(100, 10 + verified + evidence + exposure), "breakdown": [
        {"label": "Verified skills", "value": verified, "max": 50},
        {"label": "Portfolio evidence", "value": evidence, "max": 25},
        {"label": "Industry exposure", "value": exposure, "max": 15},
        {"label": "Profile foundation", "value": 10, "max": 10},
    ]}
QUESTION_BANK = {
    "python": {
        "beginner": {"question": "What does this expression produce: [x * 2 for x in range(3)]?", "options": ["[0, 1, 2]", "[0, 2, 4]", "[2, 4, 6]", "An error"], "answer": 1},
        "intermediate": {"question": "You need to process a very large text file without loading it all into memory. Which Python approach is most appropriate?", "options": ["file.read() followed by splitlines()", "Loop directly over the file object, one line at a time", "Convert the file to a list first", "Open the file once for every line"], "answer": 1},
        "expert": {"question": "For a membership test repeated many times against 100,000 unique identifiers, which structure normally gives the best average lookup performance?", "options": ["A list", "A tuple", "A set", "A string"], "answer": 2},
    },
    "sql": {
        "beginner": {"question": "Which clause filters rows before results are returned from a SELECT query?", "options": ["ORDER BY", "WHERE", "GROUP BY", "JOIN"], "answer": 1},
        "intermediate": {"question": "You need the number of applications per company, including only companies with more than five applications. Which clause filters the grouped result?", "options": ["WHERE", "HAVING", "LIMIT", "DISTINCT"], "answer": 1},
        "expert": {"question": "A frequently filtered column has high selectivity and queries are slow on a very large table. What is usually the best first optimisation to evaluate?", "options": ["Duplicate the whole table", "Add an appropriate index and inspect the query plan", "Remove all WHERE clauses", "Store every value in one text field"], "answer": 1},
    },
    "javascript": {
        "beginner": {"question": "Which keyword creates a block-scoped variable that cannot be reassigned?", "options": ["var", "let", "const", "static"], "answer": 2},
        "intermediate": {"question": "A page must wait for a network response before rendering a result. Which pattern makes the asynchronous flow clearest?", "options": ["A synchronous while loop", "async / await with error handling", "A blocking alert", "Reloading the page repeatedly"], "answer": 1},
        "expert": {"question": "A component state object has nested data. What is the safest general approach when updating it?", "options": ["Mutate the nested object in place", "Create an updated immutable copy", "Delete all state first", "Store state only in the DOM"], "answer": 1},
    },
    "data-analysis": {
        "beginner": {"question": "Before drawing conclusions from a dataset, what should you check first?", "options": ["Whether the chart colours look good", "Missing values, duplicates, and data types", "Only the final average", "The newest row only"], "answer": 1},
        "intermediate": {"question": "A dashboard shows a sudden 300% jump. What is the strongest next step?", "options": ["Publish immediately", "Validate the source, definitions, and outliers before explaining it", "Delete the chart", "Assume the trend will continue"], "answer": 1},
        "expert": {"question": "A correlation appears strong between two variables. What prevents an unsupported conclusion?", "options": ["Treat it as proof of causation", "Check confounders, study design, and uncertainty", "Ignore sample size", "Only show one variable"], "answer": 1},
    },
}

GENERIC_QUESTION_BANK = {
    "beginner": {"question": "When starting a task in this skill, what is the most reliable way to build a foundation?", "options": ["Copy an answer without understanding it", "Practice core concepts with small, explainable tasks", "Skip directly to the hardest project", "Avoid feedback"], "answer": 1},
    "intermediate": {"question": "You can complete routine tasks in this skill. What best demonstrates intermediate capability?", "options": ["Applying the skill independently to a new but familiar problem", "Only repeating one memorised example", "Avoiding constraints", "Never documenting your choices"], "answer": 0},
    "expert": {"question": "A complex task in this skill has unclear requirements. What most demonstrates expert judgement?", "options": ["Make assumptions silently", "Break down uncertainty, test options, and justify trade-offs", "Use the first solution without review", "Focus only on speed"], "answer": 1},
}


def valid_username(value): return bool(re.fullmatch(r"[a-zA-Z0-9_]{3,30}", value or ""))
def user_role(): return session.get("role")
def user_id(): return session.get("user_id")

def to_int_or_none(value):
    try: return int(value)
    except (TypeError, ValueError): return None

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not user_role():
            if request.path.startswith("/api/"): return jsonify(status="error", message="Please log in."), 401
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)
    return wrapped

def role_required(*roles):
    def wrap(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if user_role() not in roles: return jsonify(status="error", message="This action is not available for your account type."), 403
            return view(*args, **kwargs)
        return wrapped
    return wrap

def set_session(role, ident, name):
    session.clear(); session.update(role=role, user_id=ident, user_name=name)
    if role == "student": session["student_id"] = ident


@app.route("/")
@login_required
def home():
    conn = db_sqlite_backup.get_connection(); role, ident = user_role(), user_id()
    stats = db_sqlite_backup.dashboard_stats(conn, role, ident)
    user = db_sqlite_backup.student_by_id(conn, ident) if role == "student" else db_sqlite_backup.account_by_id(conn, ident)
    if not user:
        # The database may have been reseeded or a demo account removed while
        # the browser still holds its old session. Treat it as logged out
        # instead of rendering a page with a missing user object.
        conn.close()
        session.clear()
        return redirect(url_for("login_page"))
    conn.close()
    return render_template("index.html", role=role, user=user, stats=stats)

@app.route("/assessment")
@login_required
def assessment():
    if user_role() != "student": return redirect(url_for("home"))
    return render_template("assessment.html", skill_catalog=SKILL_CATALOG)

@app.route("/profile")
@login_required
def profile(): return render_template("profile.html", role=user_role(), user_name=session.get("user_name", ""))

@app.route("/login")
def login_page(): return redirect(url_for("home")) if user_role() else render_template("login.html")

@app.route("/register")
def register_page(): return redirect(url_for("home")) if user_role() else render_template("register.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login_page"))


@app.route("/api/register", methods=["POST"])
def register_api():
    payload = request.get_json(silent=True) or {}
    name, username, password, email = (payload.get("name") or "").strip(), (payload.get("username") or "").strip().lower(), payload.get("password") or "", (payload.get("email") or "").strip().lower()
    role = payload.get("role", "student")
    if role not in ("student", "industry", "academician"): return jsonify(status="error", message="Choose a valid account type."), 400
    if not name or not username or not password: return jsonify(status="error", message="Name, username and password are required."), 400
    if not valid_username(username): return jsonify(status="error", message="Use 3–30 letters, numbers, or underscores for your username."), 400
    if len(password) < 6: return jsonify(status="error", message="Use a password with at least 6 characters."), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): return jsonify(status="error", message="Enter a valid email address so we can send programme registrations."), 400
    conn = db_sqlite_backup.get_connection()
    if db_sqlite_backup.username_taken(conn, username): conn.close(); return jsonify(status="error", message="That username is already in use."), 409
    if db_sqlite_backup.email_taken(conn, email): conn.close(); return jsonify(status="error", message="An account already exists with that email address. Please log in instead."), 409
    if role == "student": ident = db_sqlite_backup.create_student(conn, name, username, generate_password_hash(password), email)
    else: ident = db_sqlite_backup.create_account(conn, role, name, username, generate_password_hash(password), (payload.get("organisation") or "").strip(), (payload.get("email") or "").strip())
    conn.close(); set_session(role, ident, name)
    return jsonify(status="success", redirect=url_for("assessment") if role == "student" else url_for("home")), 201

@app.route("/api/login", methods=["POST"])
def login_api():
    payload = request.get_json(silent=True) or {}; username, password = (payload.get("username") or "").strip().lower(), payload.get("password") or ""
    conn = db_sqlite_backup.get_connection(); student = db_sqlite_backup.student_by_username(conn, username); account = None if student else db_sqlite_backup.account_by_username(conn, username); conn.close()
    row, role = (student, "student") if student else (account, account["role"] if account else None)
    if not row or not check_password_hash(row["password_hash"], password): return jsonify(status="error", message="Incorrect username or password."), 401
    set_session(role, row["id"], row["name"])
    return jsonify(status="success", redirect=url_for("home"))

@app.route("/api/request-reset", methods=["POST"])
def request_reset():
    # Demo-safe flow: production would send a one-time, expiring email token here.
    return jsonify(status="success", message="If that account exists, a reset link has been sent to its registered email.")

def send_email(to_email, subject, body):
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    if not smtp_email or not smtp_password:
        # SMTP isn't configured yet — print the code so local/dev testing still works.
        print(f"[DEV] Email to {to_email}\nSubject: {subject}\n{body}")
        return
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = smtp_email
    message["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, [to_email], message.as_string())

def send_verification_email(to_email, code):
    send_email(to_email, "Verify your SkillBridge email", f"Your SkillBridge verification code is: {code}\nIt expires in 10 minutes.")

def send_programme_registration_email(to_email, student_name, program):
    publisher = program.get("provider") or "the programme publisher"
    body = f"""Hello {student_name},

You are registered for {program['title']} with {publisher}.

Format: {program['format']}
Duration: {program['duration']}
Mode: {program.get('mode') or 'To be confirmed'}

Message from the publisher:
{program['description']}

The publisher will share the next steps using this email address.

SkillBridge"""
    send_email(to_email, f"Registration confirmed: {program['title']}", body)

def send_application_status_email(to_email, student_name, opportunity_title, company, status):
    status_messages = {
        "Under Review": "Your application is now under review by the hiring team.",
        "Shortlisted": "Great news — you have been shortlisted for the next stage.",
        "Interview": "Congratulations — the hiring team would like to invite you to an interview. They will share the schedule and next steps shortly.",
        "Selected": "Congratulations — you have been selected. The organisation will contact you with onboarding or offer details.",
        "Not Selected": "Thank you for your interest. The organisation has decided to proceed with other candidates for this role.",
    }
    body = f"""Hello {student_name},

There is an update on your application for {opportunity_title} at {company}.

Status: {status}
{status_messages.get(status, 'Your application status has been updated.')}

SkillBridge"""
    send_email(to_email, f"Application update: {opportunity_title} — {status}", body)

def send_collaboration_accepted_email(to_email, academician_name, industry_name):
    body = f"""Hello {academician_name},

Good news — {industry_name} has accepted your SkillBridge collaboration request.

You can now follow up with the industry partner to agree on the next steps, such as a faculty development programme, live project, research collaboration, or mentorship activity.

SkillBridge"""
    send_email(to_email, "Collaboration request accepted", body)

@app.route("/api/verify-email/request", methods=["POST"])
@login_required
@role_required("industry", "academician")
def request_email_verification():
    conn = db_sqlite_backup.get_connection()
    account = db_sqlite_backup.account_by_id(conn, user_id())
    if not account["email"]:
        conn.close()
        return jsonify(status="error", message="Add a work email to your profile first."), 400
    code = f"{random.randint(0, 999999):06d}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    db_sqlite_backup.set_verification_code(conn, user_id(), code, expires)
    conn.close()
    send_verification_email(account["email"], code)
    return jsonify(status="success", message="A 6-digit code was sent to your email.")

@app.route("/api/verify-email/confirm", methods=["POST"])
@login_required
@role_required("industry", "academician")
def confirm_email_verification():
    code = ((request.get_json(silent=True) or {}).get("code") or "").strip()
    conn = db_sqlite_backup.get_connection()
    row = db_sqlite_backup.get_verification(conn, user_id())
    if not row or not row["verification_code"]:
        conn.close(); return jsonify(status="error", message="Request a code first."), 400
    if row["verification_expires"] < datetime.now(timezone.utc):
        conn.close(); return jsonify(status="error", message="That code expired. Request a new one."), 400
    if code != row["verification_code"]:
        conn.close(); return jsonify(status="error", message="Incorrect code."), 400
    db_sqlite_backup.clear_verification_code(conn, user_id())
    conn.close()
    return jsonify(status="success", message="Email verified.")


@app.route("/api/skills-catalog")
@login_required
def skills_catalog_api():
    conn = db_sqlite_backup.get_connection(); skills = db_sqlite_backup.student_skills(conn, user_id()) if user_role() == "student" else []; conn.close()
    return jsonify(status="success", categories=SKILL_CATALOG, current_skills=skills)

@app.route("/api/assessment/start", methods=["POST"])
@login_required
@role_required("student")
def start_assessment_api():
    skills = [s.strip().lower() for s in (request.get_json(silent=True) or {}).get("skills", []) if isinstance(s, str) and s.strip()]
    if not skills:
        return jsonify(status="error", message="Choose at least one skill to begin an adaptive assessment."), 400
    session["assessment_skills"] = sorted(set(skills))
    session["assessment_results"] = {}
    return jsonify(status="success", skills=session["assessment_skills"])


@app.route("/api/assessment/question")
@login_required
@role_required("student")
def skill_question_api():
    skill = (request.args.get("skill") or "").strip().lower()
    tier = (request.args.get("tier") or "beginner").strip().lower()
    if skill not in session.get("assessment_skills", []) or tier not in ("beginner", "intermediate", "expert"):
        return jsonify(status="error", message="That assessment question is not available."), 400
    question = QUESTION_BANK.get(skill, GENERIC_QUESTION_BANK)[tier]
    return jsonify(status="success", question={"id": f"{skill}:{tier}", "skill": skill, "tier": tier, "question": question["question"], "options": question["options"], "practice_url": question.get("practice_url")})


@app.route("/api/assessment/grade", methods=["POST"])
@login_required
@role_required("student")
def grade_skill_question_api():
    data = request.get_json(silent=True) or {}
    skill, tier = (data.get("skill") or "").strip().lower(), (data.get("tier") or "").strip().lower()
    if skill not in session.get("assessment_skills", []) or tier not in ("beginner", "intermediate", "expert"):
        return jsonify(status="error", message="Invalid assessment response."), 400
    question = QUESTION_BANK.get(skill, GENERIC_QUESTION_BANK)[tier]
    correct = str(data.get("answer")) == str(question["answer"])
    if tier == "beginner":
        result = {"complete": not correct, "next_tier": "intermediate" if correct else None, "level": "Beginner"}
    elif tier == "intermediate":
        result = {"complete": not correct, "next_tier": "expert" if correct else None, "level": "Intermediate"}
    else:
        result = {"complete": True, "next_tier": None, "level": "Expert" if correct else "Intermediate"}
    if result["complete"]:
        results = session.get("assessment_results", {})
        results[skill] = {"level": result["level"], "score": {"Beginner": 1, "Intermediate": 2, "Expert": 3}[result["level"]]}
        session["assessment_results"] = results
    return jsonify(status="success", correct=correct, **result)

@app.route("/api/assess", methods=["POST"])
@login_required
@role_required("student")
def assess_api():
    skills = session.get("assessment_skills", [])
    results = session.get("assessment_results", {})
    if not skills or set(skills) != set(results):
        return jsonify(status="error", message="Finish the adaptive path for each selected skill before saving your profile."), 400
    conn = db_sqlite_backup.get_connection(); db_sqlite_backup.set_student_skills(conn, user_id(), skills, results=results); conn.close()
    session.pop("assessment_skills", None); session.pop("assessment_results", None)
    return jsonify(status="success", results=results, message="Your skill-specific readiness profile is ready.")

@app.route("/api/opportunities")
@login_required
@role_required("student")
def opportunities_api():
    conn = db_sqlite_backup.get_connection(); student = db_sqlite_backup.student_by_id(conn, user_id()); opportunities = db_sqlite_backup.opportunities_with_skills(conn)
    applied = {r["opportunity_id"]: r["status"] for r in db_sqlite_backup.applications_for_student(conn, user_id())}
    skills = db_sqlite_backup.student_skills(conn, user_id()); conn.close()
    ranked = get_recommendations({"id": student["id"], "name": student["name"], "skills": skills}, opportunities)
    query = (request.args.get("q") or "").strip().lower()
    kind = (request.args.get("type") or "").strip().lower()
    location = (request.args.get("location") or "").strip().lower()
    sources_by_id = {source["id"]: source for source in opportunities}
    for item in ranked:
        source = sources_by_id[item["opportunity_id"]]
        item["application_status"] = applied.get(item["opportunity_id"])
        item["location"] = source.get("location")
        item["duration"] = source.get("duration")
        item["description"] = source.get("description")
    if query or kind or location:
        ranked = [item for item in ranked if (
            (not query or query in " ".join([item["title"], item["company"], *item["matched_skills"], *item["missing_skills"]]).lower())
            and (not kind or kind == item["type"].lower())
            and (not location or location in (item.get("location") or "").lower())
        )]
    return jsonify(status="success", opportunities=ranked, filters={"types": sorted({o.get("type") for o in opportunities}), "locations": sorted({o.get("location") for o in opportunities})})

@app.route("/api/learning-programs")
@login_required
def learning_programs_api():
    conn = db_sqlite_backup.get_connection()
    try:
        programs = db_sqlite_backup.learning_programs(conn)
        if user_role() == "student":
            registered_ids = db_sqlite_backup.registered_learning_program_ids(conn, user_id())
            for program in programs:
                program["registered"] = program["id"] in registered_ids
    except Exception:
        conn.rollback()
        return jsonify(status="error", message="Learning programmes need the Supabase setup query before they can be used."), 503
    finally:
        conn.close()
    return jsonify(status="success", programs=programs)

@app.route("/api/learning-programs", methods=["POST"])
@login_required
@role_required("industry")
def create_learning_program_api():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    format_name = (data.get("format") or "").strip()
    duration = (data.get("duration") or "").strip()
    description = (data.get("description") or "").strip()
    mode = (data.get("mode") or "").strip()
    audience = (data.get("audience") or "").strip()
    skills = [skill.strip().lower() for skill in (data.get("skills") or "").split(",") if skill.strip()]
    if not title or format_name not in ("Certification", "Workshop", "Mentorship") or not duration or not skills or not description:
        return jsonify(status="error", message="Add a title, format, duration, skills, and a message for students."), 400
    conn = db_sqlite_backup.get_connection()
    try:
        account = db_sqlite_backup.account_by_id(conn, user_id())
        db_sqlite_backup.create_learning_program(conn, user_id(), {"title": title, "format": format_name, "duration": duration, "skills": skills, "description": description, "mode": mode or "Online", "audience": audience or "Students", "publisher_name": account["organisation"] or account["name"]})
    except Exception:
        conn.rollback()
        return jsonify(status="error", message="Learning programmes need the Supabase setup query before they can be published."), 503
    finally:
        conn.close()
    return jsonify(status="success", message="Learning programme published.")

@app.route("/api/learning-programs/<int:program_id>/register", methods=["POST"])
@login_required
@role_required("student")
def register_learning_program_api(program_id):
    conn = db_sqlite_backup.get_connection()
    try:
        result, created = db_sqlite_backup.register_for_learning_program(conn, user_id(), program_id)
        if not result:
            return jsonify(status="error", message="Programme or student account was not found."), 404
        if created is None:
            return jsonify(status="error", message="Add an email to your student profile before registering."), 400
        if created:
            publisher_id = result["program"].get("publisher_account_id")
            if publisher_id:
                conn.execute(
                    "INSERT INTO notifications(account_id, message, link) VALUES (?, ?, ?)",
                    (publisher_id, f"{result['student']['name']} registered for your programme: {result['program']['title']}", "/")
                )
                conn.commit()
            try:
                send_programme_registration_email(result["student"]["email"], result["student"]["name"], result["program"])
            except Exception as error:
                # Registration has already succeeded; keep the publisher alert
                # and log mail delivery issues rather than losing the signup.
                app.logger.error("Programme registration email failed: %s", error)
        message = "You are registered. A confirmation email with the publisher’s message has been sent." if created else "You are already registered for this programme."
        return jsonify(status="success", message=message, registered=True)
    except Exception:
        conn.rollback()
        return jsonify(status="error", message="Learning programmes need the Supabase setup query before registrations can be saved."), 503
    finally:
        conn.close()

@app.route("/api/announcements")
@login_required
@role_required("student", "academician")
def announcements_api():
    conn = db_sqlite_backup.get_connection()
    try:
        # Academicians keep the Announcements section, but announcements are
        # addressed to programme registrants / opportunity applicants only.
        items = db_sqlite_backup.announcements_for_student(conn, user_id()) if user_role() == "student" else []
        return jsonify(status="success", announcements=items)
    except Exception:
        conn.rollback()
        return jsonify(status="error", message="Announcements need the Supabase announcements setup query."), 503
    finally:
        conn.close()

@app.route("/api/publisher-announcement-targets")
@login_required
@role_required("industry")
def publisher_announcement_targets_api():
    conn = db_sqlite_backup.get_connection()
    try:
        opportunities = db_sqlite_backup.opportunities_with_skills(conn, user_id())
        programs = [item for item in db_sqlite_backup.learning_programs(conn) if item["publisher_account_id"] == user_id()]
        return jsonify(status="success", opportunities=opportunities, programs=programs)
    except Exception:
        conn.rollback()
        return jsonify(status="error", message="Announcements need the Supabase announcements and learning-programmes setup queries."), 503
    finally:
        conn.close()

@app.route("/api/publisher-programme-registrations")
@login_required
@role_required("industry")
def publisher_programme_registrations_api():
    conn = db_sqlite_backup.get_connection()
    try:
        registrations = db_sqlite_backup.programme_registrations_for_publisher(conn, user_id())
        return jsonify(status="success", registrations=registrations)
    except Exception:
        conn.rollback()
        return jsonify(status="error", message="Learning programmes need the Supabase setup query before learner registrations can be viewed."), 503
    finally:
        conn.close()

@app.route("/api/announcements", methods=["POST"])
@login_required
@role_required("industry")
def create_announcement_api():
    data = request.get_json(silent=True) or {}
    target_type = (data.get("target_type") or "").strip()
    target_id = to_int_or_none(data.get("target_id"))
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()
    if target_type not in ("opportunity", "program") or not target_id or not subject or not message:
        return jsonify(status="error", message="Choose a programme or opportunity, then write a subject and message."), 400
    conn = db_sqlite_backup.get_connection()
    try:
        result, recipient_count = db_sqlite_backup.create_announcement(conn, user_id(), target_type, target_id, subject, message)
        if not result:
            return jsonify(status="error", message="That publishing target was not found for your account."), 404
        if not recipient_count:
            return jsonify(status="error", message="No students have registered or applied for this item yet."), 400
        return jsonify(status="success", message=f"Announcement sent to {recipient_count} student{'s' if recipient_count != 1 else ''}.")
    except Exception:
        conn.rollback()
        return jsonify(status="error", message="Announcements need the Supabase announcements setup query."), 503
    finally:
        conn.close()

@app.route("/api/faculty-programs")
@login_required
@role_required("academician")
def faculty_programs_api():
    return jsonify(status="success", programs=FACULTY_PROGRAMS)

@app.route("/api/apply/<int:opportunity_id>", methods=["POST"])
@login_required
@role_required("student")
def apply_api(opportunity_id):
    conn = db_sqlite_backup.get_connection(); opp = conn.execute("SELECT posted_by_account_id FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
    if not opp: conn.close(); return jsonify(status="error", message="Opportunity not found."), 404
    existing = conn.execute("SELECT id FROM applications WHERE student_id=? AND opportunity_id=?", (user_id(), opportunity_id)).fetchone()
    if existing:
        conn.close()
        return jsonify(status="success", message="You have already applied for this opportunity.", already_applied=True)
    conn.execute("INSERT INTO applications(student_id, opportunity_id) VALUES (?, ?)", (user_id(), opportunity_id))
    if opp["posted_by_account_id"]:
        conn.execute("INSERT INTO notifications(account_id, message, link) VALUES (?, ?, ?)", (opp["posted_by_account_id"], f"New candidate application from {session['user_name']}", "/"))
    conn.commit(); conn.close(); return jsonify(status="success", message="Application submitted. You can track every update in your profile.")

@app.route("/api/profile", methods=["GET", "PUT"])
@login_required
def profile_api():
    conn = db_sqlite_backup.get_connection(); role, ident = user_role(), user_id()
    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        if role == "student" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (data.get("email") or "").strip()):
            conn.close()
            return jsonify(status="error", message="Enter a valid email address for your student profile."), 400
        if role == "student": conn.execute("UPDATE students SET name=?, headline=?, bio=?, email=? WHERE id=?", ((data.get("name") or "").strip(), (data.get("headline") or "").strip(), (data.get("bio") or "").strip(), (data.get("email") or "").strip().lower(), ident))
        else: conn.execute("UPDATE accounts SET name=?, organisation=?, email=? WHERE id=?", ((data.get("name") or "").strip(), (data.get("organisation") or "").strip(), (data.get("email") or "").strip(), ident))
        conn.commit(); session["user_name"] = (data.get("name") or session["user_name"]).strip()
    user = db_sqlite_backup.student_by_id(conn, ident) if role == "student" else db_sqlite_backup.account_by_id(conn, ident)
    if not user:
        conn.close()
        session.clear()
        return jsonify(status="error", message="Your session is no longer valid. Please log in again."), 401
    response = {"status": "success", "role": role, "user": dict(user), "stats": db_sqlite_backup.dashboard_stats(conn, role, ident)}
    if role == "student":
        skills = db_sqlite_backup.student_skills(conn, ident, True)
        applications = db_sqlite_backup.applications_for_student(conn, ident)
        portfolio = db_sqlite_backup.portfolio_for_student(conn, ident)
        try:
            registered_programs = db_sqlite_backup.registered_learning_programs_for_student(conn, ident)
        except Exception:
            registered_programs = []
        response.update(skills=skills, applications=applications, portfolio=portfolio, readiness=readiness_breakdown(skills, len(portfolio), len(applications)), learning_programs=LEARNING_PROGRAMS, registered_programs=registered_programs)
    elif role == "industry":
        response.update(
            opportunities=db_sqlite_backup.opportunities_with_skills(conn, ident),
            applications=db_sqlite_backup.applications_for_industry(conn, ident),
            notifications=[dict(x) for x in conn.execute("SELECT * FROM notifications WHERE account_id=? ORDER BY created_at DESC LIMIT 6", (ident,)).fetchall()],
            collaboration_requests=db_sqlite_backup.collaboration_requests_for_industry(conn, ident),
            learning_programs=LEARNING_PROGRAMS,
            recruiter_analytics={"skill_demand": [["Quality assurance", 82], ["Clinical documentation", 71], ["Panchakarma", 63], ["Biostatistics", 54]], "time_to_fill": "12 days", "shortlist_rate": "38%"},
            demo_pipeline=DEMO_PIPELINE,
        )
    else:
        response.update(
            opportunities=db_sqlite_backup.opportunities_with_skills(conn),
            students=db_sqlite_backup.all_students_summary(conn),
            industry_partners=db_sqlite_backup.industry_partners(conn),
            collaboration_requests=db_sqlite_backup.collaboration_requests_for_academician(conn, ident),
            faculty_programs=FACULTY_PROGRAMS,
            institution_analytics={"skill_gaps": [["Biostatistics", 58], ["Clinical research", 46], ["Quality assurance", 42]], "placement_progress": [32, 44, 57, 68], "internship_participation": "67%", "readiness_average": "64%"},
        )
    conn.close(); return jsonify(response)

@app.route("/api/portfolio", methods=["POST"])
@login_required
@role_required("student")
def add_portfolio_item():
    data = request.get_json(silent=True) or {}; item_type = data.get("item_type")
    if item_type not in ("Project", "Certification", "Achievement", "Internship") or not (data.get("title") or "").strip(): return jsonify(status="error", message="Choose an item type and provide a title."), 400
    conn = db_sqlite_backup.get_connection(); conn.execute("INSERT INTO portfolio_items(student_id,item_type,title,issuer,link,description) VALUES(?,?,?,?,?,?)", (user_id(), item_type, data["title"].strip(), (data.get("issuer") or "").strip(), (data.get("link") or "").strip(), (data.get("description") or "").strip())); conn.commit(); conn.close()
    return jsonify(status="success", message="Portfolio item added.")

@app.route("/api/opportunities", methods=["POST"])
@login_required
@role_required("industry")
def create_opportunity_api():
    data = request.get_json(silent=True) or {}
    required = [s.strip().lower() for s in (data.get("required_skills") or "").split(",") if s.strip()]
    preferred = [s.strip().lower() for s in (data.get("preferred_skills") or "").split(",") if s.strip()]
    for key in ("title", "type", "description", "location", "duration"):
        if not (data.get(key) or "").strip(): return jsonify(status="error", message=f"{key.replace('_', ' ').title()} is required."), 400
    if not required: return jsonify(status="error", message="Add at least one required skill."), 400
    data.update(required_skills=required, preferred_skills=preferred)
    conn = db_sqlite_backup.get_connection(); account = db_sqlite_backup.account_by_id(conn, user_id()); ident = db_sqlite_backup.create_opportunity(conn, user_id(), account["organisation"] or account["name"], data); conn.close()
    return jsonify(status="success", opportunity_id=ident, message="Opportunity published and ready for matched candidates.")

@app.route("/api/opportunities/<int:opportunity_id>", methods=["DELETE"])
@login_required
@role_required("industry")
def delete_opportunity_api(opportunity_id):
    conn = db_sqlite_backup.get_connection()
    deleted = db_sqlite_backup.delete_opportunity(conn, opportunity_id, user_id())
    conn.close()
    return (jsonify(status="success", message="Opportunity removed.")) if deleted else (jsonify(status="error", message="Opportunity not found."), 404)

@app.route("/api/collaboration-requests", methods=["POST"])
@login_required
@role_required("academician")
def create_collaboration_request_api():
    data = request.get_json(silent=True) or {}
    industry_account_id = to_int_or_none(data.get("industry_account_id"))
    opportunity_id = to_int_or_none(data.get("opportunity_id"))
    message = (data.get("message") or "").strip()
    if not industry_account_id or not message:
        return jsonify(status="error", message="Choose a partner and add a message."), 400
    conn = db_sqlite_backup.get_connection()
    target = db_sqlite_backup.account_by_id(conn, industry_account_id)
    if not target or target["role"] != "industry":
        conn.close()
        return jsonify(status="error", message="Choose a valid industry partner."), 400
    existing = conn.execute(
        "SELECT 1 FROM collaboration_requests WHERE academician_id = ? AND industry_account_id = ? LIMIT 1",
        (user_id(), industry_account_id)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify(status="error", message="You have already sent a collaboration request to this industry partner."), 409
    request_id = db_sqlite_backup.create_collaboration_request(conn, user_id(), industry_account_id, opportunity_id, message)
    conn.execute("INSERT INTO notifications(account_id, message, link) VALUES (?, ?, ?)", (industry_account_id, f"{session['user_name']} wants to collaborate: {message[:80]}", "/profile"))
    conn.commit(); conn.close()
    return jsonify(status="success", request_id=request_id, message="Collaboration request sent.")

@app.route("/api/collaboration-requests/<int:request_id>", methods=["PATCH"])
@login_required
@role_required("industry")
def update_collaboration_request_api(request_id):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in ("Acknowledged", "Declined"):
        return jsonify(status="error", message="Invalid status."), 400
    conn = db_sqlite_backup.get_connection()
    request_details = conn.execute(
        """
        SELECT academician.name AS academician_name, academician.email AS academician_email,
               COALESCE(industry.organisation, industry.name) AS industry_name
        FROM collaboration_requests cr
        JOIN accounts academician ON academician.id = cr.academician_id
        JOIN accounts industry ON industry.id = cr.industry_account_id
        WHERE cr.id = ? AND cr.industry_account_id = ?
        """, (request_id, user_id())
    ).fetchone()
    updated = db_sqlite_backup.update_collaboration_request_status(conn, request_id, user_id(), status)
    conn.close()
    if updated and status == "Acknowledged" and request_details and request_details["academician_email"]:
        try:
            send_collaboration_accepted_email(request_details["academician_email"], request_details["academician_name"], request_details["industry_name"])
        except Exception as error:
            app.logger.error("Collaboration acceptance email failed: %s", error)
    return jsonify(status="success", message="Updated.") if updated else (jsonify(status="error", message="Request not found."), 404)

@app.route("/api/applications/<int:application_id>", methods=["PATCH"])
@login_required
@role_required("industry")
def update_application(application_id):
    status = (request.get_json(silent=True) or {}).get("status")
    allowed = {"Submitted", "Under Review", "Shortlisted", "Interview", "Selected", "Not Selected"}
    if status not in allowed: return jsonify(status="error", message="Invalid application status."), 400
    conn = db_sqlite_backup.get_connection()
    candidate = conn.execute(
        """
        SELECT s.name, s.email, o.title, o.company
        FROM applications ap
        JOIN students s ON s.id = ap.student_id
        JOIN opportunities o ON o.id = ap.opportunity_id
        WHERE ap.id = ? AND o.posted_by_account_id = ?
        """, (application_id, user_id())
    ).fetchone()
    if not candidate:
        conn.close()
        return jsonify(status="error", message="Application not found."), 404
    conn.execute("UPDATE applications SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, application_id))
    conn.commit()
    conn.close()
    try:
        if candidate["email"]:
            send_application_status_email(candidate["email"], candidate["name"], candidate["title"], candidate["company"], status)
    except Exception as error:
        app.logger.error("Application status email failed: %s", error)
    return jsonify(status="success", message="Candidate status updated and the applicant has been emailed.")

@app.route("/api/notifications", methods=["DELETE"])
@login_required
@role_required("industry", "academician")
def clear_notifications_api():
    conn = db_sqlite_backup.get_connection()
    result = conn.execute("DELETE FROM notifications WHERE account_id = ?", (user_id(),))
    conn.commit()
    conn.close()
    return jsonify(status="success", message=f"Cleared {result.rowcount} notification{'s' if result.rowcount != 1 else ''}.")


if __name__ == "__main__":
    # Listen on the local network so classmates on the same Wi-Fi can open
    # the demo. Keep Flask's debugger off when the app is reachable by others.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

import os
import re
from functools import wraps
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import db as db_sqlite_backup
from matcher import get_recommendations

app = Flask(__name__)
app.secret_key = os.environ.get("SKILLBRIDGE_SECRET_KEY", "dev-secret-key-change-me")
db_sqlite_backup.init_db()

SKILL_CATALOG = {
    "Programming & Development": ["python", "java", "cpp", "javascript", "html", "css", "flask", "react", "sql"],
    "Data & Analytics": ["data-analysis", "statistics", "excel", "financial-modeling", "mongodb"],
    "Science & Lab Skills": ["lab-safety", "microscopy", "titration", "chemical-analysis", "data-recording", "report-writing"],
    "Design & Creative": ["graphic-design", "figma", "video-editing", "photography"],
    "Business & Communication": ["content-writing", "social-media", "seo", "presentation-skills", "public-speaking", "project-management"],
}
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
    name, username, password = (payload.get("name") or "").strip(), (payload.get("username") or "").strip().lower(), payload.get("password") or ""
    role = payload.get("role", "student")
    if role not in ("student", "industry", "academician"): return jsonify(status="error", message="Choose a valid account type."), 400
    if not name or not username or not password: return jsonify(status="error", message="Name, username and password are required."), 400
    if not valid_username(username): return jsonify(status="error", message="Use 3–30 letters, numbers, or underscores for your username."), 400
    if len(password) < 6: return jsonify(status="error", message="Use a password with at least 6 characters."), 400
    conn = db_sqlite_backup.get_connection()
    if db_sqlite_backup.username_taken(conn, username): conn.close(); return jsonify(status="error", message="That username is already in use."), 409
    if role == "student": ident = db_sqlite_backup.create_student(conn, name, username, generate_password_hash(password))
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

@app.route("/api/verify-email", methods=["POST"])
@login_required
@role_required("industry", "academician")
def verify_email():
    conn = db_sqlite_backup.get_connection(); conn.execute("UPDATE accounts SET verified=1 WHERE id=?", (user_id(),)); conn.commit(); conn.close()
    return jsonify(status="success", message="Email verified for this demo account.")


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
    for item in ranked: item["application_status"] = applied.get(item["opportunity_id"])
    return jsonify(status="success", opportunities=ranked)

@app.route("/api/apply/<int:opportunity_id>", methods=["POST"])
@login_required
@role_required("student")
def apply_api(opportunity_id):
    conn = db_sqlite_backup.get_connection(); opp = conn.execute("SELECT posted_by_account_id FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
    if not opp: conn.close(); return jsonify(status="error", message="Opportunity not found."), 404
    conn.execute("INSERT OR IGNORE INTO applications(student_id, opportunity_id) VALUES (?, ?)", (user_id(), opportunity_id))
    if opp["posted_by_account_id"]:
        conn.execute("INSERT INTO notifications(account_id, message, link) VALUES (?, ?, ?)", (opp["posted_by_account_id"], f"New candidate application from {session['user_name']}", "/"))
    conn.commit(); conn.close(); return jsonify(status="success", message="Application submitted. You can track every update in your profile.")

@app.route("/api/profile", methods=["GET", "PUT"])
@login_required
def profile_api():
    conn = db_sqlite_backup.get_connection(); role, ident = user_role(), user_id()
    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        if role == "student": conn.execute("UPDATE students SET name=?, headline=?, bio=? WHERE id=?", ((data.get("name") or "").strip(), (data.get("headline") or "").strip(), (data.get("bio") or "").strip(), ident))
        else: conn.execute("UPDATE accounts SET name=?, organisation=?, email=? WHERE id=?", ((data.get("name") or "").strip(), (data.get("organisation") or "").strip(), (data.get("email") or "").strip(), ident))
        conn.commit(); session["user_name"] = (data.get("name") or session["user_name"]).strip()
    user = db_sqlite_backup.student_by_id(conn, ident) if role == "student" else db_sqlite_backup.account_by_id(conn, ident)
    response = {"status": "success", "role": role, "user": dict(user), "stats": db_sqlite_backup.dashboard_stats(conn, role, ident)}
    if role == "student": response.update(skills=db_sqlite_backup.student_skills(conn, ident, True), applications=db_sqlite_backup.applications_for_student(conn, ident), portfolio=db_sqlite_backup.portfolio_for_student(conn, ident))
    elif role == "industry":
        response.update(opportunities=db_sqlite_backup.opportunities_with_skills(conn, ident), applications=db_sqlite_backup.applications_for_industry(conn, ident), notifications=[dict(x) for x in conn.execute("SELECT * FROM notifications WHERE account_id=? ORDER BY created_at DESC LIMIT 6", (ident,)).fetchall()])
    else: response["opportunities"] = db_sqlite_backup.opportunities_with_skills(conn)
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

@app.route("/api/applications/<int:application_id>", methods=["PATCH"])
@login_required
@role_required("industry")
def update_application(application_id):
    status = (request.get_json(silent=True) or {}).get("status")
    allowed = {"Submitted", "Under Review", "Shortlisted", "Interview", "Selected", "Not Selected"}
    if status not in allowed: return jsonify(status="error", message="Invalid application status."), 400
    conn = db_sqlite_backup.get_connection(); result = conn.execute("""UPDATE applications SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND opportunity_id IN
        (SELECT id FROM opportunities WHERE posted_by_account_id=?)""", (status, application_id, user_id())); conn.commit(); conn.close()
    return jsonify(status="success", message="Candidate status updated.") if result.rowcount else (jsonify(status="error", message="Application not found."), 404)


if __name__ == "__main__":
    # Listen on the local network so classmates on the same Wi-Fi can open
    # the demo. Keep Flask's debugger off when the app is reachable by others.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

import re
from functools import wraps

from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

import db
from matcher import get_recommendations

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me-in-production"  # set via env var in real deployment

db.init_db()

# ---------------------------------------------------------------------------
# Skill catalog — drives the dynamic skill-assessment questionnaire.
# Deliberately spans multiple domains (not just programming) so the platform
# demonstrates matching for "sciences or anything", per the problem statement.
# Students can also add free-text skills not listed here (see /assessment).
# ---------------------------------------------------------------------------
SKILL_CATALOG = {
    "Programming & Development": [
        "python", "java", "cpp", "javascript", "html", "css", "flask", "django", "react", "sql",
    ],
    "Data & Analytics": [
        "data-analysis", "statistics", "excel", "financial-modeling", "mongodb",
    ],
    "Science & Lab Skills": [
        "lab-safety", "microscopy", "titration", "chemical-analysis", "data-recording", "report-writing",
    ],
    "Design & Creative": [
        "graphic-design", "figma", "video-editing", "photography",
    ],
    "Business & Communication": [
        "content-writing", "social-media", "seo", "presentation-skills", "public-speaking", "project-management",
    ],
}


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "student_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"status": "error", "message": "Not logged in"}), 401
            return redirect(url_for("login_page"))
        return view_func(*args, **kwargs)
    return wrapped


def valid_username(username):
    return bool(re.fullmatch(r"[a-zA-Z0-9_]{3,30}", username or ""))


# -------------------------------------------------------------------
# HTML Page Routes
# -------------------------------------------------------------------

@app.route('/')
@login_required
def home():
    conn = db.get_connection()
    student = db.get_student_by_id(conn, session["student_id"])
    conn.close()
    return render_template('index.html', student_name=student["name"] if student else "")


@app.route('/assessment')
@login_required
def assessment():
    return render_template('assessment.html', skill_catalog=SKILL_CATALOG)


@app.route('/login')
def login_page():
    if "student_id" in session:
        return redirect(url_for("home"))
    return render_template('login.html')


@app.route('/register')
def register_page():
    if "student_id" in session:
        return redirect(url_for("home"))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# -------------------------------------------------------------------
# Auth API
# -------------------------------------------------------------------

@app.route('/api/register', methods=['POST'])
def register_api():
    req = request.get_json(silent=True) or {}
    name = (req.get("name") or "").strip()
    username = (req.get("username") or "").strip().lower()
    password = req.get("password") or ""

    if not name or not username or not password:
        return jsonify({"status": "error", "message": "Name, username and password are all required."}), 400
    if not valid_username(username):
        return jsonify({"status": "error", "message": "Username must be 3-30 characters: letters, numbers, underscore."}), 400
    if len(password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters."}), 400

    conn = db.get_connection()
    if db.get_student_by_username(conn, username):
        conn.close()
        return jsonify({"status": "error", "message": "That username is already taken."}), 409

    student_id = db.create_student(conn, name, username, generate_password_hash(password))
    conn.close()

    session["student_id"] = student_id
    session["student_name"] = name
    return jsonify({"status": "success", "student_id": student_id, "redirect": url_for("assessment")}), 201


@app.route('/api/login', methods=['POST'])
def login_api():
    req = request.get_json(silent=True) or {}
    username = (req.get("username") or "").strip().lower()
    password = req.get("password") or ""

    conn = db.get_connection()
    student = db.get_student_by_username(conn, username)
    conn.close()

    if not student or not check_password_hash(student["password_hash"], password):
        return jsonify({"status": "error", "message": "Invalid username or password."}), 401

    session["student_id"] = student["id"]
    session["student_name"] = student["name"]
    return jsonify({"status": "success", "student_id": student["id"], "redirect": url_for("home")}), 200


# -------------------------------------------------------------------
# REST API Endpoints
# -------------------------------------------------------------------

@app.route('/api/skills-catalog', methods=['GET'])
def skills_catalog_api():
    """Powers the dynamic assessment form — categories + candidate skills,
    plus whichever skills the logged-in student already has on file."""
    current_skills = []
    if "student_id" in session:
        conn = db.get_connection()
        current_skills = db.get_student_skills(conn, session["student_id"])
        conn.close()
    return jsonify({"status": "success", "categories": SKILL_CATALOG, "current_skills": current_skills}), 200


@app.route('/api/opportunities', methods=['GET'])
@login_required
def get_opportunities_api():
    """Fetches opportunities and ranks them for the logged-in student."""
    try:
        conn = db.get_connection()
        student_row = db.get_student_by_id(conn, session["student_id"])
        student = {
            "id": student_row["id"],
            "name": student_row["name"],
            "skills": db.get_student_skills(conn, student_row["id"]),
        }
        opportunities = db.get_all_opportunities_with_skills(conn)
        conn.close()

        ranked_matches = get_recommendations(student, opportunities)

        return jsonify({
            "status": "success",
            "student_id": student["id"],
            "student_name": student["name"],
            "total_matches": len(ranked_matches),
            "opportunities": ranked_matches
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"Server Error: {str(e)}"}), 500


@app.route('/api/assess', methods=['POST'])
@login_required
def save_assessment_api():
    try:
        req_data = request.get_json(silent=True) or {}
        if "skills" not in req_data:
            return jsonify({"status": "error", "message": "'skills' array is required."}), 400

        new_skills = [s for s in req_data.get("skills", []) if isinstance(s, str) and s.strip()]

        conn = db.get_connection()
        db.set_student_skills(conn, session["student_id"], new_skills)
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Assessment skills saved.",
            "updated_skills": sorted({s.strip().lower() for s in new_skills})
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to save assessment: {str(e)}"}), 500


@app.route('/api/apply/<int:opportunity_id>', methods=['POST'])
@login_required
def apply_api(opportunity_id):
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO applications (student_id, opportunity_id) VALUES (?, ?)",
            (session["student_id"], opportunity_id),
        )
        conn.commit()
        return jsonify({"status": "success", "message": "Application recorded."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------------------
# Main Server Entry Point
# -------------------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True, port=5000)

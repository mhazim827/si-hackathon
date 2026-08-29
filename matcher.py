import json
from pathlib import Path

# NOTE: This matching logic is intentionally skill-agnostic. It never checks
# what a skill "is" — it just intersects sets of strings. That means it works
# identically whether the skills involved are "python"/"sql", or
# "microscopy"/"titration", or "graphic-design"/"figma". Any domain works as
# long as the student's skill list and the opportunity's required/preferred
# skill lists use comparable skill names.

def match_student_to_opportunity(student, opportunity):
    student_skills = {
        skill.strip().lower()
        for skill in (student.get("skills") or [])
    }
    required_skills = {
        skill.strip().lower()
        for skill in (opportunity.get("required_skills") or [])
    }
    preferred_skills = {
        skill.strip().lower()
        for skill in (opportunity.get("preferred_skills") or [])
    }

    matched_required = sorted(student_skills & required_skills)
    missing_skills = sorted(required_skills - student_skills)
    matched_preferred = sorted(student_skills & preferred_skills)

    # A match should be meaningful even when an opportunity has no optional
    # skills. Previously a role with optional skills could cap a candidate at
    # 80%, and weakly-normalised data made obvious overlaps look unconvincing.
    # Required capability is worth 70%; optional capability fills the
    # remaining 30%. If no optional capability is listed, required skills
    # account for the full score.
    if required_skills:
        required_weight = 70 if preferred_skills else 100
        required_score = (len(matched_required) / len(required_skills)) * required_weight
    else:
        required_score = 70.0 if preferred_skills else 100.0

    # Preferred Skills (20% Weight)
    if preferred_skills:
        preferred_score = (len(matched_preferred) / len(preferred_skills)) * 30
    else:
        preferred_score = 0.0

    match_score = min(100, round(required_score + preferred_score, 0))

    # Status Label
    if match_score >= 75:
        status = "Strong Match"
    elif match_score >= 50:
        status = "Partial Match"
    else:
        status = "Skill Gap Detected"

    return {
        "opportunity_id": opportunity.get("id"),
        "title": opportunity.get("title", "Untitled Position"),
        "company": opportunity.get("company", "N/A"),
        "type": opportunity.get("type", "Internship"),
        "match_score": match_score,
        "status": status,
        "matched_skills": matched_required + matched_preferred,
        "missing_skills": missing_skills,
        "why_match": (
            f"You already meet {len(matched_required)} of {len(required_skills)} core skill"
            f"{'s' if len(required_skills) != 1 else ''}"
            + (f" and add {len(matched_preferred)} preferred strength{'s' if len(matched_preferred) != 1 else ''}." if preferred_skills else ".")
        ),
        "learning_path": missing_skills[:3]
    }

def get_recommendations(student, opportunities):
    if not opportunities:
        return []
    results = [
        match_student_to_opportunity(student, opp)
        for opp in opportunities
    ]
    return sorted(results, key=lambda item: item["match_score"], reverse=True)

# Standalone execution test — reads the legacy JSON fixture directly (useful
# for quick sanity checks without spinning up Flask/SQLite).
if __name__ == '__main__':
    BASE_DIR = Path(__file__).resolve().parent
    MOCK_DATA_PATH = BASE_DIR / "data" / "mock_data.json"

    try:
        with open(MOCK_DATA_PATH, "r") as file:
            data = json.load(file)

        students = data.get("students") or [data.get("student", {})]
        student = students[0]
        opportunities = data.get("opportunities", [])

        recommendations = get_recommendations(student, opportunities)
        print(f"--- Loaded successfully from {MOCK_DATA_PATH} ---")
        print(json.dumps(recommendations, indent=2))
    except FileNotFoundError:
        print(f"Error: Unable to locate mock_data.json at {MOCK_DATA_PATH}")

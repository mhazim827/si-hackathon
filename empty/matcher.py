import json
from pathlib import Path

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

    # Required Skills (80% Weight)
    if required_skills:
        required_score = (len(matched_required) / len(required_skills)) * 80
    else:
        required_score = 80.0

    # Preferred Skills (20% Weight)
    if preferred_skills:
        preferred_score = (len(matched_preferred) / len(preferred_skills)) * 20
    else:
        preferred_score = 0.0

    match_score = round(required_score + preferred_score, 2)

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
        "missing_skills": missing_skills
    }

def get_recommendations(student, opportunities):
    if not opportunities:
        return []
    results = [
        match_student_to_opportunity(student, opp) 
        for opp in opportunities
    ]
    return sorted(results, key=lambda item: item["match_score"], reverse=True)

# Standalone execution test matching your tree layout
if __name__ == '__main__':
    BASE_DIR = Path(__file__).resolve().parent
    MOCK_DATA_PATH = BASE_DIR / "empty" / "data" / "mock_data.json"
    
    try:
        with open(MOCK_DATA_PATH, "r") as file:
            data = json.load(file)

        student = data.get("student", {})
        opportunities = data.get("opportunities", [])
        
        recommendations = get_recommendations(student, opportunities)
        print(f"--- Loaded successfully from {MOCK_DATA_PATH} ---")
        print(json.dumps(recommendations, indent=2))
    except FileNotFoundError:
        print(f"Error: Unable to locate mock_data.json at {MOCK_DATA_PATH}")
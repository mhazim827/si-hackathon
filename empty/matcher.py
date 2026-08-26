import json

def match_student_to_opportunity(student, opportunity):
    """
    Compares one student profile dictionary with one opportunity dictionary.
    Safely handles missing keys, null values, and casing differences.
    """
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

    # 1. Calculate Required Score (80% total weight)
    if required_skills:
        required_score = (len(matched_required) / len(required_skills)) * 80
    else:
        required_score = 80.0

    # 2. Calculate Preferred Score (20% total weight)
    if preferred_skills:
        preferred_score = (len(matched_preferred) / len(preferred_skills)) * 20
    else:
        preferred_score = 0.0

    match_score = round(required_score + preferred_score, 2)

    # 3. Determine Status Badge Label
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
    """Sorts and returns all opportunities by highest match score."""
    if not opportunities:
        return []
        
    results = [
        match_student_to_opportunity(student, opp) 
        for opp in opportunities
    ]
    return sorted(results, key=lambda item: item["match_score"], reverse=True)


# Local Standalone Testing (Simple 3-line path)
if __name__ == '__main__':
    with open("data/mock_data.json", "r") as file:
        data = json.load(file)

    recommendations = get_recommendations(data["student"], data["opportunities"])
    print(json.dumps(recommendations, indent=2))
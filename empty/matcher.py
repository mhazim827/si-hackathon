def match_student_to_opportunity(student, opportunity):
    """
    Compare one student profile with one internship/job opportunity.
    Both inputs are dictionaries.
    """
    student_skills = {
        skill.strip().lower()
        for skill in student.get("skills", [])
    }

    required_skills = {
        skill.strip().lower()
        for skill in opportunity.get("required_skills", [])
    }

    preferred_skills = {
        skill.strip().lower()
        for skill in opportunity.get("preferred_skills", [])
    }

    matched_required = sorted(student_skills & required_skills)
    missing_skills = sorted(required_skills - student_skills)
    matched_preferred = sorted(student_skills & preferred_skills)

    # Required skills contribute 80%; preferred skills contribute 20%.
    required_score = (
        len(matched_required) / len(required_skills) * 80
        if required_skills else 80
    )

    preferred_score = (
        len(matched_preferred) / len(preferred_skills) * 20
        if preferred_skills else 0
    )

    match_score = round(required_score + preferred_score, 2)

    if match_score >= 75:
        status = "Strong Match"
    elif match_score >= 50:
        status = "Partial Match"
    else:
        status = "Skill Gap Detected"

    return {
        "student_id": student.get("id"),
        "opportunity_id": opportunity.get("id"),
        "opportunity_title": opportunity.get("title"),
        "match_score": match_score,
        "status": status,
        "matched_skills": matched_required + matched_preferred,
        "missing_skills": missing_skills
    }

def get_recommendations(student, opportunities):
    results = []

    for opportunity in opportunities:
        result = match_student_to_opportunity(student, opportunity)
        results.append(result)

    return sorted(results, key=lambda item: item["match_score"], reverse=True)

import json


def match_student_to_opportunity(student, opportunity):
    student_skills = {
        skill.strip().lower()
        for skill in student.get("skills", [])
    }

    required_skills = {
        skill.strip().lower()
        for skill in opportunity.get("required_skills", [])
    }

    preferred_skills = {
        skill.strip().lower()
        for skill in opportunity.get("preferred_skills", [])
    }

    matched_required = sorted(student_skills & required_skills)
    missing_skills = sorted(required_skills - student_skills)
    matched_preferred = sorted(student_skills & preferred_skills)

    required_score = (
        len(matched_required) / len(required_skills) * 80
        if required_skills else 80
    )

    preferred_score = (
        len(matched_preferred) / len(preferred_skills) * 20
        if preferred_skills else 0
    )

    match_score = round(required_score + preferred_score, 2)

    return {
        "opportunity": opportunity["title"],
        "match_score": match_score,
        "matched_skills": matched_required + matched_preferred,
        "missing_skills": missing_skills
    }


def get_recommendations(student, opportunities):
    results = []

    for opportunity in opportunities:
        results.append(match_student_to_opportunity(student, opportunity))

    return sorted(results, key=lambda item: item["match_score"], reverse=True)


with open("test.json", "r") as file:
    data = json.load(file)

recommendations = get_recommendations(
    data["student"],
    data["opportunities"]
)

for result in recommendations:
    print(result)
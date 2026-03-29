from services.gemini_service import get_gemini_client


def get_roles_from_resume(resume_text, api_key):
    resume_text = resume_text[:6000]
    client = get_gemini_client(api_key)

    allowed_roles = [
        "Backend Developer",
        "Frontend Developer",
        "HR Round",
        "System Design",
        "Data Analyst"
    ]

    prompt = f"""
Analyze this resume and return all suitable roles from the list below.

Allowed roles:
- Backend Developer
- Frontend Developer
- HR Round
- System Design
- Data Analyst

Resume:
{resume_text}

Rules:
- Return only matching roles
- Return only role names
- Separate them with commas
- Do not write explanations
- Do not write any extra text

Example output:
Backend Developer, Frontend Developer, HR Round
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "max_output_tokens": 200,
            "temperature": 0.1,
        }
    )

    result = response.text.strip()
    print("ROLE LIST RESPONSE:", result)

    detected_roles = []
    for role in allowed_roles:
        if role.lower() in result.lower():
            detected_roles.append(role)

    if not detected_roles:
        detected_roles = ["Backend Developer"]

    best_role = detected_roles[0]

    reason_map = {
        "Backend Developer": "Resume shows API, Flask, database, or server-side development exposure.",
        "Frontend Developer": "Resume shows UI, HTML, CSS, JavaScript, React, or frontend project work.",
        "HR Round": "Resume reflects communication, teamwork, leadership, or presentation skills.",
        "System Design": "Resume includes architecture, scalability, database design, or system-level concepts.",
        "Data Analyst": "Resume includes SQL, Pandas, NumPy, analytics, visualization, or insight generation."
    }

    suggested_roles = []
    base_score = 90

    for i, role in enumerate(detected_roles):
        score = max(base_score - i * 8, 55)
        suggested_roles.append({
            "role": role,
            "reason": reason_map.get(role, "Relevant based on resume content."),
            "fit_score": score
        })

    return best_role, suggested_roles
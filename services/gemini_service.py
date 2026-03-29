from google import genai


# Create Gemini client safely
def get_gemini_client(api_key):
    print("Client using key:", api_key[:10] if api_key else "No key")
    return genai.Client(api_key=api_key)


# 🔥 Role-specific behavior rules
ROLE_PROMPTS = {

    "Backend Developer": """
You are a strict BACKEND technical interviewer.

Focus Areas:
- APIs, databases, authentication
- Scalability, concurrency, caching
- Clean architecture
Avoid frontend/UI questions.
""",

    "Frontend Developer": """
You are a strict FRONTEND technical interviewer.

Focus Areas:
- JavaScript fundamentals
- React, state management
- Performance optimization
- Browser rendering behavior
Avoid backend and database architecture questions.
""",

    "HR Round": """
You are an HR interviewer.

Focus Areas:
- Communication skills
- Teamwork & leadership
- Conflict resolution
- Motivation & culture fit
Avoid technical questions.
""",

    "System Design": """
You are a senior SYSTEM DESIGN interviewer.

Focus Areas:
- Distributed systems
- Scalability & load balancing
- Caching & consistency
- Microservices architecture
Avoid syntax-level coding questions.
""",

    "Data Analyst": """
You are a DATA ANALYST interviewer.

Focus Areas:
- SQL queries
- Data cleaning
- Statistics fundamentals
- Business insights from data
Avoid frontend/backend architecture questions.
"""
}


# 🔥 Difficulty rules based on level
def get_difficulty_instruction(level):

    if level <= 1:
        return "Ask beginner-level but slightly practical questions."
    elif level == 2:
        return "Ask intermediate conceptual and practical questions."
    elif level == 3:
        return "Ask practical implementation-based questions."
    elif level == 4:
        return "Ask advanced real-world problem-solving questions."
    else:
        return "Ask expert-level, deep architecture or optimization questions."


def evaluate_answer(role, question, answer, level, api_key, skip_evaluation=False, context=""):

    client = get_gemini_client(api_key)

    role_instruction = ROLE_PROMPTS.get(
        role,
        "You are a technical interviewer."
    )

    difficulty_instruction = get_difficulty_instruction(level)

    # 🔥 If first question → Skip scoring
    if skip_evaluation:
        prompt = f"""
{role_instruction}

Candidate Level: {level}
Difficulty Rule: {difficulty_instruction}

Previous Interview Conversation:
{context}

Candidate just answered an introduction question.

Now:
Ask the next interview question strictly according to role and level.

FORMAT:

Next Question: <next question>
"""

    else:
        prompt = f"""
{role_instruction}

Candidate Level: {level}
Difficulty Rule: {difficulty_instruction}

Previous Interview Conversation:
{context}

Current Question:
{question}

Candidate Answer:
{answer}

Your Tasks:
1. Evaluate the answer strictly.
2. Give a score between 0 and 10.
3. Provide constructive feedback.
4. Ask the next question strictly according to role and level.

FORMAT:

Score: <number>/10
Feedback: <detailed feedback>
Next Question: <next question>
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "max_output_tokens": 1000,
            "temperature": 0.6,
        }
    )

    return response.text


def generate_interview_feedback(role, level, context, api_key, emotion_summary=None):
    client = get_gemini_client(api_key)

    role_instruction = ROLE_PROMPTS.get(
        role,
        "You are a professional interviewer."
    )

    difficulty_instruction = get_difficulty_instruction(level)

    emotion_summary_text = ""
    if emotion_summary:
        emotion_summary_text = f"""
Supportive non-verbal interview behavior summary:
- Overall dominant emotion: {emotion_summary.get('overall_dominant_emotion', 'Unknown')}
- Overall dominant state: {emotion_summary.get('overall_dominant_state', 'Unknown')}
- Average confidence: {emotion_summary.get('average_confidence', 0)}%
- Overall eye contact: {emotion_summary.get('overall_eye_contact', 'Unknown')}
- Nervous question count: {emotion_summary.get('nervous_question_count', 0)}
- Total emotion samples captured: {emotion_summary.get('total_samples', 0)}

IMPORTANT BEHAVIOR RULES:
- Use this only as supportive interview behavior analysis.
- Do NOT treat this as medical, psychological, or clinical diagnosis.
- Do NOT overstate nervousness or confidence.
"""

    prompt = f"""
{role_instruction}

Candidate Level: {level}
Difficulty Rule: {difficulty_instruction}

Full Interview Conversation:
{context}

{emotion_summary_text}

Your task:
Analyze the candidate's complete interview performance based on all questions and answers.

Instructions:
- Main evaluation must still be based on answer quality, clarity, relevance, technical correctness, and communication quality.
- You MUST use the behavior summary in the final response.
- Strengths must mention specific good areas from the actual interview, not generic praise.
- Weaknesses must mention specific weak areas from the actual interview, not generic criticism.
- Improvement Plan must be truly personalized and should mention exact things the candidate should improve next.
- Do NOT write generic advice like "practice more mock interviews", "revise core concepts", or "improve answer structure" unless you also mention the exact topic or weak area.
- Emotion Correlation must connect behavior with interview performance in a meaningful way.
- Do NOT write generic lines like "No strong emotion-performance pattern was detected" unless the data is completely flat and no useful observation can be made.
- If confidence was moderate or low, mention how that may have affected delivery.
- If the candidate remained focused or calm, mention whether that supported answer quality.
- Next Round Focus must mention 2 to 4 specific topics or interview skills to practice next.
- Do NOT write generic phrases like "cover weak concepts" or "balanced practice round".
- If the self-introduction was weak, mention self-introduction or answer framing explicitly.
- If the candidate was good in one area but weak in another, use that contrast in the guidance.
- Keep the tone professional, realistic, constructive, and not harsh.

IMPORTANT:
Follow this format STRICTLY.
Each field must be exactly one line.
Do NOT skip any field.
Do NOT merge fields.

Strengths: one line only, must include at least one direct observation from the interview behavior summary if available
Weaknesses: one line only, must include at least one direct observation from the interview behavior summary if available
Overall Feedback: one line only, must include at least one direct observation from the interview behavior summary if available
Improvement Plan: one line only, must include at least one direct observation from the interview behavior summary if available
Emotion Correlation: one line only, must include at least one direct observation from the interview behavior summary if available
Next Round Focus: one line only, must include at least one direct observation from the interview behavior summary if available
Readiness Summary: one line only, must include at least one direct observation from the interview behavior summary if available

FORMAT:

Strengths: <specific strengths from the interview>
Weaknesses: <specific weaknesses from the interview>
Overall Feedback: <clear final evaluation>
Improvement Plan: <personalized plan with exact weak areas/topics to improve>
Emotion Correlation: <specific relation between confidence/focus/nervousness/eye contact and answer quality>
Next Round Focus: <2 to 4 specific topics or interview skills to practice next>
Readiness Summary: <short readiness interpretation based on interview and behavior>
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "max_output_tokens": 1200,
                "temperature": 0.5,
            }
        )
        return response.text
    except Exception as e:
        print("Gemini generate_interview_feedback failed:", e)
        return ""
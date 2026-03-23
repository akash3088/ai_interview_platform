from google import genai


# Create Gemini client safely
def get_gemini_client(api_key):
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



def generate_interview_feedback(role, level, context, api_key):
    client = get_gemini_client(api_key)

    role_instruction = ROLE_PROMPTS.get(
        role,
        "You are a professional interviewer."
    )

    difficulty_instruction = get_difficulty_instruction(level)

    prompt = f"""
{role_instruction}

Candidate Level: {level}
Difficulty Rule: {difficulty_instruction}

Full Interview Conversation:
{context}

Your task:
Analyze the candidate's complete interview performance based on all questions and answers.

IMPORTANT:
Follow this format STRICTLY. Do NOT skip colon.

Strengths: one line only
Weaknesses: one line only
Overall Feedback: one line only

Keep the feedback professional, constructive, and short-to-medium length.

FORMAT:

Strengths: <candidate strengths>
Weaknesses: <candidate weaknesses>
Overall Feedback: <overall final feedback>
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
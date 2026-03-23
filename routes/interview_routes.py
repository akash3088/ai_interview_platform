from flask import Blueprint, render_template, request, session, redirect, url_for, current_app
from services.gemini_service import evaluate_answer, generate_interview_feedback
from models.db import get_db_connection
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from services.conversation_manager import ConversationManager
import random

interview_bp = Blueprint('interview', __name__)

MAX_QUESTIONS = 4

FALLBACK_QUESTIONS = {
    "Backend Developer": [
        "How does authentication and authorization work in modern web applications?",
        "What are microservices and how do they differ from monolithic architecture?",
        "What is the difference between SQL and NoSQL?",
        "Explain dependency injection."
    ],

    "Frontend Developer": [
        "What is the difference between HTML, CSS and JavaScript?",
        "How does the browser render HTML, CSS, and JavaScript into a webpage?",
        "What is the role of CSS in designing responsive and user-friendly layouts?",
        "What is the difference between var, let and const?"
    ],

    "Data Analyst": [
        "What is the difference between supervised and unsupervised learning?",
        "What is data cleaning?",
        "Explain correlation vs causation.",
        "How do you handle missing values in a dataset effectively?"
    ],

    "HR Round": [
        "Tell me about your strengths.",
        "Describe a challenge you faced in a project.",
        "Where do you see yourself in 5 years?",
        "Why do you want to work with our company specifically?"
    ],

    "System Design":[
        "How would you design a scalable URL shortening service like Bitly?",
        "How would you design a real-time chat application like WhatsApp?",
        "How would you design a ride-sharing system similar to Uber or Ola?",
        "How would you design an API rate limiter for handling high traffic requests?"
    ]
}

@interview_bp.route("/interview", methods=["GET", "POST"])
def interview():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if "role" not in session:
        return "Please select a role from dashboard first."

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    # FIRST TIME START
    if request.method == "GET":

        cursor.execute("SELECT credits FROM users WHERE id=%s", (session["user_id"],))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            return "User not found."

        if user["credits"] <= 0:
            cursor.close()
            conn.close()
            return "No credits remaining."

        # Deduct 1 credit only when a fresh interview starts
        cursor.execute(
            "UPDATE users SET credits = credits - 1 WHERE id=%s",
            (session["user_id"],)
        )
        conn.commit()

        session["question_count"] = 1
        session["total_score"] = 0
        session["used_fallback_questions"] = []

        # Initialize conversation manager
        manager = ConversationManager(role=session["role"], level=1)
        session["manager"] = manager.__dict__

        question = "Tell me about yourself."

        cursor.close()
        conn.close()

        return render_template("interview.html", question=question)

    # POST — Answer Submitted
    answer = request.form["answer"]
    question = request.form["question"]
    role = session["role"]

    # Recreate conversation manager from session
    manager_data = session.get("manager")
    if not manager_data:
        cursor.close()
        conn.close()
        return redirect(url_for("interview.interview"))

    manager = ConversationManager(
        role=manager_data["role"],
        level=manager_data["level"]
    )

    manager.question_history = manager_data["question_history"]
    manager.answer_history = manager_data["answer_history"]

    # Add current interaction
    manager.add_interaction(question, answer)

    # Generate context for Gemini
    context = manager.get_context()

    # Save updated manager
    session["manager"] = manager.__dict__

    cursor.execute(
        "SELECT level FROM users WHERE id=%s",
        (session["user_id"],)
    )
    user_data = cursor.fetchone()
    level = user_data["level"] if user_data and "level" in user_data else 1

    api_key = current_app.config["GEMINI_API_KEY"]

    # FIRST QUESTION
    if session["question_count"] == 1:

        manual_score = 5
        session["total_score"] += manual_score
        session["question_count"] += 1

        try:
            with ThreadPoolExecutor() as executor:
                future = executor.submit(
                    evaluate_answer, role, question, answer, level, api_key, True, context
                )
                ai_response = future.result(timeout=20)

        except TimeoutError:
            ai_response = ""

    else:

        try:
            with ThreadPoolExecutor() as executor:
                future = executor.submit(
                    evaluate_answer, role, question, answer, level, api_key, False, context
                )
                ai_response = future.result(timeout=20)

        except TimeoutError:
            ai_response = ""

        try:
            score_line = [line for line in ai_response.split("\n") if "Score" in line][0]
            score = float(score_line.split(":")[1].strip().split("/")[0])
        except:
            score = 5

        session["total_score"] += score
        session["question_count"] += 1

    # Interview Finished
    if session["question_count"] > MAX_QUESTIONS:

        average_score = session["total_score"] / MAX_QUESTIONS

        final_context = manager.get_context()

        try:
            with ThreadPoolExecutor() as executor:
                future = executor.submit(
                    generate_interview_feedback,
                    role,
                    level,
                    final_context,
                    api_key
                )
                feedback_response = future.result(timeout=20)
        except TimeoutError:
            feedback_response = ""

        strengths = "Good effort shown during the interview."
        weaknesses = "Some answers need more clarity and depth."
        overall_feedback = "Keep practicing to improve confidence, structure, and technical precision."

        if feedback_response:
            for line in feedback_response.split("\n"):
                line = line.strip()

                if line.lower().startswith("strengths:"):
                    strengths = line.split(":", 1)[1].strip()

                elif line.lower().startswith("weaknesses:"):
                    weaknesses = line.split(":", 1)[1].strip()

                elif line.lower().startswith("overall feedback:"):
                    overall_feedback = line.split(":", 1)[1].strip()

        cursor.execute(
            "INSERT INTO interviews (user_id, role, total_score) VALUES (%s, %s, %s)",
            (session["user_id"], role, average_score)
        )

        cursor.execute("""
            UPDATE user_roles
            SET total_score = total_score + %s
            WHERE user_id=%s AND role_name=%s
        """, (average_score, session["user_id"], role))

        cursor.execute("""
            SELECT total_score FROM user_roles
            WHERE user_id=%s AND role_name=%s
        """, (session["user_id"], role))

        updated_role = cursor.fetchone()
        new_total = updated_role["total_score"]

        if new_total > 200:
            level = 5
        elif new_total > 100:
            level = 4
        elif new_total > 50:
            level = 3
        elif new_total > 20:
            level = 2
        else:
            level = 1

        cursor.execute("""
            UPDATE user_roles
            SET level=%s
            WHERE user_id=%s AND role_name=%s
        """, (level, session["user_id"], role))

        # ---------------- CREDIT REWARD SYSTEM ----------------
        reward_credits = 2
        bonus_credit = 0

        if average_score >= 8:
            bonus_credit = 1
            reward_credits += 1

        cursor.execute(
            "UPDATE users SET credits = credits + %s WHERE id=%s",
            (reward_credits, session["user_id"])
        )
        # ------------------------------------------------------

        conn.commit()

        session.pop("question_count", None)
        session.pop("total_score", None)
        session.pop("used_fallback_questions", None)
        session.pop("manager", None)

        cursor.close()
        conn.close()

        return render_template(
            "summary.html",
            average_score=average_score,
            reward_credits=reward_credits,
            bonus_credit=bonus_credit,
            strengths=strengths,
            weaknesses=weaknesses,
            overall_feedback=overall_feedback
        )

    next_question = None

    for line in ai_response.split("\n"):
        line = line.strip()

        if "next question" in line.lower():
            parts = line.split(":", 1)

            if len(parts) > 1:
                q = parts[1].strip()

                if q.lower() != "n/a" and q != "":
                    next_question = q
            break

    # FALLBACK if Gemini failed or delayed
    if not next_question:

        role_questions = FALLBACK_QUESTIONS.get(role, [])

        used_questions = session.get("used_fallback_questions", [])

        remaining_questions = [q for q in role_questions if q not in used_questions]

        if remaining_questions:
            next_question = random.choice(remaining_questions)
            used_questions.append(next_question)
            session["used_fallback_questions"] = used_questions
        else:
            next_question = "Describe a technical challenge you solved."

    manager_data = session.get("manager")
    previous_questions = manager_data["question_history"]

    if next_question in previous_questions:
        next_question = "Can you describe a technical challenge you solved?"

    cursor.close()
    conn.close()

    return render_template("interview.html", question=next_question)
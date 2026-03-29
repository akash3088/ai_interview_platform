from flask import Blueprint, render_template, request, session, redirect, url_for, current_app
from services.gemini_service import evaluate_answer, generate_interview_feedback
from models.progress_model import get_db_connection
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from services.conversation_manager import ConversationManager
from collections import Counter
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


def build_overall_emotion_summary(emotion_history):
    if not emotion_history:
        return {
            "overall_dominant_emotion": "Unknown",
            "overall_dominant_state": "Unknown",
            "average_confidence": 0,
            "overall_eye_contact": "Unknown",
            "nervous_question_count": 0,
            "total_samples": 0
        }

    emotions = [item.get("dominant_emotion", "Unknown") for item in emotion_history]
    states = [item.get("dominant_state", "Unknown") for item in emotion_history]
    eye_contacts = [item.get("eye_contact_summary", "Unknown") for item in emotion_history]
    confidences = [int(item.get("avg_confidence", 0)) for item in emotion_history]
    sample_counts = [int(item.get("samples_count", 0)) for item in emotion_history]

    nervous_question_count = sum(
        1 for item in emotion_history
        if item.get("dominant_state") in ["Slightly Nervous", "Nervous"]
    )

    return {
        "overall_dominant_emotion": Counter(emotions).most_common(1)[0][0],
        "overall_dominant_state": Counter(states).most_common(1)[0][0],
        "average_confidence": round(sum(confidences) / len(confidences)) if confidences else 0,
        "overall_eye_contact": Counter(eye_contacts).most_common(1)[0][0],
        "nervous_question_count": nervous_question_count,
        "total_samples": sum(sample_counts)
    }


def get_aptitude_summary_from_session():
    aptitude_score = session.get("aptitude_score", 0)
    aptitude_total = session.get("aptitude_total", 5)

    try:
        aptitude_score = int(aptitude_score)
    except:
        aptitude_score = 0

    try:
        aptitude_total = int(aptitude_total)
    except:
        aptitude_total = 5

    if aptitude_total <= 0:
        aptitude_total = 5

    return aptitude_score, aptitude_total


def calculate_readiness_score(average_score, aptitude_score, aptitude_total, average_confidence):
    interview_component = (average_score / 10) * 60
    aptitude_component = (aptitude_score / aptitude_total) * 25 if aptitude_total else 0
    confidence_component = (average_confidence / 100) * 15

    readiness_score = round(interview_component + aptitude_component + confidence_component)

    if readiness_score < 0:
        readiness_score = 0
    if readiness_score > 100:
        readiness_score = 100

    return readiness_score


def get_hiring_decision(readiness_score):
    if readiness_score >= 80:
        return {
            "hire_probability": readiness_score,
            "decision_label": "Recommended",
            "decision_note": "Strong overall readiness for interview performance."
        }
    elif readiness_score >= 65:
        return {
            "hire_probability": readiness_score,
            "decision_label": "Consider with Improvement",
            "decision_note": "Promising candidate, but a few areas need improvement."
        }
    elif readiness_score >= 50:
        return {
            "hire_probability": readiness_score,
            "decision_label": "Borderline",
            "decision_note": "Basic potential is visible, but more preparation is required."
        }
    else:
        return {
            "hire_probability": readiness_score,
            "decision_label": "Not Recommended Yet",
            "decision_note": "Candidate needs more preparation before a strong recommendation."
        }


@interview_bp.route("/interview", methods=["GET", "POST"])
def interview():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if "role" not in session:
        return "Please select a role from dashboard first."
    
    if session.get("selection_mode") == "resume" and not session.get("aptitude_cleared", False):
        return redirect(url_for("aptitude.aptitude_test"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

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
        session["emotion_history"] = []

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

    # Emotion data from frontend
    dominant_emotion = request.form.get("dominant_emotion", "Unknown").strip()
    dominant_state = request.form.get("dominant_state", "Unknown").strip()
    avg_confidence = request.form.get("avg_confidence", "0").strip()
    eye_contact_summary = request.form.get("eye_contact_summary", "Unknown").strip()
    emotion_samples_count = request.form.get("emotion_samples_count", "0").strip()

    try:
        avg_confidence = int(avg_confidence)
    except ValueError:
        avg_confidence = 0

    try:
        emotion_samples_count = int(emotion_samples_count)
    except ValueError:
        emotion_samples_count = 0

    # Save emotion entry for this answer
    emotion_entry = {
        "question": question,
        "dominant_emotion": dominant_emotion,
        "dominant_state": dominant_state,
        "avg_confidence": avg_confidence,
        "eye_contact_summary": eye_contact_summary,
        "samples_count": emotion_samples_count
    }

    if "emotion_history" not in session:
        session["emotion_history"] = []

    emotion_history = session["emotion_history"]
    emotion_history.append(emotion_entry)
    session["emotion_history"] = emotion_history
    session.modified = True

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

        emotion_history = session.get("emotion_history", [])
        overall_emotion_summary = build_overall_emotion_summary(emotion_history)
        aptitude_score, aptitude_total = get_aptitude_summary_from_session()

        readiness_score = calculate_readiness_score(
            average_score=average_score,
            aptitude_score=aptitude_score,
            aptitude_total=aptitude_total,
            average_confidence=overall_emotion_summary.get("average_confidence", 0)
        )

        hiring_decision = get_hiring_decision(readiness_score)

        try:
            with ThreadPoolExecutor() as executor:
                future = executor.submit(
                    generate_interview_feedback,
                    role,
                    level,
                    final_context,
                    api_key,
                    overall_emotion_summary
                )
                feedback_response = future.result(timeout=20)
        except TimeoutError:
            feedback_response = ""

        strengths = "Good effort shown during the interview."
        weaknesses = "Some answers need more clarity and depth."
        overall_feedback = "Keep practicing to improve confidence, structure, and technical precision."
        improvement_plan = "Revise core concepts, practice more mock interviews, and improve answer structure."
        emotion_correlation = "No strong emotion-performance pattern was detected."
        next_round_focus = "Continue with a balanced practice round covering weak concepts."
        readiness_summary = "The candidate shows developing interview readiness with scope for further improvement."

        if feedback_response:
            for line in feedback_response.split("\n"):
                line = line.strip()

                if line.lower().startswith("strengths:"):
                    strengths = line.split(":", 1)[1].strip()

                elif line.lower().startswith("weaknesses:"):
                    weaknesses = line.split(":", 1)[1].strip()

                elif line.lower().startswith("overall feedback:"):
                    overall_feedback = line.split(":", 1)[1].strip()

                elif line.lower().startswith("improvement plan:"):
                    improvement_plan = line.split(":", 1)[1].strip()

                elif line.lower().startswith("emotion correlation:"):
                    emotion_correlation = line.split(":", 1)[1].strip()

                elif line.lower().startswith("next round focus:"):
                    next_round_focus = line.split(":", 1)[1].strip()

                elif line.lower().startswith("readiness summary:"):
                    readiness_summary = line.split(":", 1)[1].strip()

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

        # CREDIT REWARD SYSTEM
        reward_credits = 2
        bonus_credit = 0

        if average_score >= 8:
            bonus_credit = 1
            reward_credits += 1

        cursor.execute(
            "UPDATE users SET credits = credits + %s WHERE id=%s",
            (reward_credits, session["user_id"])
        )

        conn.commit()

        session.pop("question_count", None)
        session.pop("total_score", None)
        session.pop("used_fallback_questions", None)
        session.pop("manager", None)
        session.pop("emotion_history", None)
        session.pop("aptitude_score", None)
        session.pop("aptitude_total", None)

        cursor.close()
        conn.close()

        return render_template(
            "summary.html",
            average_score=average_score,
            reward_credits=reward_credits,
            bonus_credit=bonus_credit,
            strengths=strengths,
            weaknesses=weaknesses,
            overall_feedback=overall_feedback,
            improvement_plan=improvement_plan,
            emotion_correlation=emotion_correlation,
            next_round_focus=next_round_focus,
            readiness_summary=readiness_summary,
            readiness_score=readiness_score,
            hire_probability=hiring_decision["hire_probability"],
            decision_label=hiring_decision["decision_label"],
            decision_note=hiring_decision["decision_note"],
            aptitude_score=aptitude_score,
            aptitude_total=aptitude_total,
            role=role,
            emotion_summary=overall_emotion_summary
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
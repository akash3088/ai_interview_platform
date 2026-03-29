from flask import Blueprint, render_template, request, session, redirect, url_for, flash

aptitude_bp = Blueprint("aptitude", __name__)

APTITUDE_QUESTIONS = [
    {
        "question": "If all APIs are interfaces and some interfaces are secure, what can be concluded?",
        "options": [
            "All APIs are secure",
            "Some APIs may be secure",
            "No APIs are secure",
            "All secure items are APIs"
        ],
        "answer": "Some APIs may be secure"
    },
    {
        "question": "Which number comes next: 2, 6, 12, 20, 30, ?",
        "options": ["36", "40", "42", "44"],
        "answer": "42"
    },
    {
        "question": "Which is most important in an interview setting?",
        "options": [
            "Memorizing long answers only",
            "Clear communication and understanding",
            "Speaking very fast",
            "Using difficult words always"
        ],
        "answer": "Clear communication and understanding"
    },
    {
        "question": "A system is slow under heavy traffic. What is the best first step?",
        "options": [
            "Ignore it",
            "Measure bottlenecks",
            "Delete the database",
            "Rewrite everything"
        ],
        "answer": "Measure bottlenecks"
    },
    {
        "question": "If confidence increases performance and practice increases confidence, what helps performance?",
        "options": [
            "Practice",
            "Confusion",
            "Silence",
            "Delay"
        ],
        "answer": "Practice"
    }
]


@aptitude_bp.route("/aptitude-test", methods=["GET", "POST"])
def aptitude_test():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("selection_mode") != "resume" or "role" not in session:
        flash("Please select a resume-suggested role first.")
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        score = 0

        for i, q in enumerate(APTITUDE_QUESTIONS):
            selected = request.form.get(f"q{i}")
            if selected == q["answer"]:
                score += 1

        total_questions = len(APTITUDE_QUESTIONS)

        session["aptitude_score"] = score
        session["aptitude_total"] = total_questions

        passed = score >= int(0.6 * total_questions)
        session["aptitude_cleared"] = passed

        if passed:
            flash(
                f"Aptitude test cleared. Score: {score}/{total_questions}. You can now start the interview."
            )
            return redirect(url_for("interview.interview"))
        else:
            flash(
                f"You did not clear the aptitude test. Score: {score}/{total_questions}. Please try again."
            )
            return redirect(url_for("aptitude.aptitude_test"))

    return render_template(
        "aptitude_test.html",
        questions=APTITUDE_QUESTIONS,
        selected_role=session.get("role")
    )
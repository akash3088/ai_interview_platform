from flask import Blueprint, render_template, session, redirect, url_for, request, flash, current_app
from models.progress_model import get_db_connection
from services.resume_service import extract_resume_text
from services.resume_ai_service import get_roles_from_resume

dashboard_bp = Blueprint('dashboard', __name__)


def get_dashboard_context(suggested_role=None, suggested_roles=None, active_mode="manual"):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT username, credits FROM users WHERE id=%s",
        (session["user_id"],)
    )
    user = cursor.fetchone()

    selected_role = session.get("role")
    role_data = None

    if selected_role:
        cursor.execute("""
            SELECT level, total_score
            FROM user_roles
            WHERE user_id=%s AND role_name=%s
        """, (session["user_id"], selected_role))
        role_data = cursor.fetchone()

    cursor.close()
    conn.close()

    return {
        "user": user,
        "role": selected_role,
        "role_data": role_data,
        "suggested_role": suggested_role,
        "suggested_roles": suggested_roles or [],
        "active_mode": active_mode
    }


@dashboard_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    active_mode = session.get("selection_mode", "manual")

    # 🔥 Load resume data ONLY if resume mode is active
    if active_mode == "resume":
        suggested_role = session.get("resume_best_role")
        suggested_roles = session.get("resume_suggested_roles_full", [])
    else:
        suggested_role = None
        suggested_roles = []

    context = get_dashboard_context(
        suggested_role=suggested_role,
        suggested_roles=suggested_roles,
        active_mode=active_mode
    )

    return render_template("dashboard.html", **context)


@dashboard_bp.route("/set-role", methods=["POST"])
def set_role():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    selected_role = request.form["role"]

    session["role"] = selected_role
    session["selection_mode"] = "manual"
    session["aptitude_cleared"] = True
    session.pop("resume_suggested_roles", None)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT IGNORE INTO user_roles (user_id, role_name)
        VALUES (%s, %s)
    """, (session["user_id"], selected_role))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/add-credits")
def add_credits():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET credits = credits + 5 WHERE id=%s",
        (session["user_id"],)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/analyze-resume", methods=["POST"])
def analyze_resume():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    uploaded_file = request.files.get("resume")

    if not uploaded_file or uploaded_file.filename == "":
        flash("Please upload a resume file first.")
        return redirect(url_for("dashboard.dashboard"))

    try:
        resume_text = extract_resume_text(uploaded_file)

        if not resume_text.strip():
            flash("Could not read any content from the uploaded resume.")
            return redirect(url_for("dashboard.dashboard"))

        api_key = current_app.config.get("GEMINI_API_KEY")
        best_role, suggested_roles = get_roles_from_resume(resume_text, api_key)

        session["resume_suggested_roles"] = [item["role"] for item in suggested_roles if "role" in item]
        session["resume_suggested_roles_full"] = suggested_roles
        session["resume_best_role"] = best_role
        session["selection_mode"] = "resume"
        session["aptitude_cleared"] = False

    except Exception as e:
        flash(f"Resume analysis failed: {str(e)}")
        return redirect(url_for("dashboard.dashboard"))

    context = get_dashboard_context(
        suggested_role=best_role,
        suggested_roles=suggested_roles,
        active_mode="resume"
    )
    return render_template("dashboard.html", **context)


@dashboard_bp.route("/select-resume-role", methods=["POST"])
def select_resume_role():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    selected_role = request.form.get("resume_selected_role", "").strip()
    allowed_roles = session.get("resume_suggested_roles", [])

    if not selected_role:
        flash("Please select one suggested role first.")
        return redirect(url_for("dashboard.dashboard"))

    if selected_role not in allowed_roles:
        flash("Selected role is not from the analyzed resume suggestions.")
        return redirect(url_for("dashboard.dashboard"))

    session["role"] = selected_role
    session["selection_mode"] = "resume"
    session["aptitude_cleared"] = False

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT IGNORE INTO user_roles (user_id, role_name)
        VALUES (%s, %s)
    """, (session["user_id"], selected_role))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("aptitude.aptitude_test"))
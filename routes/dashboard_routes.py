from flask import Blueprint, render_template, session, redirect, url_for, request
from models.db import get_db_connection

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user basic info
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

    return render_template(
        "dashboard.html",
        user=user,
        role=selected_role,
        role_data=role_data
    )



@dashboard_bp.route("/set-role", methods=["POST"])
def set_role():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    selected_role = request.form["role"]
    session["role"] = selected_role

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create role entry if not exists
    cursor.execute("""
        INSERT IGNORE INTO user_roles (user_id, role_name)
        VALUES (%s, %s)
    """, (session["user_id"], selected_role))

    conn.commit()

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

    return redirect(url_for("dashboard.dashboard"))

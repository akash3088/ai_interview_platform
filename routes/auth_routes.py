from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from models.user_model import create_user, get_user_by_email, verify_password
from datetime import date
from models.progress_model import get_db_connection

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        role = request.form.get("role")
        
        if not role:
            role = None

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.login", panel="signup"))

        existing_user = get_user_by_email(email)
        if existing_user:
            flash("Email already used. Please use another email.", "danger")
            return redirect(url_for("auth.login", panel="signup"))

        try:
            create_user(username, email, password, role)
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("auth.login", panel="login"))

        except Exception as e:
            print("REGISTER ERROR:", e)
            flash("Unexpected error occurred.", "danger")
            return redirect(url_for("auth.login", panel="signup"))

    return redirect(url_for("auth.login", panel="signup"))




@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = get_user_by_email(email)

        if user and verify_password(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            today = date.today()

            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                "SELECT last_login_credit_date FROM users WHERE id = %s",
                (user["id"],)
            )
            db_user = cursor.fetchone()

            if db_user["last_login_credit_date"] != today:
                cursor.execute(
                    """
                    UPDATE users
                    SET credits = credits + 3,
                        last_login_credit_date = %s
                    WHERE id = %s
                    """,
                    (today, user["id"])
                )
                conn.commit()

            cursor.close()
            conn.close()

            return redirect(url_for("dashboard.dashboard"))

        flash("Invalid credentials.", "danger")
        return redirect(url_for("auth.login", panel="login"))

    active_panel = request.args.get("panel", "login")
    return render_template("login.html", active_panel=active_panel)

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

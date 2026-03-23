from werkzeug.security import generate_password_hash, check_password_hash
from models.db import get_db_connection


def create_user(username, email, password, role):
    conn = get_db_connection()
    cursor = conn.cursor()

    hashed_password = generate_password_hash(password)

    query = """
        INSERT INTO users (username, email, password, role)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (username, email, hashed_password, role))
    conn.commit()

    user_id = cursor.lastrowid

    # Create default progress
    cursor.execute("INSERT INTO user_progress (user_id) VALUES (%s)", (user_id,))
    conn.commit()

    cursor.close()
    conn.close()


def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return user


def verify_password(stored_password, provided_password):
    return check_password_hash(stored_password, provided_password)

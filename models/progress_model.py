from models.db import get_db_connection


def get_user_progress(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT u.username, u.role, p.credits, p.level, p.total_interviews
        FROM users u
        JOIN user_progress p ON u.id = p.user_id
        WHERE u.id = %s
    """
    cursor.execute(query, (user_id,))
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    return data

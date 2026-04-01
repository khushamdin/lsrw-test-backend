import sqlite3

DB_NAME = "test.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        current_question INTEGER,
        answers TEXT,
        scores TEXT,
        question_indices TEXT,
        chat_history TEXT DEFAULT '[]',
        student_name TEXT,
        turn_metrics TEXT DEFAULT '[]'
    )
    """)
    # Add columns if they don't exist (for existing DBs)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN chat_history TEXT DEFAULT '[]'")
    except:
        pass # Column already exists
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN student_name TEXT")
    except:
        pass # Column already exists
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN turn_metrics TEXT DEFAULT '[]'")
    except:
        pass # Column already exists

    conn.commit()
    conn.close()




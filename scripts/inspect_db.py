import sqlite3

def inspect_db():
    try:
        conn = sqlite3.connect('diagnostic_bot.db')
        cursor = conn.cursor()
        
        print("=== Tables ===")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(table[0])
            
        print("\n=== Schema of pdp_plans ===")
        cursor.execute("PRAGMA table_info(pdp_plans);")
        columns = cursor.fetchall()
        for col in columns:
            print(col)

        print("\n=== Schema of task_reminders ===")
        cursor.execute("PRAGMA table_info(task_reminders);")
        columns = cursor.fetchall()
        for col in columns:
            print(col)

        print("\n=== Alembic Version ===")
        try:
            cursor.execute("SELECT * FROM alembic_version;")
            print(cursor.fetchall())
        except sqlite3.OperationalError:
            print("alembic_version table not found")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_db()

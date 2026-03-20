import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def create_database():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    db_name = os.getenv("MYSQL_DATABASE", "expense_tracker")

    print(f"Connecting to MySQL at {host} as {user}...")
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            port=port
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"Database '{db_name}' ensured.")
        conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")

if __name__ == "__main__":
    create_database()

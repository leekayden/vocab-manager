import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASS"],
    "host": os.environ["DB_HOST"],
    "database": os.environ["DB_NAME"],
}

def get_all_words():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT word FROM vocabulary")
    words = cursor.fetchall()
    conn.close()
    return [word[0] for word in words]

def print_words():
    words = get_all_words()
    print(" ".join(words))

print_words()

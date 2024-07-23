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

def init_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INT AUTO_INCREMENT PRIMARY KEY,
            word VARCHAR(255) NOT NULL,
            meaning TEXT NOT NULL
        )
    """
    )
    conn.close()

def fetch_words():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT id, word FROM vocabulary")
    words = cursor.fetchall()
    conn.close()
    return words

def delete_word(word_id):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vocabulary WHERE id = %s", (word_id,))
    conn.commit()
    conn.close()

def purge_duplicates():
    words = fetch_words()
    seen = set()
    duplicates = []

    for word_id, word in words:
        if word in seen:
            duplicates.append(word_id)
        else:
            seen.add(word)

    for word_id in duplicates:
        delete_word(word_id)

    print(f"Purged {len(duplicates)} duplicate words from the database.")

init_db()
purge_duplicates()

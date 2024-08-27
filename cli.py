import mysql.connector
import requests
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASS"],
    "host": os.environ["DB_HOST"],
    "database": os.environ["DB_NAME"],
}

DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


def fetch_meaning(word):
    url = f"{DICTIONARY_API_URL}{word.lower()}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data[0]["meanings"][0]["definitions"][0]["definition"]


def add_word():
    meaning = ''
    
    word = input("Enter word >_")

    if not word:
        print("Input Error - Please fill in the word field")
        return

    if not meaning:
        meaning = fetch_meaning(word)

    if not meaning:
        print("Fetch Error - Could not fetch meaning from the dictionary")
        return

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vocabulary (word, meaning) VALUES (%s, %s)", (word, meaning)
    )
    conn.commit()
    conn.close()
    
    print(meaning)

while True:
    add_word()


import tkinter as tk
from tkinter import messagebox, ttk
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


def init_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INT AUTO_INCREMENT PRIMARY KEY,
            word VARCHAR(255) NOT NULL,
            meaning TEXT NOT NULL,
            UNIQUE(word)
        )
    """)
    conn.close()


def fetch_meaning(word):
    url = f"{DICTIONARY_API_URL}{word.lower()}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data[0]["meanings"][0]["definitions"][0]["definition"]


def add_word():
    word = entry_word.get().strip()
    meaning = entry_meaning.get().strip()

    if not word:
        messagebox.showwarning("Input Error", "Please provide a word.")
        return

    if not meaning:
        meaning = fetch_meaning(word)
        if not meaning:
            messagebox.showwarning("Fetch Error", "Could not fetch meaning from the dictionary.")
            return

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO vocabulary (word, meaning) VALUES (%s, %s)", (word, meaning))
        conn.commit()
        conn.close()
        messagebox.showinfo("Success", f"'{word}' added successfully!")
        entry_word.delete(0, tk.END)
        entry_meaning.delete(0, tk.END)
        load_vocabulary()
    except mysql.connector.IntegrityError:
        messagebox.showerror("Error", "Word already exists in the database.")


def load_vocabulary(search_term=""):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    query = "SELECT word, meaning FROM vocabulary"
    if search_term:
        query += " WHERE word LIKE %s"
        cursor.execute(query, (f"%{search_term}%",))
    else:
        cursor.execute(query)
    words = cursor.fetchall()
    conn.close()

    for row in tree_vocabulary.get_children():
        tree_vocabulary.delete(row)

    for word in words:
        tree_vocabulary.insert("", "end", values=word)


def on_search():
    search_term = entry_search.get().strip()
    load_vocabulary(search_term)


def delete_word():
    selected_item = tree_vocabulary.selection()
    if not selected_item:
        messagebox.showwarning("Selection Error", "Please select a word to delete.")
        return

    word = tree_vocabulary.item(selected_item, "values")[0]
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vocabulary WHERE word = %s", (word,))
    conn.commit()
    conn.close()

    messagebox.showinfo("Success", "Word deleted successfully.")
    load_vocabulary()


# Initialize root window
root = tk.Tk()
root.title("Vocabulary Manager")
root.geometry("900x600")

# Configure theme
style = ttk.Style()
style.theme_use('clam')
style.configure("Treeview", font=("Arial", 10), rowheight=30)
style.configure("Treeview.Heading", font=("Arial", 12, "bold"))
style.configure(".", font=("Arial", 11))

# Search Frame
frame_search = ttk.Frame(root, padding=10)
frame_search.pack(fill=tk.X)

ttk.Label(frame_search, text="Search:").pack(side=tk.LEFT, padx=5)
entry_search = ttk.Entry(frame_search)
entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
ttk.Button(frame_search, text="Search", command=on_search).pack(side=tk.LEFT, padx=5)

# Vocabulary Treeview
columns = ("Word", "Meaning")
tree_vocabulary = ttk.Treeview(root, columns=columns, show="headings")
tree_vocabulary.heading("Word", text="Word")
tree_vocabulary.heading("Meaning", text="Meaning")
tree_vocabulary.column("Word", width=200, anchor="w")
tree_vocabulary.column("Meaning", width=650, anchor="w")
tree_vocabulary.pack(fill=tk.BOTH, expand=True, pady=10)

scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=tree_vocabulary.yview)
tree_vocabulary.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Input Frame
frame_input = ttk.Frame(root, padding=10)
frame_input.pack(fill=tk.X)

ttk.Label(frame_input, text="Word:").pack(side=tk.LEFT, padx=5)
entry_word = ttk.Entry(frame_input, width=30)
entry_word.pack(side=tk.LEFT, padx=5)
ttk.Label(frame_input, text="Meaning:").pack(side=tk.LEFT, padx=5)
entry_meaning = ttk.Entry(frame_input, width=50)
entry_meaning.pack(side=tk.LEFT, padx=5)

ttk.Button(frame_input, text="Add Word", command=add_word).pack(side=tk.LEFT, padx=5)
ttk.Button(frame_input, text="Delete Word", command=delete_word).pack(side=tk.LEFT, padx=5)

# Load initial vocabulary
init_db()
load_vocabulary()

# Start main loop
root.mainloop()

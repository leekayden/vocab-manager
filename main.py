import tkinter as tk
from tkinter import messagebox, ttk
import mysql.connector
import requests

DB_CONFIG = {
    "user": "root",
    "password": "",
    "host": "localhost",
    "database": "vocab_manager",
}

DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


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


def fetch_meaning(word):
    url = f"{DICTIONARY_API_URL}{word.lower()}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        meanings = data[0]["meanings"][0]["definitions"][0]["definition"]
        return meanings
    else:
        return None


def fetch_full_details(word):
    url = f"{DICTIONARY_API_URL}{word.lower()}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data[0]
    else:
        return None


def add_word():
    word = entry_word.get()
    meaning = entry_meaning.get()

    if not word:
        messagebox.showwarning("Input Error", "Please fill in the word field")
        return

    if not meaning:
        meaning = fetch_meaning(word)
        if not meaning:
            messagebox.showwarning(
                "Fetch Error", "Could not fetch meaning from the dictionary"
            )
            return

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vocabulary (word, meaning) VALUES (%s, %s)", (word, meaning)
    )
    conn.commit()
    conn.close()

    entry_word.delete(0, ttk.END)
    entry_meaning.delete(0, ttk.END)

    messagebox.showinfo("Success", "Word added successfully")
    load_vocabulary()


def update_word():
    selected_item = listbox_vocabulary.selection()
    if not selected_item:
        messagebox.showwarning("Selection Error", "Please select an item to update")
        return

    word_id = listbox_vocabulary.item(selected_item)["values"][0]
    new_word = entry_word.get()
    new_meaning = entry_meaning.get()

    if not new_word or not new_meaning:
        messagebox.showwarning("Input Error", "Please fill in both fields")
        return

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE vocabulary SET word = %s, meaning = %s WHERE id = %s",
        (new_word, new_meaning, word_id),
    )
    conn.commit()
    conn.close()

    entry_word.delete(0, ttk.END)
    entry_meaning.delete(0, ttk.END)

    messagebox.showinfo("Success", "Word updated successfully")
    load_vocabulary()


def delete_word(event=None):
    selected_item = listbox_vocabulary.selection()
    if not selected_item:
        messagebox.showwarning("Selection Error", "Please select an item to delete")
        return

    word_id = listbox_vocabulary.item(selected_item)["values"][0]

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vocabulary WHERE id = %s", (word_id,))
    conn.commit()
    conn.close()

    messagebox.showinfo("Success", "Word deleted successfully")
    load_vocabulary()


def load_vocabulary(search_term=""):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    if search_term:
        cursor.execute(
            "SELECT id, word, meaning FROM vocabulary WHERE word LIKE %s",
            ("%" + search_term + "%",),
        )
    else:
        cursor.execute("SELECT id, word, meaning FROM vocabulary")
    words = cursor.fetchall()
    conn.close()

    listbox_vocabulary.delete(*listbox_vocabulary.get_children())
    for word in words:
        listbox_vocabulary.insert("", "end", values=word)


def search_vocabulary():
    search_term = entry_search.get()
    load_vocabulary(search_term)


def resize_columns(event):
    total_width = listbox_vocabulary.winfo_width()
    listbox_vocabulary.column("ID", width=int(total_width * 0.10))
    listbox_vocabulary.column("Word", width=int(total_width * 0.20))
    listbox_vocabulary.column("Meaning", width=int(total_width * 0.70))


def show_word_details(event):
    selected_item = listbox_vocabulary.selection()
    if not selected_item:
        if paned_window.panes() and side_panel in paned_window.panes():
            paned_window.forget(side_panel)
        return

    word = listbox_vocabulary.item(selected_item)["values"][1]
    details = fetch_full_details(word)

    if not details:
        detail_label.config(text="Unknown word")
    else:
        detail_text = f"Word: {details['word']}\n\nPhonetic: {details.get('phonetic', 'N/A')}\n\nOrigin: {details.get('origin', 'N/A')}\n\nMeanings:\n"

        for meaning in details["meanings"]:
            part_of_speech = meaning.get("partOfSpeech", "N/A")
            definitions = meaning["definitions"]
            detail_text += f"\nPart of Speech: {part_of_speech}\n"
            for definition in definitions:
                detail_text += f" - {definition['definition']}\n"
                if "example" in definition:
                    detail_text += f"   Example: {definition['example']}\n"

        detail_label.config(text=detail_text)

    panel_width = int(root.winfo_width() * 0.25)

    if side_panel not in paned_window.panes():
        paned_window.add(side_panel)
    paned_window.paneconfigure(side_panel, minsize=panel_width)
    paned_window.sash_place(1, int(root.winfo_width() * 0.75), 0)


init_db()

root = tk.Tk()
root.title("Vocabulary Manager")
root.state("zoomed")

main_frame = ttk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

frame_search = ttk.Frame(main_frame)
frame_search.pack(fill=tk.X, pady=5)
lbl_search = ttk.Label(frame_search, text="Search:")
lbl_search.pack(side=tk.LEFT, padx=5)
entry_search = ttk.Entry(frame_search)
entry_search.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=5)
btn_search = ttk.Button(frame_search, text="Search", command=search_vocabulary)
btn_search.pack(side=tk.LEFT, padx=5)

paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
paned_window.pack(fill=tk.BOTH, expand=True)

frame = ttk.Frame(paned_window)
paned_window.add(frame)

columns = ("ID", "Word", "Meaning")
listbox_vocabulary = ttk.Treeview(frame, columns=columns, show="headings")
listbox_vocabulary.heading("ID", text="ID", anchor="w")
listbox_vocabulary.heading("Word", text="Word", anchor="w")
listbox_vocabulary.heading("Meaning", text="Meaning", anchor="w")
listbox_vocabulary.column("ID", anchor="w", width=int(frame.winfo_width() * 0.10))
listbox_vocabulary.column("Word", anchor="w", width=int(frame.winfo_width() * 0.20))
listbox_vocabulary.column("Meaning", anchor="w", width=int(frame.winfo_width() * 0.70))
listbox_vocabulary.pack(fill=tk.BOTH, expand=True, pady=10)

listbox_vocabulary.bind("<Delete>", delete_word)

listbox_vocabulary.bind("<<TreeviewSelect>>", show_word_details)

listbox_vocabulary.bind("<Configure>", resize_columns)

frame_add = ttk.Frame(main_frame)
frame_add.pack(fill=tk.X, pady=5)
lbl_word = ttk.Label(frame_add, text="Word:")
lbl_word.pack(side=tk.LEFT, padx=5)
entry_word = ttk.Entry(frame_add)
entry_word.pack(side=tk.LEFT, padx=5)
lbl_meaning = ttk.Label(frame_add, text="Meaning:")
lbl_meaning.pack(side=tk.LEFT, padx=5)
entry_meaning = ttk.Entry(frame_add)
entry_meaning.pack(side=tk.LEFT, padx=5)
btn_add = ttk.Button(frame_add, text="Add Word", command=add_word)
btn_add.pack(side=tk.LEFT, padx=5)
btn_update = ttk.Button(frame_add, text="Update Word", command=update_word)
btn_update.pack(side=tk.LEFT, padx=5)
btn_delete = ttk.Button(frame_add, text="Delete Word", command=delete_word)
btn_delete.pack(side=tk.LEFT, padx=5)

side_panel = ttk.Frame(paned_window)
detail_label = ttk.Label(side_panel, text="", justify=tk.LEFT, anchor="nw")
detail_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

load_vocabulary()

root.mainloop()

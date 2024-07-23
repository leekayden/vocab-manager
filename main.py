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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INT AUTO_INCREMENT PRIMARY KEY,
            word VARCHAR(255) NOT NULL,
            meaning TEXT NOT NULL,
            UNIQUE(word)
        )
    """
    )
    conn.close()

def fetch_meaning(word):
    url = f"{DICTIONARY_API_URL}{word.lower()}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data[0]["meanings"][0]["definitions"][0]["definition"]

def fetch_full_details(word):
    url = f"{DICTIONARY_API_URL}{word.lower()}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data[0]

def add_word(event=None):
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
    try:
        cursor.execute(
            "INSERT INTO vocabulary (word, meaning) VALUES (%s, %s)", (word, meaning)
        )
        conn.commit()
        messagebox.showinfo("Success", "Word added successfully")
    except mysql.connector.IntegrityError:
        messagebox.showerror("Error", "Word already exists in the database")
    conn.close()

    entry_word.delete(0, tk.END)
    entry_meaning.delete(0, tk.END)

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

    entry_word.delete(0, tk.END)
    entry_meaning.delete(0, tk.END)

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
            (f"%{search_term}%",),
        )
    else:
        cursor.execute("SELECT id, word, meaning FROM vocabulary")
    words = cursor.fetchall()
    conn.close()

    listbox_vocabulary.delete(*listbox_vocabulary.get_children())
    for word in words:
        listbox_vocabulary.insert("", "end", values=word)

def search_vocabulary(event=None):
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
        if side_panel.winfo_ismapped():
            side_panel.pack_forget()
        return

    word = listbox_vocabulary.item(selected_item)["values"][1]
    if details := fetch_full_details(word):
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
    else:
        detail_label.config(text="Unknown word")

    panel_width = int(root.winfo_width() * 0.10)  # Set to 10% of window width
    if not side_panel.winfo_ismapped():
        side_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5))

    # Update the sash position
    paned_window.sash_place(1, int(root.winfo_width() * 0.90), 0)

def close_panel(event=None):
    # Deselect any selected item
    listbox_vocabulary.selection_remove(*listbox_vocabulary.selection())
    # Hide the side panel
    if side_panel.winfo_ismapped():
        side_panel.pack_forget()

def search_dictionary():
    selected_item = listbox_vocabulary.selection()
    selected_word = ""
    if selected_item:
        selected_word = listbox_vocabulary.item(selected_item)["values"][1]
    
    search_window = tk.Toplevel(root)
    search_window.title("Search Dictionary")
    search_window.geometry("600x400")
    search_window.resizable(False, False)
    search_window.attributes("-toolwindow", True)
    search_window.protocol("WM_DELETE_WINDOW", search_window.destroy)

    lbl_search_word = ttk.Label(search_window, text="Enter Word:")
    lbl_search_word.pack(pady=10)
    entry_search_word = ttk.Entry(search_window)
    entry_search_word.pack(pady=10)
    
    if selected_word:
        entry_search_word.insert(0, selected_word)
    
    def close_window(event=None):
        search_window.destroy()

    def perform_search(event=None):
        word = entry_search_word.get()
        details = fetch_full_details(word)
        if details:
            detail_text = f"Word: {details['word']}\n\nPhonetic: {details.get('phonetic', 'N/A')}\n\nOrigin: {details.get('origin', 'N/A')}\n\nMeanings:\n"
            for meaning in details["meanings"]:
                part_of_speech = meaning.get("partOfSpeech", "N/A")
                definitions = meaning["definitions"]
                detail_text += f"\nPart of Speech: {part_of_speech}\n"
                for definition in definitions:
                    detail_text += f" - {definition['definition']}\n"
                    if "example" in definition:
                        detail_text += f"   Example: {definition['example']}\n"
        else:
            detail_text = "Unknown word"

        result_text.config(state=tk.NORMAL)
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, detail_text)
        result_text.config(state=tk.DISABLED)

    btn_search_word = ttk.Button(search_window, text="Search", command=perform_search)
    btn_search_word.pack(pady=10)

    result_frame = ttk.Frame(search_window)
    result_frame.pack(fill=tk.BOTH, expand=True)

    result_text = tk.Text(result_frame, wrap=tk.WORD, height=10)
    result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    result_text.config(state=tk.DISABLED)

    scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=result_text.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    result_text.config(yscrollcommand=scrollbar.set)

    entry_search_word.bind("<Return>", perform_search)
    search_window.bind("<Control-w>", close_window)
    search_window.bind("<Escape>", close_window)

    if selected_word:
        perform_search()

def show_about():
    copyright_text = (
        "© 2024 Kayden Lee\n"
        "All rights reserved.\n\n"
        "This software and its contents are protected by copyright law. "
        "Unauthorized reproduction or distribution of this software, or any portion of it, "
        "may result in severe civil and criminal penalties, and will be prosecuted to the "
        "maximum extent possible under the law."
    )
    messagebox.showinfo("Copyright Information", copyright_text)

root = tk.Tk()
root.title("Vocabulary Manager")
root.geometry("800x600")
root.state("zoomed")  # Start the window maximized
root.resizable(True, True)

init_db()

main_frame = ttk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True)

frame_search = ttk.Frame(main_frame)
frame_search.pack(fill=tk.X, pady=5)
lbl_search = ttk.Label(frame_search, text="Search:")
lbl_search.pack(side=tk.LEFT, padx=5)
entry_search = ttk.Entry(frame_search)
entry_search.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=5)
entry_search.bind("<KeyRelease>", search_vocabulary)

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
entry_word.bind("<Return>", add_word)
lbl_meaning = ttk.Label(frame_add, text="Meaning:")
lbl_meaning.pack(side=tk.LEFT, padx=5)
entry_meaning = ttk.Entry(frame_add)
entry_meaning.pack(side=tk.LEFT, padx=5)
entry_meaning.bind("<Return>", add_word)
btn_add = ttk.Button(frame_add, text="Add Word", command=add_word)
btn_add.pack(side=tk.LEFT, padx=5)
btn_update = ttk.Button(frame_add, text="Update Word", command=update_word)
btn_update.pack(side=tk.LEFT, padx=5)
btn_delete = ttk.Button(frame_add, text="Delete Word", command=delete_word)
btn_delete.pack(side=tk.LEFT, padx=5)

side_panel = ttk.Frame(paned_window)
canvas = tk.Canvas(side_panel)
scroll_y = ttk.Scrollbar(side_panel, orient="vertical", command=canvas.yview)
scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
canvas.configure(yscrollcommand=scroll_y.set)
scroll_y.config(command=canvas.yview)

detail_label = ttk.Label(canvas, text="", justify=tk.LEFT, anchor="nw")
canvas.create_window((0, 0), window=detail_label, anchor="nw")

menubar = tk.Menu(root)

file = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file)
file.add_command(label="Refresh Data", command=load_vocabulary)
file.add_separator()
file.add_command(label="Exit", command=root.destroy)

edit = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="About", menu=edit)
edit.add_command(label="Information", command=show_about)

tools = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Tools", menu=tools)
tools.add_command(label="Search Dictionary", command=search_dictionary)

root.config(menu=menubar)

load_vocabulary()

root.bind("<Escape>", close_panel)

root.mainloop()

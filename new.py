import tkinter as tk
from tkinter import messagebox, ttk
import mysql.connector
import requests
import os
import uuid
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DB_CONFIG = {
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASS"],
    "host": os.environ["DB_HOST"],
    "database": "vocab-manager-dev",
}

DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


def generate_machine_id():
    """Generate a unique identifier for the current machine using its MAC address."""
    return ":".join(
        ["{:02x}".format((uuid.getnode() >> ele) & 0xFF) for ele in range(0, 8 * 6, 8)][
            ::-1
        ]
    )


MACHINE_ID = generate_machine_id()


def init_db():
    """Initialize the database schema with the required tables."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Create vocabulary table
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

    # Create license_keys table with machine_id feature and max_computers column
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS license_keys (
            key_id INT AUTO_INCREMENT PRIMARY KEY,
            license_key VARCHAR(255) NOT NULL UNIQUE,
            machine_id VARCHAR(255),
            status ENUM('active', 'used', 'revoked') NOT NULL DEFAULT 'active',
            expiry_date DATE DEFAULT NULL,
            max_computers INT NOT NULL DEFAULT 1  -- New column to track number of computers it can activate
        )
    """
    )

    # Create user_vocabularies table to link words with users and license keys
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_vocabularies (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            license_key_id INT,  -- Foreign key to the license_key
            word VARCHAR(255) NOT NULL,
            meaning TEXT NOT NULL,
            FOREIGN KEY (license_key_id) REFERENCES license_keys(key_id) ON DELETE CASCADE
        )
    """
    )

    conn.close()


def validate_license_key(license_key):
    """Validate the license key and ensure it matches the machine."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Check if the current machine has a used license
    cursor.execute(
        "SELECT license_key FROM license_keys WHERE machine_id = %s AND status = 'used'",
        (MACHINE_ID,),
    )
    used_license = cursor.fetchone()

    if used_license:
        conn.close()
        return (
            True,
            "Machine is already associated with a used license, skipping validation.",
        )

    # Proceed with regular license validation
    cursor.execute(
        "SELECT status, expiry_date, machine_id, max_computers FROM license_keys WHERE license_key = %s",
        (license_key,),
    )
    result = cursor.fetchone()

    if not result:
        conn.close()
        return False, "Invalid license key."

    status, expiry_date, machine_id, max_computers = result

    # Check status
    if status != "active":
        conn.close()
        return False, "License key is not active."
    elif machine_id and machine_id != MACHINE_ID:
        conn.close()
        return False, "License key is already linked to another machine."

    # Check if the number of activated computers exceeds max_computers
    cursor.execute(
        "SELECT COUNT(DISTINCT machine_id) FROM license_keys WHERE license_key = %s",
        (license_key,),
    )
    active_computers = cursor.fetchone()[0]

    if active_computers >= max_computers:
        conn.close()
        return (
            False,
            "This license has already been activated on the maximum number of computers.",
        )

    # Mark as used and associate with the machine if valid
    cursor.execute(
        "UPDATE license_keys SET status = 'used', machine_id = %s WHERE license_key = %s",
        (MACHINE_ID, license_key),
    )
    conn.commit()
    conn.close()
    return True, "License key validated successfully and linked to this machine."


def fetch_meaning(word):
    """Fetch the meaning of a word using the dictionary API."""
    url = f"{DICTIONARY_API_URL}{word.lower()}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data[0]["meanings"][0]["definitions"][0]["definition"]


def add_word(event=None):
    """Add a new word and its meaning to the user's vocabulary."""
    word = entry_word.get().strip()
    meaning = entry_meaning.get().strip()

    if not word:
        messagebox.showwarning("Input Error", "Please provide a word.")
        return

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Check if the word already exists for the user's license
    cursor.execute(
        "SELECT COUNT(*) FROM user_vocabularies WHERE license_key_id = %s AND word = %s",
        (license_key_id, word),
    )
    exists = cursor.fetchone()[0]

    if exists:
        conn.close()
        messagebox.showerror(
            "Error",
            f"The word '{word}' already exists in the database for this license.",
        )
        return

    if not meaning:
        set_cursor("wait")  # Show loading cursor
        meaning = fetch_meaning(word)
        set_cursor("")  # Reset cursor
        if not meaning:
            messagebox.showwarning(
                "Fetch Error", "Could not fetch meaning from the dictionary."
            )
            return

    try:
        cursor.execute(
            "INSERT INTO user_vocabularies (license_key_id, word, meaning) VALUES (%s, %s, %s)",
            (license_key_id, word, meaning),
        )
        conn.commit()
        conn.close()
        messagebox.showinfo(
            "Success", f"'{word}' added successfully to your vocabulary!"
        )
        entry_word.delete(0, tk.END)
        entry_meaning.delete(0, tk.END)
        load_vocabulary()
    except mysql.connector.Error as e:
        conn.close()
        messagebox.showerror("Database Error", f"An error occurred: {e}")


def edit_word():
    """Edit the selected word and update the database."""
    selected_item = tree_vocabulary.selection()
    if not selected_item:
        messagebox.showwarning("Selection Error", "Please select a word to edit.")
        return

    word = tree_vocabulary.item(selected_item, "values")[0]

    # Prompt user for new word and meaning
    edit_window = tk.Toplevel(root)
    edit_window.title("Edit Word")
    edit_window.geometry("400x200")

    ttk.Label(edit_window, text="Word:").pack(pady=5)
    entry_new_word = ttk.Entry(edit_window, font=("Verdana", 12))
    entry_new_word.pack(pady=5, padx=10, fill=tk.X)
    entry_new_word.insert(0, word)

    ttk.Label(edit_window, text="Meaning:").pack(pady=5)
    entry_new_meaning = ttk.Entry(edit_window, font=("Verdana", 12))
    entry_new_meaning.pack(pady=5, padx=10, fill=tk.X)

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT meaning FROM vocabulary WHERE word = %s", (word,))
    old_meaning = cursor.fetchone()
    if old_meaning:
        entry_new_meaning.insert(0, old_meaning[0])
    conn.close()

    def save_changes():
        new_word = entry_new_word.get().strip()
        new_meaning = entry_new_meaning.get().strip()

        if not new_word or not new_meaning:
            messagebox.showwarning(
                "Input Error", "Both Word and Meaning fields must be filled."
            )
            return

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE vocabulary SET word = %s, meaning = %s WHERE word = %s",
                (new_word, new_meaning, word),
            )
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Word updated successfully!")
            edit_window.destroy()
            load_vocabulary()
        except mysql.connector.IntegrityError:
            conn.close()
            messagebox.showerror("Error", "This word already exists in the database.")

    ttk.Button(edit_window, text="Save Changes", command=save_changes).pack(pady=10)

    edit_window.protocol("WM_DELETE_WINDOW", edit_window.destroy)


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


def on_search():
    search_term = entry_search.get().strip()
    load_vocabulary(search_term)


def load_vocabulary(search_term=""):
    """Load vocabulary words and meanings into the Treeview."""
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


def set_cursor(cursor_type):
    """Set the cursor type for the application."""
    root.config(cursor=cursor_type)
    root.update_idletasks()


def show_license_key_entry():
    """Prompt user to enter a license key for validation or skip if already validated."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Check if the machine already has a valid license
    cursor.execute(
        "SELECT status FROM license_keys WHERE machine_id = %s AND status IN ('active', 'used')",
        (MACHINE_ID,),
    )
    result = cursor.fetchone()
    conn.close()

    if result:
        # If a valid license is found, skip the license key input
        root.deiconify()  # Show the main application window
        return

    # Prompt for license key if no valid license is associated
    def submit_key():
        license_key = entry_license.get().strip()
        valid, message = validate_license_key(license_key)

        if valid:
            messagebox.showinfo("License Validation", message)
            license_window.destroy()
            root.deiconify()  # Show the main application window
        else:
            messagebox.showerror("License Validation", message)

    root.withdraw()  # Hide the main application window
    license_window = tk.Toplevel(root)
    license_window.title("License Key Validation")
    license_window.geometry("400x200")
    license_window.resizable(False, False)

    tk.Label(license_window, text="Enter your license key:", font=("Verdana", 12)).pack(
        pady=10
    )
    entry_license = ttk.Entry(license_window, font=("Verdana", 12))
    entry_license.pack(pady=5, padx=10, fill=tk.X)

    ttk.Button(license_window, text="Submit", command=submit_key).pack(pady=10)

    license_window.protocol("WM_DELETE_WINDOW", root.destroy)


def fetch_all_definitions(word):
    """Fetch all available definitions of a word using the dictionary API."""
    url = f"{DICTIONARY_API_URL}{word.lower()}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()

    # Extract all definitions
    definitions = []
    for meaning in data[0]["meanings"]:
        part_of_speech = meaning.get("partOfSpeech", "Unknown")
        definitions.extend(
            {
                "partOfSpeech": part_of_speech,
                "definition": definition["definition"],
            }
            for definition in meaning["definitions"]
        )
    return definitions


def view_definitions():
    """Display all definitions for the selected word in a popup window."""
    selected_item = tree_vocabulary.selection()
    if not selected_item:
        messagebox.showwarning(
            "Selection Error", "Please select a word to view its definitions."
        )
        return

    word = tree_vocabulary.item(selected_item, "values")[0]
    definitions = fetch_all_definitions(word)

    if not definitions:
        messagebox.showerror(
            "Error", "Could not fetch definitions for the selected word."
        )
        return

    # Create a popup window
    definitions_window = tk.Toplevel(root)
    definitions_window.title(f"Definitions of '{word}'")
    definitions_window.geometry("500x400")
    definitions_window.resizable(True, True)

    ttk.Label(
        definitions_window,
        text=f"{word}",
        font=("Verdana", 14, "bold"),
    ).pack(pady=10)

    # Create a scrollable text widget to display definitions
    frame = ttk.Frame(definitions_window)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    text_widget = tk.Text(frame, wrap=tk.WORD, font=("Verdana", 12))
    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    text_widget.config(yscrollcommand=scrollbar.set)

    # Insert definitions into the text widget
    for idx, definition in enumerate(definitions, start=1):
        part_of_speech = definition["partOfSpeech"]
        definition_text = definition["definition"]
        text_widget.insert(tk.END, f"{idx}. ({part_of_speech}) {definition_text}\n\n")

    text_widget.config(state=tk.DISABLED)  # Make the text widget read-only

    ttk.Button(
        definitions_window, text="Close", command=definitions_window.destroy
    ).pack(pady=10)


def show_license_status():
    """Display the license status linked to the current machine."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT license_key, status, expiry_date FROM license_keys WHERE machine_id = %s",
        (MACHINE_ID,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        messagebox.showinfo(
            "License Status", "No active or used license found for this machine."
        )
        return

    license_key, status, expiry_date = row
    expiry_text = "No expiry" if expiry_date is None else expiry_date
    message = f"License Key: {license_key}\nStatus: {status}\nExpiry: {expiry_text}"
    messagebox.showinfo("License Status", message)


def show_about():
    """Display information about the application."""
    messagebox.showinfo(
        "About Vocabulary Manager",
        "Vocabulary Manager\nVersion 1.0\n\nAuthor: Kayden Lee\n© 2024",
    )


def check_db_connection():
    """Test the database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.close()
        messagebox.showinfo("Database Connection", "Database connection is active.")
    except mysql.connector.Error as e:
        messagebox.showerror("Database Connection", f"Database connection failed: {e}")


def adjust_column_widths(event):
    """Adjust column widths based on Treeview width."""
    total_width = tree_vocabulary.winfo_width()
    word_width = int(total_width * 0.2)
    meaning_width = int(total_width * 0.8)

    tree_vocabulary.column("Word", width=word_width)
    tree_vocabulary.column("Meaning", width=meaning_width)


def clear_selection(event=None):
    """Clear the current selection in the Treeview."""
    tree_vocabulary.selection_remove(tree_vocabulary.selection())


# Main Application Window
root = tk.Tk()
root.title("Vocabulary Manager")
root.geometry("900x600")
root.iconbitmap("32x32.ico")
root.option_add("*Font", "Verdana 10")

# Menu Bar
menubar = tk.Menu(root)

# License Menu
license_menu = tk.Menu(menubar, tearoff=0)
license_menu.add_command(label="Check Activation Status", command=show_license_status)
menubar.add_cascade(label="License", menu=license_menu)

# Database Tools Menu
db_menu = tk.Menu(menubar, tearoff=0)
db_menu.add_command(label="Check Database Connection", command=check_db_connection)
db_menu.add_command(label="Refresh Data", command=lambda: load_vocabulary())
menubar.add_cascade(label="Database", menu=db_menu)

# About Menu
about_menu = tk.Menu(menubar, tearoff=0)
about_menu.add_command(label="About App", command=show_about)
menubar.add_cascade(label="About", menu=about_menu)

root.config(menu=menubar)

# Configure Treeview
style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview", font=("Verdana", 10), rowheight=30)
style.configure("Treeview.Heading", font=("Verdana", 12, "bold"))

columns = ("Word", "Meaning")
tree_vocabulary = ttk.Treeview(root, columns=columns, show="headings")
tree_vocabulary.heading("Word", text="Word")
tree_vocabulary.heading("Meaning", text="Meaning")
tree_vocabulary.column("Word", anchor="w")
tree_vocabulary.column("Meaning", anchor="w")
tree_vocabulary.pack(fill=tk.BOTH, expand=True, pady=10)

# Bind the resize event to adjust column widths dynamically
tree_vocabulary.bind("<Configure>", adjust_column_widths)

# Bind the Escape key to clear the selection
tree_vocabulary.bind("<Escape>", clear_selection)

# Scrollbar for Treeview
scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=tree_vocabulary.yview)
tree_vocabulary.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Search Frame
frame_search = ttk.Frame(root, padding=10)
frame_search.pack(fill=tk.X)

ttk.Label(frame_search, text="Search:").pack(side=tk.LEFT, padx=5)
entry_search = ttk.Entry(frame_search)
entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
ttk.Button(frame_search, text="Search", command=on_search).pack(side=tk.LEFT, padx=5)

# Input Frame
frame_input = ttk.Frame(root, padding=10)
frame_input.pack(fill=tk.X)

ttk.Label(frame_input, text="Word:").pack(side=tk.LEFT, padx=5)
entry_word = ttk.Entry(frame_input, width=30)
entry_word.pack(side=tk.LEFT, padx=5)
entry_word.bind("<Return>", add_word)  # Bind Enter key for adding a word

ttk.Label(frame_input, text="Meaning:").pack(side=tk.LEFT, padx=5)
entry_meaning = ttk.Entry(frame_input, width=50)
entry_meaning.pack(side=tk.LEFT, padx=5)
entry_meaning.bind("<Return>", add_word)  # Bind Enter key for adding a word

ttk.Button(frame_input, text="Add Word", command=add_word).pack(side=tk.LEFT, padx=5)
ttk.Button(frame_input, text="Edit Word", command=edit_word).pack(side=tk.LEFT, padx=5)
ttk.Button(frame_input, text="Delete Word", command=delete_word).pack(
    side=tk.LEFT, padx=5
)
ttk.Button(frame_input, text="View Definitions", command=view_definitions).pack(
    side=tk.LEFT, padx=5
)

# Initialize and Run Application
init_db()
show_license_key_entry()
load_vocabulary()

root.mainloop()

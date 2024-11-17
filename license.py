import tkinter as tk
from tkinter import messagebox, ttk
import mysql.connector
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DB_CONFIG = {
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASS"],
    "host": os.environ["DB_HOST"],
    "database": os.environ["DB_NAME"],
}

DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


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

    # Create license_keys table with expiry feature
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS license_keys (
            key_id INT AUTO_INCREMENT PRIMARY KEY,
            license_key VARCHAR(255) NOT NULL UNIQUE,
            status ENUM('active', 'used', 'revoked') NOT NULL DEFAULT 'active',
            expiry_date DATE DEFAULT NULL
        )
    """
    )

    conn.close()


def validate_license_key(license_key):
    """Validate the license key and check for expiry."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT status, expiry_date FROM license_keys WHERE license_key = %s",
        (license_key,),
    )
    result = cursor.fetchone()

    if not result:
        conn.close()
        return False, "Invalid license key."

    status, expiry_date = result

    # Check status
    if status == "revoked":
        conn.close()
        return False, "License key has been revoked."
    elif status == "used":
        conn.close()
        return False, "License key has already been used."

    # Check expiry
    if expiry_date and datetime.strptime(expiry_date, "%Y-%m-%d") < datetime.now():
        conn.close()
        return False, "License key has expired."

    # Mark as used if valid
    cursor.execute(
        "UPDATE license_keys SET status = 'used' WHERE license_key = %s", (license_key,)
    )
    conn.commit()
    conn.close()
    return True, "License key validated successfully."


# License Key Entry UI
def show_license_key_entry():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT license_key, status, expiry_date FROM license_keys WHERE status IN ('active', 'used')"
    )
    rows = cursor.fetchall()
    conn.close()

    if rows:
        return

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

    tk.Label(license_window, text="Enter your license key:", font=("Arial", 12)).pack(
        pady=10
    )
    entry_license = ttk.Entry(license_window, font=("Arial", 12))
    entry_license.pack(pady=5, padx=10, fill=tk.X)

    ttk.Button(license_window, text="Submit", command=submit_key).pack(pady=10)

    license_window.protocol("WM_DELETE_WINDOW", root.destroy)


def show_license_status():
    """Display the current activation and license status."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT license_key, status, expiry_date FROM license_keys WHERE status IN ('active', 'used')"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        messagebox.showinfo("License Status", "No active or used licenses found.")
        return

    message = ""
    for license_key, status, expiry_date in rows:
        expiry_text = "No expiry" if expiry_date is None else expiry_date
        message += f"Key: {license_key}\nStatus: {status}\nExpiry: {expiry_text}\n\n"

    messagebox.showinfo("License Status", message.strip())


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


def set_cursor(cursor_type):
    """Set the cursor type for the application."""
    root.config(cursor=cursor_type)
    root.update_idletasks()


# Functionality for fetching meaning, adding, deleting words (same as before)
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
        set_cursor("wait")  # Show loading cursor
        meaning = fetch_meaning(word)
        set_cursor("")  # Reset cursor
        if not meaning:
            messagebox.showwarning(
                "Fetch Error", "Could not fetch meaning from the dictionary."
            )
            return

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        set_cursor("wait")  # Show loading cursor
        cursor.execute(
            "INSERT INTO vocabulary (word, meaning) VALUES (%s, %s)", (word, meaning)
        )
        conn.commit()
        conn.close()
        set_cursor("")  # Reset cursor
        messagebox.showinfo("Success", f"'{word}' added successfully!")
        entry_word.delete(0, tk.END)
        entry_meaning.delete(0, tk.END)
        load_vocabulary()
    except mysql.connector.IntegrityError:
        set_cursor("")  # Reset cursor
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


# Initialize root window
root = tk.Tk()
root.title("Vocabulary Manager")
root.geometry("900x600")
root.iconbitmap("32x32.ico")

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

# Configure theme
style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview", font=("Arial", 10), rowheight=30)
style.configure("Treeview.Heading", font=("Arial", 12, "bold"))
style.configure(".", font=("Arial", 11))

# Search Frame
frame_search = ttk.Frame(root, padding=10)
frame_search.pack(fill=tk.X)

ttk.Label(frame_search, text="Search:").pack(side=tk.LEFT, padx=5)
entry_search = ttk.Entry(frame_search)
entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
ttk.Button(
    frame_search, text="Search", command=lambda: load_vocabulary(entry_search.get())
).pack(side=tk.LEFT, padx=5)

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

# Load initial vocabulary
init_db()
show_license_key_entry()
load_vocabulary()

# Start main loop
root.mainloop()

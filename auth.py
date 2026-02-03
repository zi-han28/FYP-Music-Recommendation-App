# auth.py
import sqlite3
import bcrypt
import streamlit as st

# Database file name (will be created automatically)
DB_NAME = "users.db"

def init_db():
    """Create the users table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Create table with username (primary key) and hashed password
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def create_user(username, password):
    """Register a new user securely."""
    if not username or not password:
        return False, "Username and password cannot be empty."
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if user already exists
    c.execute('SELECT username FROM users WHERE username = ?', (username,))
    if c.fetchone():
        conn.close()
        return False, "Username already exists."
    
    # Hash the password (using bcrypt)
    # 1. Encode string to bytes
    # 2. Generate salt and hash
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_pw))
        conn.commit()
        success = True
        msg = "Account created successfully! Please login."
    except Exception as e:
        success = False
        msg = f"Error creating account: {e}"
    finally:
        conn.close()
        
    return success, msg

def authenticate_user(username, password):
    """Verify login credentials."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('SELECT password FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    
    if result:
        stored_hash = result[0]
        # Check if the provided password matches the stored hash
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return True
            
    return False
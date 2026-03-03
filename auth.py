# auth.py (updated version)
import sqlite3
import bcrypt
import streamlit as st
import json

# Database file name (will be created automatically)
DB_NAME = "users.db"

def init_db():
    """Create the users table with favourites column if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Create table with username (primary key), hashed password, and favourites JSON column
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            favourites TEXT DEFAULT '[]'
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
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        c.execute('INSERT INTO users (username, password, favourites) VALUES (?, ?, ?)', 
                 (username, hashed_pw, '[]'))
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

def get_user_favourites(username):
    """Get favourites for a user."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('SELECT favourites FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0]:
        return json.loads(result[0])
    return []

def add_to_favourites(username, track_data):
    """Add a track to user's favourites."""
    favourites = get_user_favourites(username)
    
    # Check if already in favourites (avoid duplicates)
    for track in favourites:
        if track['track_id'] == track_data['track_id']:
            return False, "Song already in favourites"
    
    favourites.append(track_data)
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute('UPDATE users SET favourites = ? WHERE username = ?', 
                 (json.dumps(favourites), username))
        conn.commit()
        success = True
        msg = "Added to favourites!"
    except Exception as e:
        success = False
        msg = f"Error adding to favourites: {e}"
    finally:
        conn.close()
    
    return success, msg

def remove_from_favourites(username, track_id):
    """Remove a track from user's favourites."""
    favourites = get_user_favourites(username)
    
    # Filter out the track to remove
    favourites = [track for track in favourites if track['track_id'] != track_id]
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute('UPDATE users SET favourites = ? WHERE username = ?', 
                 (json.dumps(favourites), username))
        conn.commit()
        success = True
        msg = "Removed from favourites!"
    except Exception as e:
        success = False
        msg = f"Error removing from favourites: {e}"
    finally:
        conn.close()
    
    return success, msg

def is_favourite(username, track_id):
    """Check if a track is in user's favourites."""
    favourites = get_user_favourites(username)
    return any(track['track_id'] == track_id for track in favourites)
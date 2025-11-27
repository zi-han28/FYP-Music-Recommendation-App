import streamlit as st
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv

load_dotenv()

st.title("My Music Recommendation App")

# Authenticate user with Spotify
sp = Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-top-read"
))

st.write("Spotify authentication successful!")

# Example: Get user's top tracks
top_tracks = sp.current_user_top_tracks(limit=10)

for idx, track in enumerate(top_tracks["items"]):
    st.write(f"{idx+1}. {track['name']} by {track['artists'][0]['name']}")

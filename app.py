import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from dotenv import load_dotenv

load_dotenv()

st.title("My Music App")

client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

os.environ["SPOTIPY_CLIENT_ID"] = client_id
os.environ["SPOTIPY_CLIENT_SECRET"] = client_secret
os.environ["SPOTIPY_REDIRECT_URI"] = "https://open.spotify.com/"

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())

search = st.text_input("Enter a song to search:")

if search:
    results = sp.search(q=search, type="track", limit=5 )
    tracks = results["tracks"]["items"]

    if len(tracks) > 0:
        for i, track in enumerate(tracks) :
            st.write(f"**{i+1}. {track['name']}**")
            st.write("Artist:", track["artists"][0]["name"])
            st.write("Album:", track["album"]["name"])
            st.image(track["album"]["images"][1]["url"], width=200)
            st.markdown("---")
    else:
        st.write("No results found.")

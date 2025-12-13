# from reccobeats_api import get_reccobeats_features
# from soundcharts_api import get_audio_features_from_soundcharts
from soundnet_api import get_audio_features_from_soundnet
import librosa
import numpy as np
import requests
import io
from youtubesearchpython import VideosSearch
import streamlit as st
import streamlit.components.v1 as components
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

# --- 1. Initialize Session State for Search ---
if "search_query" not in st.session_state:
    st.session_state.search_query = ""

# --- 2. Song page ---
def show_song_page(track_id):
    # Add error handling in case ID is invalid
    try:
        track = sp.track(track_id)
    except:
        st.error("Could not load track.")
        if st.button("Back"):
             st.query_params.clear()
             st.rerun()
        st.stop()

    st.header(track["name"])
    st.subheader(track["artists"][0]["name"])

    if track["album"]["images"]:
        st.image(track["album"]["images"][0]["url"], width=300)
    
    st.write('Song Preview')
    embed_url = f"https://open.spotify.com/embed/track/{track['id']}"
    components.iframe(embed_url, height=80)

    st.write("Album:", track["album"]["name"])
    st.write("Release Date:", track["album"]["release_date"])

    st.markdown('Full Song: 'f"[Open in Spotify]({track['external_urls']['spotify']})")

    st.subheader("YouTube Video")
    # Create a search query based on the song info
    search_query = f"{track['name']} {track['artists'][0]['name']}"
    
    with st.spinner("Finding video on YouTube..."):
        try:
            # Search YouTube for 1 video
            videosSearch = VideosSearch(search_query, limit=1)
            results = videosSearch.result()
            
            if results['result']:
                # Get the video link
                video_url = results['result'][0]['link']
                # Streamlit has a native video player that handles YouTube links
                st.video(video_url)
            else:
                st.write("Could not find a video on YouTube.")
        except Exception as e:
            st.error(f"Error loading video")

    # Add this to your app.py (in the song page section, around line 80-90)

     # ###################################       
    st.subheader("Audio Features (Soundnet)")

    features = get_audio_features_from_soundnet(track_id)

    if not features:
        st.write("Could not fetch audio features for this track.")
    else:
        st.write(f"**Key:** {features.get('key')}")
        st.write(f"**Mode:** {features.get('mode')}")
        st.write(f"**Tempo (BPM):** {features.get('tempo')}")
        st.write(f"**Energy:** {features.get('energy')}")
        st.write(f"**Danceability:** {features.get('danceability')}")
        st.write(f"**Happiness:** {features.get('happiness')}")
        st.write(f"**Acousticness:** {features.get('acousticness')}")
        st.write(f"**Instrumentalness:** {features.get('instrumentalness')}")
        st.write(f"**Liveness:** {features.get('liveness')}")
        st.write(f"**Speechiness:** {features.get('speechiness')}")
        st.write(f"**Loudness:** {features.get('loudness')}")
     # ###################################
    st.subheader("Recommended Similar Songs")

    # Check if dataset exists
    dataset_path = "dataset.csv"
    if os.path.exists(dataset_path):
        try:
            # Import the recommender
            from recommender import get_recommendations_from_features
        
            # Get features from Soundnet (already fetched)
            features = get_audio_features_from_soundnet(track_id)
        
            if features:
                with st.spinner("Finding similar songs..."):
                    recommendations = get_recommendations_from_features(
                        features_dict=features,
                        track_id=track_id,
                        dataset_path=dataset_path,
                        k=5
                    )   
                
                if recommendations:
                    st.write("**Songs you might like:**")
                    for rec in recommendations:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{rec['track_name']}** — {rec['artists']}")
                            st.write(f"*Similarity: {rec['similarity_score']:.2f}*")
                        with col2:
                            if st.button("View", key=f"view_{rec['track_id']}"):
                                st.query_params["track_id"] = rec['track_id']
                                st.rerun()
                        st.markdown("---")
                else:
                    st.write("No recommendations found.")
            else:
                st.write("Could not get features for recommendations.")
        except ImportError:
            st.warning("Recommender module not available.")
        except Exception as e:
            st.error(f"Error getting recommendations: {e}")
    else:
        st.write("*Dataset file not found. Recommendations unavailable.*")
        ###########################################################

if "track_id" in st.query_params:
    show_song_page(st.query_params["track_id"])
    
    # Simple Back Button
    if st.button("Back to Search"):
        st.query_params.clear()
        st.rerun()
    st.stop()

# --- 3. Search function ---

# Link the widget to the session
def update_search_state():
    st.session_state.search_query = st.session_state.search_input

search = st.text_input(
    "Search a song:", 
    key="search_input", 
    value=st.session_state.search_query,
    on_change=update_search_state
)

if search:
    # Update the persistent state manually just to be safe
    st.session_state.search_query = search
    
    results = sp.search(q=search, type="track", limit=5)
    tracks = results["tracks"]["items"]

    if len(tracks) > 0:
        for i, track in enumerate(tracks):
            st.write(f"### {i+1}. {track['name']}")
            st.write("Artist:", track["artists"][0]["name"])
            st.write("Album:", track["album"]["name"])
            
            if track["album"]["images"]:
                st.image(track["album"]["images"][1]["url"], width=200)

            # Button: Select Song
            if st.button(f"Select Song {i+1}", key=track["id"]):
                st.query_params["track_id"] = track["id"]
                st.rerun()

            st.markdown("---")
    else:
        st.write("No results found.")

import time
from genius_api import get_lyrics, get_lyrics_with_info
from soundnet_api import get_audio_features_from_soundnet
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

     # ###################################       
    st.subheader("Audio Features (Soundnet)")

    # Try to get features with retry
    max_retries = 2
    features = None
    
    for attempt in range(max_retries + 1):
        with st.spinner(f"Fetching audio features (attempt {attempt + 1}/{max_retries + 1})..."):
            features = get_audio_features_from_soundnet(track_id)
        
        if features:
            break
        elif attempt < max_retries:
            st.info(f"Attempt {attempt + 1} failed. Retrying...")
            import time
            time.sleep(1)  # Small delay before retry

    if not features:
        st.write("⚠️ Could not fetch audio features for this track.")
        st.info("This might be because:")
        st.write("- The track is not in Soundnet's database")
        st.write("- The API is temporarily unavailable")
        st.write("- There's a network connection issue")
        st.write("")
        st.write("You can still enjoy the song preview, YouTube video, and recommendations.")
    else:
        # Display the features
        st.write(f"**Key:** {features.get('key', 'N/A')}")
        st.write(f"**Mode:** {features.get('mode', 'N/A')}")
        st.write(f"**Tempo (BPM):** {features.get('tempo', 'N/A')}")
        st.write(f"**Energy:** {features.get('energy', 'N/A')}")
        st.write(f"**Danceability:** {features.get('danceability', 'N/A')}")
        st.write(f"**Happiness:** {features.get('happiness', 'N/A')}")
        st.write(f"**Acousticness:** {features.get('acousticness', 'N/A')}")
        st.write(f"**Instrumentalness:** {features.get('instrumentalness', 'N/A')}")
        st.write(f"**Liveness:** {features.get('liveness', 'N/A')}")
        st.write(f"**Speechiness:** {features.get('speechiness', 'N/A')}")
        st.write(f"**Loudness:** {features.get('loudness', 'N/A')}")
     # ###################################
        ##########################################
    st.subheader("Recommended Similar Songs")
    # Check if dataset exists
    dataset_path = "dataset.csv"
    if os.path.exists(dataset_path):
        try:
            # Import the recommender
            from recommender import get_recommendations_from_features
            
            # Get features from Soundnet (with retry logic)
            max_retries = 2
            features = None
            
            for attempt in range(max_retries + 1):
                with st.spinner(f"Fetching features for recommendations (attempt {attempt + 1}/{max_retries + 1})..."):
                    features = get_audio_features_from_soundnet(track_id)
                
                if features:
                    break
                elif attempt < max_retries:
                    time.sleep(1)  # Small delay before retry
        
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
                    for i, rec in enumerate(recommendations):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{rec['track_name']}** — {rec['artists']}")
                            st.write(f"*Similarity: {rec['similarity_score']:.2f}*")
                        with col2:
                            # Use index in key to ensure uniqueness
                            if st.button("View", key=f"view_{i}_{rec['track_id']}"):
                                st.query_params["track_id"] = rec['track_id']
                                st.rerun()
                        st.markdown("---")
                else:
                    st.write("No recommendations found.")
            else:
                st.warning("⚠️ Could not fetch audio features for recommendations.")
                st.write("The recommender needs audio features to find similar songs.")
                st.write("")
                st.write("**Possible reasons:**")
                st.write("- This track is not in Soundnet's database")
                st.write("- The API service is temporarily unavailable")
                st.write("- There's a network connection issue")
                st.write("")
                st.write("**You can try:**")
                st.write("- Searching for a different song")
                st.write("- Checking your internet connection")
                st.write("- Trying again later")
                
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

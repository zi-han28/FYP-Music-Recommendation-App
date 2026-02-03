import time
import streamlit as st
import streamlit.components.v1 as components
import spotipy
import os
from spotipy.oauth2 import SpotifyClientCredentials
from reccobeats import get_audio_features_with_fallback, get_recommendations_from_features  # Use your new Spotify helper
from dotenv import load_dotenv
from youtubesearchpython import VideosSearch

# Import your custom modules
from genius_api import get_lyrics_with_info
from BERT_analysis import SentimentAnalyzer
from auth import init_db, create_user, authenticate_user

# --- INITIAL SETUP ---
init_db()
load_dotenv()

# Initialize session state for login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "recommendations" not in st.session_state:
    st.session_state.recommendations = None
if "current_track_for_rec" not in st.session_state:
    st.session_state.current_track_for_rec = None

# --- LOGIN FUNCTIONS ---
def login_page():
    st.title("🎵 Music App Login")
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.header("Welcome Back")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            if authenticate_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        st.header("Create Account")
        new_user = st.text_input("New Username", key="reg_user")
        new_pass = st.text_input("New Password", type="password", key="reg_pw")
        if st.button("Register"):
            if len(new_pass) < 4:
                st.error("Password must be at least 4 characters")
            else:
                success, msg = create_user(new_user, new_pass)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

def logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.recommendations = None
    st.session_state.current_track_for_rec = None
    st.rerun()

# --- CHECK LOGIN STATUS ---
if not st.session_state.logged_in:
    login_page()
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.username}**")
    if st.button("Logout"):
        logout()
    st.divider()

# --- SPOTIFY SETUP ---
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

# Ensure env vars are set for Spotipy
os.environ["SPOTIPY_CLIENT_ID"] = client_id
os.environ["SPOTIPY_CLIENT_SECRET"] = client_secret
os.environ["SPOTIPY_REDIRECT_URI"] = "http://localhost:8501/callback" # Updated to localhost

# Initialize Spotify Client
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())

# --- AI MODEL LOADING ---
@st.cache_resource
def load_bert_analyzer():
    with st.spinner("Loading AI Sentiment Model..."):
        return SentimentAnalyzer()

bert_analyzer = load_bert_analyzer()

# --- RECOMMENDATION DISPLAY FUNCTION ---
def display_recommendations(recommendations, current_track_name):
    if not recommendations:
        st.warning("No recommendations available.")
        return
    
    st.subheader(f"🎧 Recommended Songs (Similar to {current_track_name})")
    

    
    for i, rec in enumerate(recommendations):
            
            with st.container():
                # Get track details from Spotify
                try:
                    track_info = sp.track(rec['track_id'])
                    
                    # Display album cover
                    if track_info["album"]["images"]:
                        st.image(track_info["album"]["images"][1]["url"], width=150)
                    
                    # Display track info
                    st.write(f"**{rec['track_name']}**")
                    st.write(f"*{rec['artists']}*")
                    
                    # Display similarity score
                    similarity_percent = rec['similarity_score'] * 100
                    st.progress(rec['similarity_score'], 
                                text=f"Similarity: {similarity_percent:.1f}%")
                    
                    # View button
                    if st.button("View", key=f"rec_{i}_{rec['track_id']}"):
                        st.query_params["track_id"] = rec['track_id']
                        st.session_state.recommendations = None
                        st.session_state.current_track_for_rec = None
                        st.rerun()
                    
                    st.divider()
                    
                except Exception as e:
                    st.error(f"Could not load track details: {e}")
                    # Fallback display without album cover
                    st.write(f"**{rec['track_name']}**")
                    st.write(f"*{rec['artists']}*")
                    
                    similarity_percent = rec['similarity_score'] * 100
                    st.progress(rec['similarity_score'], 
                                text=f"Similarity: {similarity_percent:.1f}%")
                    
                    if st.button("View", key=f"rec_{i}_{rec['track_id']}_fallback"):
                        st.query_params["track_id"] = rec['track_id']
                        st.session_state.recommendations = None
                        st.session_state.current_track_for_rec = None
                        st.rerun()

# --- SONG PAGE LOGIC ---
def show_song_page(track_id):
    # Clear previous recommendations when viewing a new track
    if st.session_state.current_track_for_rec != track_id:
        st.session_state.recommendations = None
        st.session_state.current_track_for_rec = track_id
    
    # 1. Fetch Track Metadata
    try:
        track = sp.track(track_id)
    except Exception as e:
        st.error(f"Could not load track: {e}")
        if st.button("Back"):
             st.query_params.clear()
             st.rerun()
        st.stop()

    # Back Button
    if st.button("Back to Search"):
        st.query_params.clear()
        st.session_state.recommendations = None
        st.session_state.current_track_for_rec = None
        st.rerun()

    # Display Header & Album Art
    st.header(track["name"])
    st.subheader(track["artists"][0]["name"])

    if track["album"]["images"]:
        st.image(track["album"]["images"][0]["url"], width=300)
    
    # Spotify Embed Player
    st.write('Song Preview')
    embed_url = f"https://open.spotify.com/embed/track/{track['id']}" # Fixed embed URL format
    components.iframe(embed_url, height=80)

    st.write(f"**Album:** {track['album']['name']}")
    st.write(f"**Release Date:** {track['album']['release_date']}")
    st.markdown(f"[Open in Spotify]({track['external_urls']['spotify']})")

    # YouTube Section
    st.subheader("YouTube Video")
    search_query = f"{track['name']} {track['artists'][0]['name']}"
    with st.spinner("Finding video on YouTube..."):
        try:
            videosSearch = VideosSearch(search_query, limit=1)
            results = videosSearch.result()
            if results['result']:
                video_url = results['result'][0]['link']
                st.video(video_url)
            else:
                st.write("Could not find a video on YouTube.")
        except Exception:
            st.warning("Could not load YouTube video.")

    # --- AUDIO FEATURES SECTION ---
    st.subheader("🎵 Audio Features Analysis")
    
    with st.spinner("Analyzing audio features via Reccobeats..."):
        features, reccobeats_id = get_audio_features_with_fallback(track_id)
    
    if features and reccobeats_id:
        # Create columns for organized display
        col1, col2, col3 = st.columns(3)
        
        # Common audio features
        with col1:
            if 'danceability' in features:
                st.metric("Danceability", f"{features['danceability']:.3f}")
            if 'energy' in features:
                st.metric("Energy", f"{features['energy']:.3f}")
            if 'valence' in features:
                valence_desc = "Happy/Positive" if features['valence'] > 0.5 else "Sad/Negative"
                st.metric("Valence", f"{features['valence']:.3f}")
                st.caption(valence_desc)
        
        with col2:
            if 'tempo' in features:
                st.metric("Tempo", f"{features['tempo']:.1f} BPM")
            if 'loudness' in features:
                st.metric("Loudness", f"{features['loudness']:.1f} dB")
            if 'acousticness' in features:
                st.metric("Acousticness", f"{features['acousticness']:.3f}")
        
        with col3:
            if 'instrumentalness' in features:
                instrumental_desc = "Instrumental" if features['instrumentalness'] > 0.5 else "Vocal"
                st.metric("Instrumentalness", f"{features['instrumentalness']:.3f}")
                st.caption(instrumental_desc)
            if 'speechiness' in features:
                speech_desc = "Speech-heavy" if features['speechiness'] > 0.66 else "Music-heavy"
                st.metric("Speechiness", f"{features['speechiness']:.3f}")
                st.caption(speech_desc)
            if 'liveness' in features:
                live_desc = "Live recording" if features['liveness'] > 0.8 else "Studio recording"
                st.metric("Liveness", f"{features['liveness']:.3f}")
                st.caption(live_desc)
        
        # Raw data expander for debugging
        with st.expander("📊 View Raw Audio Features Data"):
            st.json(features)
    else:
        st.warning("Audio features not available for this track via Reccobeats")
        
    # --- RECOMMENDATIONS SECTION ---
    st.write("---")
    st.subheader("🎯 Get Recommendations")
    
    # Button to trigger recommendations
    if st.button("Get Similar Songs", type="primary", key="get_recommendations"):
        with st.spinner("Finding similar songs..."):
            try:
                recommendations = get_recommendations_from_features(
                    features_dict=features if features else {},
                    track_id=track_id,
                    k=6  # Get 6 recommendations
                )
                
                if recommendations:
                    st.session_state.recommendations = recommendations
                    st.success(f"Found {len(recommendations)} recommendations!")
                    st.rerun()
                else:
                    st.error("Could not generate recommendations. Please try again.")
                    
            except Exception as e:
                st.error(f"Error generating recommendations: {e}")
    
    # Display recommendations if they exist
    if st.session_state.recommendations:
        display_recommendations(st.session_state.recommendations, track["name"])
    
    # Clear recommendations button
    if st.session_state.recommendations:
        if st.button("Clear Recommendations", key="clear_recommendations"):
            st.session_state.recommendations = None
            st.rerun()

# --- SEARCH PAGE LOGIC ---
if "track_id" in st.query_params:
    show_song_page(st.query_params["track_id"])
    
    if st.button("Back to Search", key="bottom_back"):
        st.query_params.clear()
        st.session_state.recommendations = None
        st.session_state.current_track_for_rec = None
        st.rerun()
    st.stop()

# --- MAIN SEARCH PAGE ---
st.title("My Music App")

def update_search_state():
    st.session_state.search_query = st.session_state.search_input

search = st.text_input(
    "Search a song:", 
    key="search_input", 
    value=st.session_state.search_query,
    on_change=update_search_state
)

if search:
    st.session_state.search_query = search
    try:
        results = sp.search(q=search, type="track", limit=5)
        tracks = results["tracks"]["items"]

        if len(tracks) > 0:
            for i, track in enumerate(tracks):
                st.write(f"### {i+1}. {track['name']}")
                st.write(f"**Artist:** {track['artists'][0]['name']}")
                st.write(f"**Album:** {track['album']['name']}")
                
                if track["album"]["images"]:
                    st.image(track["album"]["images"][1]["url"], width=200)

                if st.button(f"Select Song", key=track["id"]):
                    st.query_params["track_id"] = track["id"]
                    st.session_state.recommendations = None
                    st.session_state.current_track_for_rec = None
                    st.rerun()

                st.markdown("---")
        else:
            st.write("No results found.")
    except Exception as e:
        st.error(f"Search failed: {e}")
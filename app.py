import time
import streamlit as st
import streamlit.components.v1 as components
import spotipy
import os
from spotipy.oauth2 import SpotifyClientCredentials
from hybrid import get_audio_features_with_fallback, get_recommendations_from_features, get_hybrid_recommendations_for_user, CollaborativeFilteringEngine
from auth import get_user_favourites, add_to_favourites, remove_from_favourites, is_favourite
from dotenv import load_dotenv
import yt_dlp


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
if "lyrics_cache" not in st.session_state:
    st.session_state.lyrics_cache = {}
if "sentiment_cache" not in st.session_state:
    st.session_state.sentiment_cache = {}
if "hybrid_recs_cache" not in st.session_state:
    st.session_state.hybrid_recs_cache = None
if "hybrid_recs_fav_hash" not in st.session_state:
    st.session_state.hybrid_recs_fav_hash = None
if "use_sentiment_features" not in st.session_state:
    st.session_state.use_sentiment_features = True

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
    st.session_state.lyrics_cache = {}
    st.session_state.sentiment_cache = {}
    st.session_state.hybrid_recs_cache = None
    st.session_state.hybrid_recs_fav_hash = None
    st.rerun()

def _invalidate_hybrid_cache():
    """Invalidate the hybrid recommendations cache (call when favourites change)."""
    st.session_state.hybrid_recs_cache = None
    st.session_state.hybrid_recs_fav_hash = None

# --- CHECK LOGIN STATUS ---
if not st.session_state.logged_in:
    login_page()
    st.stop()

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

# --- FAVOURITES---
def display_favourites_in_sidebar():
    """Display user's favourite songs in the sidebar."""
    with st.sidebar:
        st.divider()
        st.subheader("❤️ Your Favourites")
        
        favourites = get_user_favourites(st.session_state.username)
        
        if not favourites:
            st.caption("No favourites yet. Click the heart on any song to add!")
        else:
            for i, track in enumerate(favourites[-10:]):  # Show last 10 favourites
                with st.container():
                    col1, col2 = st.columns([3, 1.5])
                    with col1:
                        if st.button(f"🎵 {track['track_name'][:20]}...", 
                                    key=f"fav_{i}_{track['track_id']}",
                                    use_container_width=True):
                            st.query_params["track_id"] = track['track_id']
                            st.session_state.recommendations = None
                            st.session_state.current_track_for_rec = None
                            st.rerun()
                    with col2:
                        remove_button = st.button("❌", key=f"remove_fav_{i}_{track['track_id']}")

                if remove_button:
                    success, msg = remove_from_favourites(
                        st.session_state.username, 
                        track['track_id']
                    )
                    if success:
                        st.success(msg)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(msg)
                    
            
            if len(favourites) > 10:
                st.caption(f"...and {len(favourites) - 10} more")

def handle_favourite_button(track_id, track_name, artist_name, album_name, album_image):
    """Handle favourite button click."""
    is_fav = is_favourite(st.session_state.username, track_id)
    
    col_heart, col_status = st.columns([1, 10])
    
    with col_heart:
        button_label = "❤️" if is_fav else "🩶"
        clicked = st.button(button_label, key=f"favourite_{track_id}", help="Add to favourites")
    
    with col_status:
        if is_fav:
            st.caption("In your favourites")
    
    # Handle click OUTSIDE columns so messages render full-width
    if clicked:
        if is_fav:
            success, msg = remove_from_favourites(st.session_state.username, track_id)
        else:
            track_data = {
                'track_id': track_id,
                'track_name': track_name,
                'artist_name': artist_name,
                'album_name': album_name,
                'album_image': album_image,
                'added_at': time.time()
            }
            success, msg = add_to_favourites(st.session_state.username, track_data)
        
        if success:
            _invalidate_hybrid_cache()
            st.success(msg)
            time.sleep(1)
            st.rerun()
        else:
            st.error(msg)

# --- SIDEBAR ---
with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.username}**")
    if st.button("Logout"):
        logout()
    st.divider()

    display_favourites_in_sidebar()

# --- LYRICS---
def get_cached_lyrics(track_name, artist_name):
    """Get lyrics from cache or fetch if not cached."""
    cache_key = f"{track_name}|{artist_name}"
    
    if cache_key in st.session_state.lyrics_cache:
        return st.session_state.lyrics_cache[cache_key]
    
    # Fetch and cache
    with st.spinner("Fetching lyrics..."):
        lyrics_data = get_lyrics_with_info(track_name, artist_name)
        st.session_state.lyrics_cache[cache_key] = lyrics_data
        return lyrics_data

def get_cached_sentiment(lyrics_text, track_name, artist_name):
    """Get sentiment from cache or analyze if not cached."""
    cache_key = f"{track_name}|{artist_name}"
    
    if cache_key in st.session_state.sentiment_cache:
        return st.session_state.sentiment_cache[cache_key]
    
    # Analyze and cache
    try:
        sentiment_result = bert_analyzer.analyze(lyrics_text)
        st.session_state.sentiment_cache[cache_key] = sentiment_result
        return sentiment_result
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        return None

def display_lyrics_section(track_name, artist_name):
    """Display lyrics and sentiment analysis section."""
    st.write("---")
    st.subheader("Lyrics Analysis")
    
    # Get cached lyrics
    lyrics_data = get_cached_lyrics(track_name, artist_name)
    
    if lyrics_data and lyrics_data.get('lyrics'):
        # Get cached sentiment
        sentiment_result = get_cached_sentiment(lyrics_data['lyrics'], track_name, artist_name)
        
        if sentiment_result:
            col1, col2 = st.columns(2)
            
            with col1:
                label = sentiment_result['label']
                color_str = "green" if "Positive" in label else "red" if "Negative" in label else "gray"
                st.markdown(f"**Mood:** :{color_str}[{label}]")
                
            with col2:
                st.metric("Sentiment Score", f"{sentiment_result['score']}/2.0")
                st.caption(f"Confidence: {int(sentiment_result['confidence'] * 100)}%")
        
        # Lyrics expander
        with st.expander("Show Full Lyrics"):
            st.text(lyrics_data['lyrics'])
            st.markdown("---")
            
            # Add refresh button for lyrics (optional)
            if st.button("Refresh Lyrics", key="refresh_lyrics"):
                # Clear from cache to force refresh
                cache_key = f"{track_name}|{artist_name}"
                if cache_key in st.session_state.lyrics_cache:
                    del st.session_state.lyrics_cache[cache_key]
                if cache_key in st.session_state.sentiment_cache:
                    del st.session_state.sentiment_cache[cache_key]
                st.rerun()
    else:
        st.info("Lyrics not found for this track.")
        # Add retry button
        if st.button("Retry Lyrics Search", key="retry_lyrics"):
            cache_key = f"{track_name}|{artist_name}"
            if cache_key in st.session_state.lyrics_cache:
                del st.session_state.lyrics_cache[cache_key]
            st.rerun()

# --- RECOMMENDATION DISPLAY---
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

def display_recommendations_section(track_id, track, features):
    track_name = track['name']
    artist_name = track['artists'][0]['name']
    cache_key = f"{track_name}|{artist_name}"

    # Check if sentiment is available
    has_sentiment = cache_key in st.session_state.sentiment_cache

    if has_sentiment:
        sentiment_result = st.session_state.sentiment_cache[cache_key]
        sentiment_score = sentiment_result['score'] / 2.0
    
        st.caption("Choose which audio features to use for recommendations:")
        with st.container(border=True):
            col_sent, col_orig = st.columns(2)
            with col_sent:
                if st.button(
                    "Sentimental Value",
                    key="btn_sentiment",
                    type="primary" if st.session_state.use_sentiment_features else "secondary",
                    use_container_width=True
                ):
                    st.session_state.use_sentiment_features = True
                    st.session_state.recommendations = None
                    st.rerun()
            with col_orig:
                if st.button(
                    "Original Features",
                    key="btn_original",
                    type="primary" if not st.session_state.use_sentiment_features else "secondary",
                    use_container_width=True
                ):
                    st.session_state.use_sentiment_features = False
                    st.session_state.recommendations = None
                    st.rerun()

        # Build features based on selection
        if st.session_state.use_sentiment_features:
            modified_features = features.copy() if features else {}
            modified_features['valence'] = sentiment_score
            st.info(f"Using BERT sentimental valence: {sentiment_score:.3f}")
        else:
            modified_features = features.copy() if features else {}
            st.info(f"Using original valence: {modified_features.get('valence', 'N/A')}")
    else:
        modified_features = features.copy() if features else {}
    
    # Button to trigger recommendations
    if st.button("Get Similar Songs", type="primary", key="get_recommendations"):
        with st.spinner("Finding similar songs..."):
            try:
                recommendations = get_recommendations_from_features(
                    features_dict=modified_features,
                    track_id=track_id,
                    k=6
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
    
    # Clear recommendations button (only shows when recommendations exist)
    if st.session_state.recommendations:
        if st.button("Clear Recommendations", key="clear_recommendations"):
            st.session_state.recommendations = None
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
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header(track["name"])
        st.subheader(track["artists"][0]["name"])

    # Add favourite button near the header
    album_image = track["album"]["images"][0]["url"] if track["album"]["images"] else None
    handle_favourite_button(
        track_id=track_id,
        track_name=track["name"],
        artist_name=track["artists"][0]["name"],
        album_name=track["album"]["name"],
        album_image=album_image)

    if track["album"]["images"]:
        st.image(track["album"]["images"][0]["url"], width=300)
    
    # Spotify Embed Player
    st.write('Song Preview')
    embed_url = f"https://open.spotify.com/embed/track/{track['id']}" # Fixed embed URL format
    components.iframe(embed_url, height=80)

    st.write(f"**Album:** {track['album']['name']}")
    st.write(f"**Release Date:** {track['album']['release_date']}")
    st.markdown(f"[Open in Spotify]({track['external_urls']['spotify']})")

    # YOUTUBE SECTION
    st.subheader("YouTube Video")
    search_query = f"{track['name']} {track['artists'][0]['name']}"
    with st.spinner("Finding video on YouTube..."):
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True, 'default_search': 'ytsearch1'}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{search_query}", download=False)
                if info and 'entries' in info and info['entries']:
                    video_url = info['entries'][0]['webpage_url']
                    st.video(video_url)
                else:
                    st.write("Could not find a video on YouTube.")
        except Exception:
            st.warning("Could not load YouTube video.")

    # AUDIO FEATURES SECTION
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

    # --- LYRICS & SENTIMENT SECTION ---
    track_name = track['name']
    artist_name = track['artists'][0]['name']
    display_lyrics_section(track_name, artist_name)
        
    # --- CBF RECOMMENDATIONS SECTION ---
    st.write("---")
    st.subheader("🎯 Get Recommendations")
    display_recommendations_section(track_id, track, features)
    
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
tab_search, tab_fyp = st.tabs(["🔍 Search", "🎯 For You"])


# =============================================================================
# SEARCH TAB
with tab_search:
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
# =============================================================================
# FYP TAB
with tab_fyp:
    favourites = get_user_favourites(st.session_state.username)
    
    # Hash of favourites to detect changes → invalidate cache
    fav_hash = hash(tuple(sorted(f.get('track_id', '') for f in favourites))) if favourites else None
    
    cache_valid = (
        st.session_state.hybrid_recs_cache is not None
        and st.session_state.hybrid_recs_fav_hash == fav_hash
    )
    
    if not favourites:
        # --- Cold start: show popular tracks from charts ---
        st.subheader("🔥 Popular Tracks")
        st.caption("Add songs to your favourites to get personalised recommendations!")
        
        cf_engine = CollaborativeFilteringEngine("final_charts_updated.csv")
        popular = cf_engine.get_popular_tracks(k=6)
        
        if popular:
            for i, rec in enumerate(popular):
                with st.container():
                    st.write(f"**{i+1}. {rec['track_name']}**")
                    st.write(f"*{rec['artists']}*")
                    
                    try:
                        track_info = sp.track(rec['track_id'])
                        if track_info["album"]["images"]:
                            st.image(track_info["album"]["images"][1]["url"], width=150)
                        if st.button("View", key=f"pop_{i}_{rec['track_id']}"):
                            st.query_params["track_id"] = rec['track_id']
                            st.session_state.recommendations = None
                            st.session_state.current_track_for_rec = None
                            st.rerun()
                    except Exception:
                        st.caption(f"Spotify ID: {rec['track_id']}")
                    
                    st.divider()
        else:
            st.info("Charts data not available.")
    
    else:
        # --- Personalised hybrid recommendations ---
        st.subheader("🎯 Recommended For You")
        
        col_info, col_refresh = st.columns([4, 1])
        with col_refresh:
            if st.button("🔄 Refresh", key="refresh_hybrid"):
                cache_valid = False
        
        if cache_valid:
            hybrid_recs, alpha, debug_info = st.session_state.hybrid_recs_cache
        else:
            with st.spinner("Building your personalised recommendations..."):
                hybrid_recs, alpha, debug_info = get_hybrid_recommendations_for_user(
                    favourites,
                    charts_csv_path="final_charts_updated.csv",
                    k=6
                )
                st.session_state.hybrid_recs_cache = (hybrid_recs, alpha, debug_info)
                st.session_state.hybrid_recs_fav_hash = fav_hash
        
        # Info line
        with col_info:
            mode_label = debug_info.get('mode', 'unknown')
            in_charts = debug_info.get('in_charts', 0)
            total_fav = debug_info.get('total_favourites', 0)
            
            if mode_label == 'cbf_only':
                st.caption(f"Based on your {total_fav} favourite(s) • Content-based")
            elif mode_label == 'hybrid':
                st.caption(
                    f"Based on your {total_fav} favourite(s) • "
                    f"Hybrid (α={alpha:.2f}, {in_charts} in charts)"
                )
            else:
                st.caption("Popular tracks")
        
        # Debug expander
        with st.expander("ℹ️ How this works"):
            st.write(f"**Dynamic Alpha:** {alpha:.3f}")
            st.write(f"**Favourites in charts:** {debug_info.get('in_charts', 0)} / {debug_info.get('total_favourites', 0)}")
            st.write(f"**Mode:** {debug_info.get('mode', 'N/A')}")
            st.write(f"**CF recommendations:** {debug_info.get('cf_count', 0)}")
            st.write(f"**CBF recommendations:** {debug_info.get('cbf_count', 0)}")
            st.caption(
                "When more of your favourites are in the charts dataset, "
                "the system uses collaborative filtering (CF) more heavily. "
                "Otherwise it relies on content-based filtering (CBF) using audio features."
            )
        
        # Display recommendations
        if hybrid_recs:
            for i, rec in enumerate(hybrid_recs):
                with st.container():
                    source_tag = ""
                    if rec.get('source') == 'cf':
                        source_tag = "📊 Charts-based"
                    elif rec.get('source') == 'cbf':
                        source_tag = "🎵 Audio-based"
                    elif rec.get('source') == 'popular':
                        source_tag = "🔥 Popular"
                    
                    try:
                        track_info = sp.track(rec['track_id'])
                        
                        col_img, col_info_card = st.columns([1, 3])
                        with col_img:
                            if track_info["album"]["images"]:
                                st.image(track_info["album"]["images"][1]["url"], width=150)
                        
                        with col_info_card:
                            st.write(f"**{rec['track_name']}**")
                            st.write(f"*{rec['artists']}*")
                            if source_tag:
                                st.caption(source_tag)
                            
                            similarity_percent = rec['similarity_score'] * 100
                            st.progress(
                                min(rec['similarity_score'], 1.0),
                                text=f"Match: {similarity_percent:.1f}%"
                            )
                            
                            if st.button("View", key=f"fy_{i}_{rec['track_id']}"):
                                st.query_params["track_id"] = rec['track_id']
                                st.session_state.recommendations = None
                                st.session_state.current_track_for_rec = None
                                st.rerun()
                    
                    except Exception:
                        st.write(f"**{rec['track_name']}**")
                        st.write(f"*{rec['artists']}*")
                        if source_tag:
                            st.caption(source_tag)
                        if st.button("View", key=f"fy_{i}_{rec['track_id']}_fb"):
                            st.query_params["track_id"] = rec['track_id']
                            st.session_state.recommendations = None
                            st.session_state.current_track_for_rec = None
                            st.rerun()
                    
                    st.divider()
        # else:
        #     st.info("Could not generate recommendations. Try adding more songs to your favourites!")
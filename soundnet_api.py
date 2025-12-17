# soundnet_api.py
import requests
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# Simple cache to avoid repeated API calls
_features_cache = {}

def get_audio_features_from_soundnet(track_id: str, max_retries: int = 2) -> dict:
    """
    Get audio features for a Spotify track using the Soundnet API via RapidAPI.
    
    Args:
        track_id (str): Spotify track ID
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        dict: Audio features or None if request fails
    """
    # Check cache first
    if track_id in _features_cache:
        print(f"Using cached features for track {track_id}")
        return _features_cache[track_id]
    
    if not RAPIDAPI_KEY:
        print("ERROR: RAPIDAPI_KEY not found in environment variables")
        print("Please add RAPIDAPI_KEY=your_key to your .env file")
        return None
    
    url = f"https://track-analysis.p.rapidapi.com/pktx/spotify/{track_id}"
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "track-analysis.p.rapidapi.com"
    }
    
    for attempt in range(max_retries + 1):
        try:
            print(f"Attempt {attempt + 1}/{max_retries + 1} for track {track_id}")
            
            # Increase timeout for retries
            timeout = 15 if attempt > 0 else 10
            
            response = requests.get(url, headers=headers, timeout=timeout)
            
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Successfully fetched features for track {track_id}")
                    
                    # Cache the successful response
                    _features_cache[track_id] = data
                    return data
                    
                except ValueError as e:
                    print(f"JSON decode error: {e}")
                    if attempt == max_retries:
                        print(f"Response text: {response.text[:200]}...")
                    continue
                    
            elif response.status_code == 401:
                print(f"Authentication error: Invalid API key")
                return None
                
            elif response.status_code == 403:
                print(f"Access forbidden: Check your RapidAPI subscription")
                return None
                
            elif response.status_code == 404:
                print(f"Track not found in Soundnet database: {track_id}")
                # Cache the not-found result to avoid retrying
                _features_cache[track_id] = None
                return None
                
            elif response.status_code == 429:
                print(f"Rate limit exceeded: Too many requests")
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    print(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                return None
                
            else:
                print(f"API error: Status code {response.status_code}")
                if attempt == max_retries:
                    print(f"Response: {response.text[:200]}...")
                continue
                
        except requests.Timeout:
            print(f"Request timeout for track {track_id} (attempt {attempt + 1})")
            if attempt < max_retries:
                wait_time = (attempt + 1) * 1  # Linear backoff
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                continue
            _features_cache[track_id] = None
            return None
            
        except requests.RequestException as e:
            print(f"Request error: {e}")
            if attempt < max_retries:
                time.sleep(1)
                continue
            _features_cache[track_id] = None
            return None
            
        except Exception as e:
            print(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries:
                time.sleep(1)
                continue
            _features_cache[track_id] = None
            return None
    
    # If all retries failed
    _features_cache[track_id] = None
    return None


def clear_cache():
    """Clear the features cache."""
    global _features_cache
    _features_cache.clear()
    print("Features cache cleared")


def get_cached_features(track_id: str) -> dict:
    """Get features from cache if available."""
    return _features_cache.get(track_id)
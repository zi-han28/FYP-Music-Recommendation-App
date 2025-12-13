# import requests
# import os

# RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")  # put in .env

# def get_audio_features_from_soundnet(track_id: str):
#     url = f"https://track-analysis.p.rapidapi.com/pktx/spotify/{track_id}"

#     headers = {
#         "x-rapidapi-key": RAPIDAPI_KEY,
#         "x-rapidapi-host": "track-analysis.p.rapidapi.com"
#     }

#     response = requests.get(url, headers=headers)

#     if response.status_code != 200:
#         return None

#     try:
#         return response.json()
#     except Exception:
#         return None
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

def get_audio_features_from_soundnet(track_id: str):
    """
    Get audio features for a Spotify track using the Soundnet API via RapidAPI.
    
    Args:
        track_id (str): Spotify track ID
        
    Returns:
        dict: Audio features or None if request fails
    """
    if not RAPIDAPI_KEY:
        print("ERROR: RAPIDAPI_KEY not found in environment variables")
        print("Please add RAPIDAPI_KEY=your_key to your .env file")
        return None
    
    url = f"https://track-analysis.p.rapidapi.com/pktx/spotify/{track_id}"
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "track-analysis.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # Debug: Print status code
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Successfully fetched features for track {track_id}")
                return data
            except ValueError as e:
                print(f"JSON decode error: {e}")
                print(f"Response text: {response.text}")
                return None
        elif response.status_code == 401:
            print(f"Authentication error: Invalid API key")
            return None
        elif response.status_code == 403:
            print(f"Access forbidden: Check your RapidAPI subscription")
            return None
        elif response.status_code == 429:
            print(f"Rate limit exceeded: Too many requests")
            return None
        else:
            print(f"API error: Status code {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.Timeout:
        print(f"Request timeout for track {track_id}")
        return None
    except requests.RequestException as e:
        print(f"Request error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None
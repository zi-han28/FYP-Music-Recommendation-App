# spotify_features.py
import spotipy
from typing import Dict, Optional

def get_audio_features(track_id: str, sp_client: spotipy.Spotify) -> Optional[Dict]:
    """
    Fetch audio features directly from Spotify's official API.
    
    Args:
        track_id: The Spotify ID of the track.
        sp_client: The authenticated Spotipy client object.
        
    Returns:
        Dictionary of audio features or None if failed.
    """
    try:
        # Get audio features for the track
        # This returns a list containing one dictionary
        features_list = sp_client.audio_features([track_id])
        
        if features_list and features_list[0]:
            features = features_list[0]
            
            # Rename 'valence' to 'happiness' if your app expects that key, 
            # or keep it as 'valence' to match the dataset.
            # The Kaggle dataset uses 'valence', so we keep it.
            
            return features
        else:
            print(f"No audio features found for track {track_id}")
            return None
            
    except Exception as e:
        print(f"Error fetching Spotify audio features: {e}")
        return None
"""
Music Recommender System
=======================
A K-NN based recommender that uses Soundnet audio features
to find similar songs from a pre-built dataset.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from typing import List, Dict, Tuple

try:
    from soundnet_api import get_audio_features_from_soundnet
except ImportError:
    def get_audio_features_from_soundnet(track_id: str):
        print(f"Warning: soundnet_api not available")
        return None


def load_and_prepare_dataset(dataset_path: str) -> Tuple[pd.DataFrame, StandardScaler, List[str]]:
    """
    Load the dataset and prepare features for comparison.
    
    Args:
        dataset_path: Path to the CSV dataset file
        
    Returns:
        Tuple of (feature_df, fitted_scaler, feature_columns)
    """
    # Load dataset
    df = pd.read_csv(dataset_path)
    
    # Define features that will be used for comparison
    # Using Spotify dataset features (0-1 scale)
    feature_columns = [
        'danceability',    # 0-1
        'energy',          # 0-1
        'key',             # 0-11
        'loudness',        # dB (negative)
        'mode',            # 0 or 1
        'speechiness',     # 0-1
        'acousticness',    # 0-1
        'instrumentalness', # 0-1
        'liveness',        # 0-1
        'valence',         # 0-1 (happiness)
        'tempo'           # BPM
    ]
    
    # Check which columns exist in the dataset
    available_features = [col for col in feature_columns if col in df.columns]
    
    if len(available_features) < len(feature_columns):
        missing = set(feature_columns) - set(available_features)
        print(f"Warning: Missing columns in dataset: {missing}")
    
    # Create feature DataFrame
    feature_df = df[available_features].copy()
    
    # Add track metadata
    metadata_cols = ['track_id', 'track_name', 'artists', 'album_name']
    for col in metadata_cols:
        if col in df.columns:
            feature_df[col] = df[col]
    
    # Normalize features
    scaler = StandardScaler()
    feature_df[available_features] = scaler.fit_transform(feature_df[available_features])
    
    return feature_df, scaler, available_features


def convert_soundnet_to_spotify_scale(soundnet_features: Dict) -> Dict:
    """
    Convert Soundnet API values (0-100 scale) to Spotify dataset scale (0-1).
    
    Args:
        soundnet_features: Raw features from Soundnet API
        
    Returns:
        Features converted to Spotify scale
    """
    converted = {}
    
    # Convert 0-100 to 0-1 for these features
    for feature in ['danceability', 'energy', 'happiness', 'acousticness', 
                   'instrumentalness', 'liveness', 'speechiness']:
        if feature in soundnet_features:
            value = soundnet_features[feature]
            # Handle different data types
            if isinstance(value, (int, float)):
                converted[feature] = value / 100.0
            elif isinstance(value, str):
                try:
                    converted[feature] = float(value) / 100.0
                except:
                    converted[feature] = 0.5  # Default
            else:
                converted[feature] = 0.5
        else:
            converted[feature] = 0.5  # Default
    
    # Tempo is already in BPM, but handle string format
    if 'tempo' in soundnet_features:
        tempo = soundnet_features['tempo']
        if isinstance(tempo, str):
            try:
                converted['tempo'] = float(tempo)
            except:
                converted['tempo'] = 120.0  # Default BPM
        else:
            converted['tempo'] = float(tempo)
    else:
        converted['tempo'] = 120.0
    
    # Loudness: Soundnet returns "-10 dB", dataset uses -9.935
    if 'loudness' in soundnet_features:
        loudness = soundnet_features['loudness']
        if isinstance(loudness, str) and 'dB' in loudness:
            try:
                converted['loudness'] = float(loudness.replace('dB', '').strip())
            except:
                converted['loudness'] = -10.0
        else:
            converted['loudness'] = float(loudness)
    else:
        converted['loudness'] = -10.0
    
    # Convert key from note name to number (0-11)
    key_map = {
        'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
        'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
        'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
    }
    
    if 'key' in soundnet_features:
        key = str(soundnet_features['key']).strip().upper()
        if key in key_map:
            converted['key'] = key_map[key]
        else:
            # Try to parse as number
            try:
                key_num = int(key)
                if 0 <= key_num <= 11:
                    converted['key'] = key_num
                else:
                    converted['key'] = 0
            except:
                converted['key'] = 0
    else:
        converted['key'] = 0
    
    # Mode: major=1, minor=0
    if 'mode' in soundnet_features:
        mode = str(soundnet_features['mode']).lower()
        if 'major' in mode:
            converted['mode'] = 1
        elif 'minor' in mode:
            converted['mode'] = 0
        else:
            # Try numeric
            try:
                mode_val = int(mode)
                converted['mode'] = 1 if mode_val == 1 else 0
            except:
                converted['mode'] = 1  # Default to major
    else:
        converted['mode'] = 1
    
    # Rename 'happiness' to 'valence' to match dataset
    if 'happiness' in converted:
        converted['valence'] = converted.pop('happiness')
    elif 'valence' not in converted:
        converted['valence'] = 0.5
    
    return converted


def prepare_soundnet_features(
    features_dict: Dict, 
    scaler: StandardScaler, 
    feature_columns: List[str]
) -> np.ndarray:
    """
    Convert Soundnet API response to normalized feature vector.
    
    Args:
        features_dict: Dictionary from Soundnet API
        scaler: Pre-fitted StandardScaler
        feature_columns: List of feature names in correct order
        
    Returns:
        Normalized feature vector
    """
    # First convert Soundnet features to Spotify scale
    spotify_features = convert_soundnet_to_spotify_scale(features_dict)
    
    # Build feature vector in the correct order
    feature_vector = []
    for col in feature_columns:
        if col in spotify_features:
            value = spotify_features[col]
        else:
            # Default values for missing features
            if col in ['danceability', 'energy', 'valence', 'acousticness', 
                      'instrumentalness', 'liveness', 'speechiness']:
                value = 0.5  # Middle value for 0-1 features
            elif col == 'key':
                value = 0  # C major
            elif col == 'mode':
                value = 1  # Major
            elif col == 'tempo':
                value = 120.0  # Default BPM
            elif col == 'loudness':
                value = -10.0  # Default dB
            else:
                value = 0
        
        feature_vector.append(float(value))
    
    # Convert to numpy array
    feature_array = np.array(feature_vector).reshape(1, -1)
    
    # Apply the same scaling used on the dataset
    feature_array = scaler.transform(feature_array)
    
    return feature_array.flatten()


def find_same_track_in_dataset(track_id: str, feature_df: pd.DataFrame) -> int:
    """
    Check if a track exists in the dataset and return its index.
    
    Args:
        track_id: Spotify track ID to find
        feature_df: Dataset DataFrame
        
    Returns:
        Index of the track in the DataFrame, or -1 if not found
    """
    if 'track_id' not in feature_df.columns:
        return -1
    
    # Check if track_id exists in dataset
    matches = feature_df['track_id'] == track_id
    if matches.any():
        return matches.idxmax()  # Return first match index
    return -1


def get_recommendations_from_features(
    features_dict: Dict,
    track_id: str = None,  # Add track_id parameter to exclude it
    dataset_path: str = "dataset.csv",
    k: int = 5
) -> List[Dict]:
    """
    Get song recommendations based on Soundnet features.
    
    Args:
        features_dict: Audio features from Soundnet API
        track_id: Original track ID to exclude from recommendations
        dataset_path: Path to dataset CSV
        k: Number of recommendations
        
    Returns:
        List of recommended tracks with metadata
    """
    try:
        # Load and prepare dataset
        feature_df, scaler, feature_columns = load_and_prepare_dataset(dataset_path)
        
        # Extract only feature columns (no metadata)
        metadata_cols = ['track_id', 'track_name', 'artists', 'album_name']
        feature_cols_only = [col for col in feature_columns if col not in metadata_cols]
        
        # Get feature matrix
        feature_matrix = feature_df[feature_cols_only].values
        
        # Train KNN model - ask for more neighbors to have enough after filtering
        n_neighbors = min(k + 5, len(feature_matrix))  # Get extra neighbors
        model = NearestNeighbors(
            n_neighbors=n_neighbors,
            metric='cosine',
            algorithm='brute'
        )
        model.fit(feature_matrix)
        
        # Prepare query features from Soundnet
        query_features = prepare_soundnet_features(features_dict, scaler, feature_cols_only)
        query_features_reshaped = query_features.reshape(1, -1)
        
        # Find nearest neighbors
        distances, indices = model.kneighbors(query_features_reshaped)
        
        # Build recommendation list, excluding the original track if it exists in dataset
        recommendations = []
        for i, idx in enumerate(indices.flatten()):
            if len(recommendations) >= k:
                break
                
            track_data = feature_df.iloc[idx]
            current_track_id = track_data.get('track_id', 'Unknown')
            
            # Skip if this is the same track we're getting recommendations for
            if track_id and current_track_id == track_id:
                continue
            
            # Skip duplicates in recommendations
            if any(rec['track_id'] == current_track_id for rec in recommendations):
                continue
            
            recommendation = {
                'track_id': current_track_id,
                'track_name': track_data.get('track_name', 'Unknown'),
                'artists': track_data.get('artists', 'Unknown'),
                'album_name': track_data.get('album_name', 'Unknown'),
                'similarity_score': float(1 - distances.flatten()[i])  # Convert to similarity
            }
            recommendations.append(recommendation)
        
        # If we don't have enough recommendations, try getting more without the track_id check
        if len(recommendations) < k:
            for i, idx in enumerate(indices.flatten()):
                if len(recommendations) >= k:
                    break
                    
                track_data = feature_df.iloc[idx]
                current_track_id = track_data.get('track_id', 'Unknown')
                
                # Skip duplicates
                if any(rec['track_id'] == current_track_id for rec in recommendations):
                    continue
                
                recommendation = {
                    'track_id': current_track_id,
                    'track_name': track_data.get('track_name', 'Unknown'),
                    'artists': track_data.get('artists', 'Unknown'),
                    'album_name': track_data.get('album_name', 'Unknown'),
                    'similarity_score': float(1 - distances.flatten()[i])
                }
                recommendations.append(recommendation)
        
        return recommendations
        
    except FileNotFoundError:
        print(f"Error: Dataset file not found at {dataset_path}")
        return []
    except Exception as e:
        print(f"Error in get_recommendations_from_features: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_recommendations(
    track_id: str,
    dataset_path: str = "dataset.csv",
    k: int = 5
) -> List[Dict]:
    """
    Get recommendations by fetching features from Soundnet API.
    
    Args:
        track_id: Spotify track ID
        dataset_path: Path to dataset CSV
        k: Number of recommendations
        
    Returns:
        List of recommended tracks
    """
    # Get features from Soundnet
    features = get_audio_features_from_soundnet(track_id)
    
    if not features:
        print(f"Could not fetch features for track {track_id}")
        return []
    
    # Debug: Print raw Soundnet features
    print(f"Raw Soundnet features for {track_id}:")
    for key, value in features.items():
        print(f"  {key}: {value} (type: {type(value).__name__})")
    
    # Use the features to get recommendations, excluding the original track
    return get_recommendations_from_features(features, track_id, dataset_path, k)


# Testing
# if __name__ == "__main__":
#     print("Testing recommender system...")
    
#     # Test with mock Creep features
#     mock_features = {
#         'key': 'G',
#         'mode': 'major',
#         'tempo': '92',
#         'energy': '43',
#         'danceability': '52',
#         'happiness': '10',
#         'acousticness': '1',
#         'instrumentalness': '0',
#         'liveness': '13',
#         'speechiness': '4',
#         'loudness': '-10 dB'
#     }
    
#     try:
#         # Test with a mock track ID that won't be in dataset
#         recommendations = get_recommendations_from_features(
#             features_dict=mock_features,
#             track_id="test_track_123",  # Not in dataset
#             dataset_path="dataset.csv",
#             k=5
#         )
        
#         print(f"\nFound {len(recommendations)} recommendations:")
#         for i, rec in enumerate(recommendations, 1):
#             print(f"{i}. {rec['track_name']} by {rec['artists']}")
#             print(f"   Album: {rec.get('album_name', 'Unknown')}")
#             print(f"   Track ID: {rec['track_id']}")
#             print(f"   Similarity: {rec['similarity_score']:.3f}")
#             print()
            
#     except Exception as e:
#         print(f"Test failed: {e}")
#         import traceback
#         traceback.print_exc()
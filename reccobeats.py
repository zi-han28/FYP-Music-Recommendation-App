# reccobeats.py
import requests
import numpy as np
from typing import Dict, Optional, Tuple, Any, List
import json
import time
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors


class ReccobeatsAPI:
    """Client for interacting with the Reccobeats API."""
    
    def __init__(self):
        """Initialize the Reccobeats API client."""
        self.base_url = "https://api.reccobeats.com/v1"
        self.headers = {
            'Accept': 'application/json'
        }
    
    def get_track_details(self, spotify_track_id: str) -> Optional[Dict[str, Any]]:
        """
        Get track details from Reccobeats API using Spotify track ID.
        """
        url = f"{self.base_url}/track?ids={spotify_track_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            track_data = response.json()
            
            if "content" in track_data and len(track_data["content"]) > 0:
                return track_data["content"][0]
            else:
                return None
                
        except requests.exceptions.RequestException:
            return None
        except json.JSONDecodeError:
            return None
    
    def get_audio_features(self, spotify_track_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get audio features for the selected Spotify track.
        """
        # Step 1: Get track details to extract Reccobeats ID
        track_details = self.get_track_details(spotify_track_id)
        
        if not track_details:
            return None, None
        
        # Extract Reccobeats ID
        reccobeats_id = track_details.get("id")
        if not reccobeats_id:
            return None, None
        
        # Step 2: Get audio features using Reccobeats ID
        url = f"{self.base_url}/track/{reccobeats_id}/audio-features"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            audio_features = response.json()
            return audio_features, reccobeats_id
            
        except requests.exceptions.RequestException:
            return None, reccobeats_id
        except json.JSONDecodeError:
            return None, reccobeats_id
    
    def get_batch_AF(self, reccobeats_ids: List[str], batch_size: int = 40) -> List[Dict]:
        """
        Get audio features for multiple tracks using Reccobeats IDs.
        """
        all_features = []
        
        for i in range(0, len(reccobeats_ids), batch_size):
            batch = reccobeats_ids[i:i + batch_size]
            params = {"ids": ",".join(batch)}
            
            try:
                url = f"{self.base_url}/audio-features"
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                features_list = self._extract_features_from_response(data)
                if features_list:
                    all_features.extend(features_list)
                
                print(f"Processed {min(i + batch_size, len(reccobeats_ids))} / {len(reccobeats_ids)} Reccobeats IDs")
                time.sleep(0.2)
                
            except Exception as e:
                print(f"Request error for batch starting at index {i}: {e}")
                time.sleep(1.0)
                # Retry logic omitted for brevity, keeping main flow clean
                
        return all_features
    
    def _extract_features_from_response(self, data: Any) -> List[Dict]:
        """Extract audio features list from API response."""
        if isinstance(data, dict):
            if "audio_features" in data:
                features_list = data["audio_features"] or []
            elif "features" in data:
                features_list = data["features"] or []
            elif "data" in data:
                features_list = data["data"] or []
            elif "items" in data:
                features_list = data["items"] or []
            elif "content" in data:
                features_list = data["content"] or []
            else:
                candidates = [v for v in data.values() if isinstance(v, list)]
                features_list = candidates[0] if candidates else []
        elif isinstance(data, list):
            features_list = data
        else:
            features_list = []
        return features_list
    
    def extract_audio_features_vector(self, audio_features: Dict) -> List[float]:
        """Extract and normalize audio features into a numerical vector."""
        feature_definitions = {
            'danceability': {'range': (0, 1), 'default': 0.5},
            'energy': {'range': (0, 1), 'default': 0.5},
            'valence': {'range': (0, 1), 'default': 0.5},
            'tempo': {'range': (0, 250), 'default': 120},
            'loudness': {'range': (-60, 0), 'default': -10},
            'acousticness': {'range': (0, 1), 'default': 0.5},
            'instrumentalness': {'range': (0, 1), 'default': 0.5},
            'liveness': {'range': (0, 1), 'default': 0.5},
            'speechiness': {'range': (0, 1), 'default': 0.5},
            'key': {'range': (0, 11), 'default': 0},
            'mode': {'range': (0, 1), 'default': 1}
        }
        
        feature_vector = []
        for feature_name, feature_config in feature_definitions.items():
            if feature_name in audio_features and audio_features[feature_name] is not None:
                value = audio_features[feature_name]
                min_val, max_val = feature_config['range']
                if max_val > min_val:
                    normalized = (value - min_val) / (max_val - min_val)
                    normalized = max(0, min(1, normalized))
                else:
                    normalized = 0.5
                feature_vector.append(normalized)
            else:
                min_val, max_val = feature_config['range']
                default_val = feature_config['default']
                normalized = (default_val - min_val) / (max_val - min_val) if max_val > min_val else 0.5
                feature_vector.append(normalized)
        
        return feature_vector
    
    def get_recommendations(
        self, 
        spotify_track_id: str,
        size: int = 6,  # Default size updated to 6
        **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """Get track recommendations based on a Spotify track ID."""
        params = {
            'size': size,
            'seeds': spotify_track_id
        }
        
        # Add optional filters
        optional_params = ['acousticness', 'danceability', 'energy', 'instrumentalness', 
                          'key', 'liveness', 'loudness', 'mode', 'speechiness', 
                          'tempo', 'valence', 'popularity']
        
        for param in optional_params:
            if param in kwargs and kwargs[param] is not None:
                params[param] = kwargs[param]
        
        try:
            url = f"{self.base_url}/track/recommendation"
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            response.raise_for_status()
            
            recommendations_data = response.json()
            if "content" in recommendations_data:
                return recommendations_data["content"]
            else:
                return []
        except Exception as e:
            print(f"Error fetching recommendations: {e}")
            return None
    
    def get_enhanced_recommendations(
        self, 
        spotify_track_id: str,
        initial_recommendations_count: int = 100,
        final_recommendations_count: int = 6,
        **filters
    ) -> List[Dict]:
        """
        Get enhanced recommendations using K-NN filtering.
        """
        try:
            # 1. Get original track features
            original_features, _ = self.get_audio_features(spotify_track_id)
            if not original_features:
                return []
            original_vector = self.extract_audio_features_vector(original_features)
            
            # 2. Get initial recommendations
            initial_recs = self.get_recommendations(
                spotify_track_id,
                size=initial_recommendations_count,
                **filters
            )
            if not initial_recs:
                return []
            
            # 3. Process metadata & extract IDs
            reccobeats_ids = []
            rec_map = {}
            for rec in initial_recs:
                rid = rec.get('id')
                if rid:
                    reccobeats_ids.append(rid)
                    
                    # Extract Spotify ID from URL more carefully
                    spotify_url = rec.get('href', '')
                    spotify_track_id_from_url = ''
                    
                    # Try different patterns for Spotify URL
                    if 'spotify.com/track/' in spotify_url:
                        # Handle various URL formats
                        parts = spotify_url.split('spotify.com/track/')
                        if len(parts) > 1:
                            track_part = parts[1]
                            # Remove query parameters if any
                            spotify_track_id_from_url = track_part.split('?')[0].split('/')[0]
                    
                    # If no valid Spotify ID found, use Reccobeats ID
                    track_id_to_use = spotify_track_id_from_url if len(spotify_track_id_from_url) == 22 else rid
                    
                    rec_map[rid] = {
                        'track_title': rec.get('trackTitle', 'Unknown'),
                        'artists': ', '.join([a.get('name', 'Unknown') for a in rec.get('artists', [])]),
                        'spotify_url': spotify_url,
                        'spotify_track_id': track_id_to_use,
                        'popularity': rec.get('popularity', 0)
                    }

            if not reccobeats_ids:
                return []

            # 4. Batch fetch audio features for recommendations
            batch_features = self.get_batch_AF(reccobeats_ids)
            features_by_id = {f.get('id'): f for f in batch_features if f.get('id')}
            
            # 5. Prepare data for K-NN
            recs_with_features = []
            for rid in reccobeats_ids:
                if rid in features_by_id and rid in rec_map:
                    feat_vec = self.extract_audio_features_vector(features_by_id[rid])
                    meta = rec_map[rid]
                    recs_with_features.append({
                        'track_id': meta['spotify_track_id'],
                        'track_name': meta['track_title'],
                        'artists': meta['artists'],
                        'feature_vector': feat_vec,
                        'popularity': meta['popularity'],
                        'spotify_url': meta['spotify_url'],
                        'reccobeats_id': rid  # Store for fallback
                    })

            # Handle edge case: not enough data for K-NN
            if len(recs_with_features) < 2:
                return [
                    {
                        'track_id': r['track_id'],
                        'track_name': r['track_name'],
                        'artists': r['artists'],
                        'similarity_score': 0.8,
                        'popularity': r['popularity'],
                        'reccobeats_id': r['reccobeats_id']
                    } for r in recs_with_features[:final_recommendations_count]
                ]

            # 6. Run K-NN
            vectors = [original_vector] + [r['feature_vector'] for r in recs_with_features]
            scaler = StandardScaler()
            scaled_vectors = scaler.fit_transform(np.array(vectors))
            
            k_neighbors = min(final_recommendations_count + 1, len(scaled_vectors))
            knn = NearestNeighbors(n_neighbors=k_neighbors, metric='cosine', algorithm='brute')
            knn.fit(scaled_vectors)
            
            distances, indices = knn.kneighbors(scaled_vectors[0:1])
            
            final_recs = []
            for i, neighbor_idx in enumerate(indices[0]):
                if neighbor_idx == 0: continue # Skip self
                
                rec_idx = neighbor_idx - 1 # Adjust for offset
                if 0 <= rec_idx < len(recs_with_features):
                    rec = recs_with_features[rec_idx]
                    similarity = 1 - distances[0][i]
                    
                    # Weight by popularity (optional)
                    weighted_score = (0.9 * similarity) + (0.1 * (rec['popularity'] / 100.0))
                    
                    final_recs.append({
                        'track_id': rec['track_id'],
                        'track_name': rec['track_name'],
                        'artists': rec['artists'],
                        'similarity_score': weighted_score,
                        'popularity': rec['popularity'],
                        'reccobeats_id': rec['reccobeats_id']
                    })
            
            final_recs.sort(key=lambda x: x['similarity_score'], reverse=True)
            return final_recs[:final_recommendations_count]
            
        except Exception as e:
            print(f"Error in enhanced recommendations: {e}")
            return []

# --- EXPORTED FUNCTIONS ---

def get_audio_features_with_fallback(spotify_track_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Convenience function to get audio features."""
    api = ReccobeatsAPI()
    return api.get_audio_features(spotify_track_id)

def get_recommendations_from_features(
    features_dict: Dict,
    track_id: str = None,
    dataset_path: str = None,
    k: int = 6  # UPDATED DEFAULT to 6
) -> List[Dict]:
    """
    Main entry point for recommendations. 
    Uses Reccobeats API with K-NN enhancement.
    """
    if not track_id:
        return []
    
    api = ReccobeatsAPI()
    return api.get_enhanced_recommendations(
        track_id,
        initial_recommendations_count=100,
        final_recommendations_count=k
    )

# UNIT TESTS

def test_batch_audio_features():
    """Test the batch audio features functionality."""
    print("=" * 60)
    print("Testing Batch Audio Features")
    print("=" * 60)
    
    # Create API instance
    api = ReccobeatsAPI()
    
    # First get Reccobeats IDs for some Spotify tracks
    test_spotify_ids = [
        "70LcF31zb1H0PyJoS1Sx1r",  # Creep - Radiohead
        "11dFghVXANMlKmJXsNCbNl",  # Bohemian Rhapsody - Queen
        "0UaMYEvWZi0ZqiDOoHU3YI",  # Blinding Lights - The Weeknd
    ]
    
    print("Getting Reccobeats IDs for test tracks...")
    reccobeats_ids = []
    for spotify_id in test_spotify_ids:
        track_details = api.get_track_details(spotify_id)
        if track_details and 'id' in track_details:
            reccobeats_ids.append(track_details['id'])
            print(f"  {spotify_id} -> {track_details['id']}")
        else:
            print(f"  Warning: Could not get Reccobeats ID for {spotify_id}")
    
    if reccobeats_ids:
        print(f"\nGetting batch audio features for {len(reccobeats_ids)} Reccobeats IDs...")
        batch_features = api.get_batch_AF(reccobeats_ids, batch_size=3)
        
        if batch_features:
            print(f"\n✅ Retrieved {len(batch_features)} audio features")
            print("-" * 40)
            
            for i, features in enumerate(batch_features):
                reccobeats_id = features.get('id', 'Unknown')
                print(f"\n{i+1}. Reccobeats ID: {reccobeats_id}")
                if 'danceability' in features:
                    print(f"   Danceability: {features['danceability']:.3f}")
                if 'energy' in features:
                    print(f"   Energy: {features['energy']:.3f}")
                if 'tempo' in features:
                    print(f"   Tempo: {features['tempo']:.1f} BPM")
        else:
            print("\n❌ No batch features retrieved")
    else:
        print("\n❌ No Reccobeats IDs obtained")
    
    print("\n" + "=" * 60)
    return batch_features


def test_enhanced_recommendations_with_batch():
    """Test enhanced recommendations using batch processing."""
    print("=" * 60)
    print("Testing Enhanced Recommendations with Batch Processing")
    print("=" * 60)
    
    # Spotify ID for "Creep" by Radiohead
    creep_spotify_id = "70LcF31zb1H0PyJoS1Sx1r"
    
    # Create API instance
    api = ReccobeatsAPI()
    
    print(f"\n🎵 Getting enhanced recommendations for 'Creep' (Spotify ID: {creep_spotify_id})")
    print("-" * 40)
    
    # Get enhanced recommendations
    enhanced_recommendations = api.get_enhanced_recommendations(
        creep_spotify_id,
        initial_recommendations_count=100,
        final_recommendations_count=4
    )
    
    if enhanced_recommendations:
        print(f"\n✅ Found {len(enhanced_recommendations)} enhanced recommendations")
        print("-" * 40)
        
        for i, rec in enumerate(enhanced_recommendations, 1):
            similarity_percent = rec['similarity_score'] * 100
            print(f"\n{i}. {rec['track_name']}")
            print(f"   Artists: {rec['artists']}")
            print(f"   Similarity: {similarity_percent:.1f}%")
            print(f"   Popularity: {rec.get('popularity', 'N/A')}")
            print(f"   Track ID: {rec['track_id']}")
    else:
        print("\n❌ No enhanced recommendations found")
    
    print("\n" + "=" * 60)
    return enhanced_recommendations


if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING RECCOBEATS API WITH BATCH PROCESSING")
    print("="*80)
    
    # Test batch audio features
    test_batch_audio_features()
    
    # Test enhanced recommendations with batch processing
    test_enhanced_recommendations_with_batch()
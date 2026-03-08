from tkinter import N
from turtle import distance
import requests
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Any, List
import json
import time
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
import os
from pathlib import Path


# knn model
def train_knn(vectors: np.ndarray, n_neighbors: int = 10, scale: bool = True) -> Tuple['NearestNeighbors', np.ndarray, Optional['StandardScaler']]:
    """
    Shared KNN trainer used by CBF (song page), CBF (taste profile), and CF.
    
    Returns:
        - Fitted NearestNeighbors model
        - Scaled (or raw) vectors used for fitting
        - StandardScaler instance (None if scale=False)
    """
    scaler = None
    if scale:
        scaler = StandardScaler()
        scaled = scaler.fit_transform(vectors)
    else:
        scaled = vectors
    
    k = min(n_neighbors, len(scaled))
    model = NearestNeighbors(n_neighbors=k, metric='cosine', algorithm='brute')
    model.fit(scaled)
    return model, scaled, scaler


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
        # Get track details to extract Reccobeats ID
        track_details = self.get_track_details(spotify_track_id)
        
        if not track_details:
            return None, None
        
        # Extract Reccobeats ID
        reccobeats_id = track_details.get("id")
        if not reccobeats_id:
            return None, None
        
        #Get audio features using Reccobeats ID
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

            url = f"{self.base_url}/audio-features"
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
                
            features_list = self.extract_features_from_response(data)
            if features_list:
                all_features.extend(features_list)
                
            print(f"Processed {min(i + batch_size, len(reccobeats_ids))} / {len(reccobeats_ids)} Reccobeats IDs")
            time.sleep(0.2)
            
            # try:
            # except Exception as e:
            #     print(f"Request error for batch starting at index {i}: {e}")
            #     time.sleep(1.0)
                # Retry logic omitted for brevity, keeping main flow clean
                
        return all_features
    
    def extract_features_from_response(self, data: Any) -> List[Dict]:
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
        
    @staticmethod
    def extract_spotifyID_from_url(spotify_url: str) -> str:

        if not spotify_url or 'spotify.com/track/' not in spotify_url:
            return ''
        parts = spotify_url.split('spotify.com/track/')
        if len(parts) > 1:
            track_part = parts[1]
            if len(track_part) == 22: #make sure that the spotify id is only 22 characters
                return track_part
        return ''

    
    def rec_metadata(self, initial_recs: List[Dict]) -> Tuple[List[str], Dict]:
        """
        Process raw recommendation results into reccobeats_ids list and rec_map dict.
        Shared helper for get_enhanced_recommendations and CF pipeline.
        """
        reccobeats_ids = []
        rec_map = {}
        
        for rec in initial_recs:
            rid = rec.get('id')
            if rid:
                reccobeats_ids.append(rid)
                
                spotify_url = rec.get('href', '')
                spotify_id = self.extract_spotifyID_from_url(spotify_url)
                track_id_to_use = spotify_id if spotify_id else rid
                
                rec_map[rid] = {
                    'track_title': rec.get('trackTitle', 'Unknown'),
                    'artists': ', '.join([a.get('name', 'Unknown') for a in rec.get('artists', [])]),
                    'spotify_url': spotify_url,
                    'spotify_track_id': track_id_to_use,
                    'popularity': rec.get('popularity', 0)  # Reccobeats 0-100
                }
        
        return reccobeats_ids, rec_map

    
    def get_enhanced_recommendations(
        self, 
        spotify_track_id: str,
        initial_recommendations_count: int = 100,
        final_recommendations_count: int = 6,
        original_features: Optional[Dict] = None,
        **filters) -> List[Dict]:
        """
        Get enhanced recommendations using K-NN filtering.
        """
        try:
            if original_features:
                features = original_features
            else:
                features, _= self.get_audio_features(spotify_track_id)
                if not features:
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
            
            # 3. Process metadata & extract IDs from
            reccobeats_ids, rec_map = self.rec_metadata(initial_recs)

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

            # 6. Run K-NN
            vectors = np.array([original_vector] + [r['feature_vector'] for r in recs_with_features])
            knn, scaled_vectors, _= train_knn(vectors, n_neighbors=final_recommendations_count + 1)

            distances, indices= knn.kneighbors(scaled_vectors[0:1])
            
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

    def get_valid_recommendations(
        self,
        spotify_track_id: str,
        final_recommendations_count: int = 6,
        og_feature: Optional[Dict] = None,
        min_similarity: float = 0.7,
        **filters
    ) -> List[Dict]:
        """
        Wrapper around get_enhanced_recommendations that retries with
        different popularity tiers until final_recommendations_count
        songs above min_similarity are collected.
        """
        qualified_recs = []
        seen_track_ids = set()
        
        popularity_tiers = [100,90,80,70,60,50,40,30,20,10,100,90,80,70,60,50,40,30,20,10]
        
        for round_num, pop_value in enumerate(popularity_tiers):
            if len(qualified_recs) >= final_recommendations_count:
                break
            
            # Build filters for this round
            round_filters = dict(filters)
            if pop_value is not None:
                round_filters['popularity'] = pop_value
            
            recs = self.get_enhanced_recommendations(
                spotify_track_id=spotify_track_id,
                initial_recommendations_count=100,
                final_recommendations_count=6,  # fetch more, we'll filter
                original_features=og_feature,
                **round_filters
            )
            
            if not recs:
                continue
            
            new_this_round = 0
            for rec in recs:
                if rec['track_id'] in seen_track_ids:
                    continue
                
                seen_track_ids.add(rec['track_id'])
                
                if rec['similarity_score'] >= min_similarity:
                    qualified_recs.append(rec)
                    new_this_round += 1
            
            pop_label = f"popularity={pop_value}" if pop_value is not None else "no filter"
            print(f"Round {round_num + 1} ({pop_label}): {len(qualified_recs)}/{final_recommendations_count} qualified (>= {min_similarity*100:.0f}%)")
        
        qualified_recs.sort(key=lambda x: x['similarity_score'], reverse=True)
        return qualified_recs[:final_recommendations_count]

        
class CollaborativeFilteringEngine:
    """
    Item-based CF using chart co-occurrence and popularity similarity.
    
    CSV format: title, artist, total_popularity_weight, spotify_id
    
    total_popularity_weight is normalised to a 0-100 scale (popularity_100)
    where 100 = the maximum weight in the dataset.  This matches the Reccobeats
    API popularity parameter (0-100) so CF and CBF scores are directly
    comparable and blendable.
    """
    
    def __init__(self, csv_path: str = "final_charts_updated.csv"):
        self.csv_path = csv_path
        self._charts_df = None
        self._spotify_id_set = None
        self._knn_model = None
        self._scaler = None
        self._sorted_df = None
        self._track_index_map = None
    
    # ---- lazy-loaded properties ----
    
    @property
    def charts_df(self) -> pd.DataFrame:
        if self._charts_df is None:
            self._charts_df = self._load_charts()
        return self._charts_df
    
    @property
    def spotify_id_set(self) -> set:
        if self._spotify_id_set is None:
            self._spotify_id_set = set(self.charts_df['spotify_id'].dropna().unique())
        return self._spotify_id_set
    
    # ---- data loading ----
    
    def _load_charts(self) -> pd.DataFrame:
        """Load charts CSV and normalise popularity to 0-100."""
        try:
            df = pd.read_csv(self.csv_path)
            max_pop = df['total_popularity_weight'].max()
            # Normalise to 0-100 (same scale as Reccobeats popularity parameter)
            df['popularity_100'] = (
                (df['total_popularity_weight'] / max_pop * 100.0) if max_pop > 0 else 0
            )
            return df
        except FileNotFoundError:
            print(f"Charts CSV not found at {self.csv_path}")
            return pd.DataFrame(columns=[
                'title', 'artist', 'total_popularity_weight', 'spotify_id', 'popularity_100'
            ])
        except Exception as e:
            print(f"Error loading charts CSV: {e}")
            return pd.DataFrame(columns=[
                'title', 'artist', 'total_popularity_weight', 'spotify_id', 'popularity_100'
            ])
    
    # ---- lookup helpers ----
    
    def is_in_charts(self, spotify_track_id: str) -> bool:
        return spotify_track_id in self.spotify_id_set
    
    def get_chart_popularity_100(self, spotify_track_id: str) -> Optional[float]:
        """Return the 0-100 normalised popularity, or None if not in charts."""
        row = self.charts_df.loc[self.charts_df['spotify_id'] == spotify_track_id]
        if row.empty:
            return None
        return float(row.iloc[0]['popularity_100'])
    
    # ---- similarity model ----
    def _build_knn(self):
        """Build item-item KNN based on chart popularity proximity."""
        df = self.charts_df
        if df.empty:
            return
        
        df_sorted = df.sort_values('total_popularity_weight', ascending=False).reset_index(drop=True)

        feature_matrix = df_sorted[['popularity_100']].values
        knn, _, scaler = train_knn(feature_matrix, n_neighbors=50)

        self._knn_model = knn
        self._scaler = scaler
        self._sorted_df = df_sorted
        self._track_index_map = {
            row['spotify_id']: idx
            for idx, row in df_sorted.iterrows()
            if pd.notna(row['spotify_id'])
        }
    
    # ---- CF recommendations ----
    
    def get_cf_recommendations(
        self,
        favourite_spotify_ids: List[str],
        k: int = 6
    ) -> List[Dict]:
        """
        For each favourite in charts, find similar chart items by popularity return top-k.
        
        Uses popularity_100 (0-100) — same scale as Reccobeats popularity.
        """
        df = self.charts_df
        if df.empty:
            return []
        
        fav_in_charts = [fid for fid in favourite_spotify_ids if self.is_in_charts(fid)]
        if not fav_in_charts:
            return []
        
        if self._knn_model is None:
            self._build_knn()
        if self._knn_model is None:
            return []
        
        candidate_scores: Dict[str, float] = {}
        
        for fav_id in fav_in_charts:
            if fav_id not in self._track_index_map:
                continue
            
            idx = self._track_index_map[fav_id]
            row_features = self._sorted_df.iloc[idx][['popularity_100']].values.reshape(1, -1)
            scaled_query = self._scaler.transform(row_features)
            
            n_neighbors = min(20, len(self._sorted_df))
            distances, indices = self._knn_model.kneighbors(scaled_query, n_neighbors=n_neighbors)
            
            for dist, neighbor_idx in zip(distances[0], indices[0]):
                neighbor_row = self._sorted_df.iloc[neighbor_idx]
                neighbor_id = neighbor_row['spotify_id']
                
                if pd.isna(neighbor_id) or neighbor_id in favourite_spotify_ids:
                    continue
                
                similarity = 1 - dist
                # Blend cosine similarity with normalised popularity (pop/100 → 0-1)
                pop_01 = neighbor_row['popularity_100'] / 100.0
                score = (0.7 * similarity) + (0.3 * pop_01)
                
                if neighbor_id not in candidate_scores or score > candidate_scores[neighbor_id]:
                    candidate_scores[neighbor_id] = score
        
        sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for spotify_id, score in sorted_candidates[:k]:
            row = df[df['spotify_id'] == spotify_id].iloc[0]
            results.append({
                'track_id': spotify_id,
                'track_name': row['title'],
                'artists': row['artist'],
                'similarity_score': float(min(score, 1.0)),
                'popularity': float(row['popularity_100']),  # 0-100 scale
                'source': 'cf'
            })
        
        return results
    
    def get_popular_tracks(self, k: int = 6, exclude_ids: set = None) -> List[Dict]:
        """Cold-start fallback: top popular tracks from charts."""
        df = self.charts_df
        if df.empty:
            return []
        
        if exclude_ids:
            df = df[~df['spotify_id'].isin(exclude_ids)]
        
        top = df.nlargest(k, 'total_popularity_weight')
        return [
            {
                'track_id': row['spotify_id'],
                'track_name': row['title'],
                'artists': row['artist'],
                'similarity_score': float(row['popularity_100'] / 100.0),
                'popularity': float(row['popularity_100']),
                'source': 'popular'
            }
            for _, row in top.iterrows()
            if pd.notna(row['spotify_id'])
        ]
    
    def get_artist_recommendations(
        self,
        artist_names: List[str],
        exclude_titles: set = None
    ) -> List[Dict]:
        """
        For each artist, return their most popular chart track (1 per artist).
        Skips artists not found in charts and tracks already in exclude_ids.
        """
        df = self.charts_df
        if df.empty:
            return []
        
        
        exclude_titles_set = exclude_titles if exclude_titles else set()
        results = []
        seen_artists = set()
        
        for artist_name in artist_names:
            # Normalise for case-insensitive matching
            artist_lower = artist_name.strip().lower()
            if artist_lower in seen_artists:
                continue
            seen_artists.add(artist_lower)
            
            # Find all tracks by this artist in the charts
            artist_tracks = df[df['artist'].str.lower().str.strip() == artist_lower]
            if artist_tracks.empty:
                continue       

            
            # Also exclude by title match against existing recommendations
            if exclude_titles_set:
                artist_tracks = artist_tracks[~artist_tracks['title'].str.strip().str.lower().isin(exclude_titles)]           
            if artist_tracks.empty:
                continue
            
            # Pick the most popular track by this artist
            random_track = artist_tracks.sample(n=1).iloc[0]
            
            if pd.notna(random_track['spotify_id']):
                results.append({
                    'track_id': random_track['spotify_id'],
                    'track_name': random_track['title'],
                    'artists': random_track['artist'],
                    'similarity_score': float(random_track['popularity_100'] / 100.0),
                    'popularity': float(random_track['popularity_100']),
                    'source': 'artist'
            })
                # Also exclude this track so the next artist can't pick it
                exclude_titles.add(random_track['title'].strip().lower())
        
        return results
    
# =============================================================================
# DYNAMIC ALPHA
# =============================================================================

def dynamic_alpha(
    user_favourites: List[Dict],
    charts_engine: CollaborativeFilteringEngine,
    k: int = 10
) -> float:
    """
    Calculate alpha based on how many favourites are in charts data.
    
    alpha ≈ 0.9  → heavy CF weight (most favourites in charts)
    alpha = 0.0  → pure CBF        (no favourites in charts)
    """
    if not user_favourites:
        return 0.0
    
    in_charts_count = sum(
        1 for f in user_favourites
        if charts_engine.is_in_charts(f.get('track_id', ''))
    )
    total_favourites = len(user_favourites)
    
    confidence_ratio = in_charts_count / total_favourites if total_favourites > 0 else 0
    
    alpha = confidence_ratio * 0.9
    alpha = min(alpha, (k / 30) * 0.9)
    
    return alpha

# =============================================================================
# CBF TASTE-PROFILE RECOMMENDER
# =============================================================================

def get_cbf_recommendations_from_favourites(
    user_favourites: List[Dict],
    k: int = 6,
    exclude_ids: set = None
) -> List[Dict]:
    """
    Scoring uses the same formula as the song-page CBF:
      weighted = 0.9 * cosine_similarity + 0.1 * (reccobeats_popularity / 100)
    """
    if not user_favourites:
        return []
    
    api = ReccobeatsAPI()
    
    feature_keys = [
        'danceability', 'energy', 'valence', 'tempo', 'loudness',
        'acousticness', 'instrumentalness', 'liveness', 'speechiness',
        'key', 'mode'
    ]

    fav_features = []
    fav_ids_for_seeds = []
    
    for fav in user_favourites:
        track_id = fav.get('track_id', '')
        if not track_id:
            continue
        features, _ = api.get_audio_features(track_id)
        if features:
            fav_features.append(api.extract_audio_features_vector(features))
            fav_ids_for_seeds.append(track_id)
    
    if not fav_features:
        return []
    
    # 2. Average into taste profile
    taste_profile = {}
    for key in feature_keys:
        values = [f[key] for f in fav_features if key in f and f[key] is not None]
        if values:
            taste_profile[key] = sum(values) / len(values)
    
    # 3. Seed recommendations from up to 3 favourites
    seed_ids = fav_ids_for_seeds[:3]
    seen_ids = set(exclude_ids) if exclude_ids else set()
    seen_ids.update(f.get('track_id', '') for f in user_favourites)
    
    all_recs = []
    
    for seed_id in seed_ids:
        try:
            recs = api.get_enhanced_recommendations(
                spotify_track_id=seed_id,
                initial_recommendations_count=100,
                final_recommendations_count=k,
                original_features=taste_profile
            )
            if recs:
                for rec in recs:
                    if rec['track_id'] not in seen_ids:
                        seen_ids.add(rec['track_id'])
                        rec['source'] = 'cbf'
                        all_recs.append(rec)
        except Exception as e:
            print(f"CBF seed error for {seed_id}: {e}")
    
    # 4. Sort by similarity score and return top k
    all_recs.sort(key=lambda x: x['similarity_score'], reverse=True)
    return all_recs[:k]
    
# =============================================================================
# HYBRID RECOMMENDATION MERGER  ("For You" page)
# =============================================================================

def get_hybrid_recommendations_for_user(
    user_favourites: List[Dict],
    charts_csv_path: str = "final_charts_updated.csv",
    k: int = 6
) -> Tuple[List[Dict], float, Dict]:
    """
    Main entry point for the "For You"  on the search page.
    
    1. Compute dynamic alpha from favourites ↔ charts overlap.
    2. Allocate round(alpha × k) slots to CF, remainder to CBF.
    3. CF: item-based chart similarity (popularity_100 on 0-100 scale).
    4. CBF: taste-profile KNN seeded from favourites,
       using Reccobeats popularity (0-100) in the scoring formula.
    5. Merge, deduplicate, pad with popular tracks if needed.
    
    Returns (recommendations, alpha, debug_info).
    """
    cf_engine = CollaborativeFilteringEngine(charts_csv_path)
    
    # Cold start
    if not user_favourites:
        popular = cf_engine.get_popular_tracks(k=k)
        return popular, 0.0, {'mode': 'cold_start', 'cf_count': 0, 'cbf_count': 0}
    
    # --- dynamic alpha ---
    alpha = dynamic_alpha(user_favourites, cf_engine, k=k)
    
    fav_ids = {f.get('track_id', '') for f in user_favourites}
    
    debug_info = {
        'alpha': alpha,
        'total_favourites': len(user_favourites),
        'in_charts': sum(
            1 for f in user_favourites if cf_engine.is_in_charts(f.get('track_id', ''))
        ),
    }
    
    cf_count = round(alpha * k)
    
    # --- CF ---
    cf_recs = []
    if cf_count > 0:
        fav_spotify_ids = [f.get('track_id', '') for f in user_favourites]
        cf_recs = cf_engine.get_cf_recommendations(fav_spotify_ids, k=cf_count)
    debug_info['cf_returned'] = len(cf_recs)
    
    # --- CBF (fill remaining slots) ---
    cf_track_ids = {r['track_id'] for r in cf_recs}
    exclude = fav_ids | cf_track_ids
    cbf_needed = k - len(cf_recs)
    
    cbf_recs = []
    if cbf_needed > 0:
        cbf_recs = get_cbf_recommendations_from_favourites(
            user_favourites, k=cbf_needed, exclude_ids=exclude
        )
    debug_info['cbf_returned'] = len(cbf_recs)
    
    # --- Merge ---
    merged = cf_recs + cbf_recs

     # --- Artist bonus: 1 song per unique favourite artist from charts ---
    all_rec_ids = {r['track_id'] for r in merged} | fav_ids
    fav_artists = list(dict.fromkeys(
        f.get('artist_name', '') for f in user_favourites if f.get('artist_name', '')
    ))  # unique artists, preserving order
    # make sure favourite tracks are not recommended 
    fav_tracks = {f.get('track_name', '').strip().lower() for f in user_favourites}

    artist_recs = cf_engine.get_artist_recommendations(
        fav_artists, 
        exclude_titles=fav_tracks)
    merged.extend(artist_recs)
    
    debug_info['mode'] = 'hybrid' if cf_count > 0 else 'cbf_only'
    debug_info['cf_count'] = len(cf_recs)
    debug_info['cbf_count'] = len(cbf_recs)
    return merged, alpha, debug_info

# --- EXPORTED FUNCTIONS ---

def get_audio_features_with_fallback(spotify_track_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Convenience function to get audio features."""
    api = ReccobeatsAPI()
    return api.get_audio_features(spotify_track_id)

def get_recommendations_from_features(
    features_dict: Dict,
    track_id: str = None,
    dataset_path: str = None,
    k: int = 6  
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
        final_recommendations_count=k,
        original_features= features_dict if features_dict else None
    )

def valid_recommendations(
        features_dict: Dict,
        spotify_track_id: str = None,
        dataset_path: str = None,
        k: int = 6
) -> List[Dict]:
    if not spotify_track_id:
        return []
    
    api = ReccobeatsAPI()
    return api.get_valid_recommendations(
        spotify_track_id,
        og_feature = features_dict if features_dict else None
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
        batch_features = []
    
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
        initial_recommendations_count=40,
        final_recommendations_count=6,
        min_similarity= 0.7
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

def test_hybrid_cold_start():
    """Test Case 1: Zero favourites → cold start (popular tracks from CSV)."""
    print("=" * 60)
    print("Test Case 1: Hybrid Recommendations – ZERO Favourites (Cold Start)")
    print("=" * 60)

    user_favourites = []

    recommendations, alpha, debug_info = get_hybrid_recommendations_for_user(
        user_favourites,
        charts_csv_path="final_charts_updated.csv",
        k=6
    )

    print(f"\n📊 Debug Info:")
    print(f"   Mode:            {debug_info.get('mode')}")
    print(f"   Alpha:           {alpha:.3f}")
    print(f"   Total favourites: {debug_info.get('total_favourites', 0)}")
    print(f"   In charts:       {debug_info.get('in_charts', 0)}")
    print(f"   CF count:        {debug_info.get('cf_count', 0)}")
    print(f"   CBF count:       {debug_info.get('cbf_count', 0)}")

    if recommendations:
        print(f"\n✅ Got {len(recommendations)} recommendations (expected: popular tracks)")
        print("-" * 40)
        for i, rec in enumerate(recommendations, 1):
            match_pct = rec['similarity_score'] * 100
            print(f"\n{i}. {rec['track_name']}")
            print(f"   Artists:    {rec['artists']}")
            print(f"   Match:      {match_pct:.1f}%")
            print(f"   Popularity: {rec.get('popularity', 'N/A')}")
            print(f"   Source:     {rec.get('source', 'N/A')}")
            print(f"   Track ID:   {rec['track_id']}")
    else:
        print("\n❌ No recommendations returned")

    # Assertions
    assert alpha == 0.0, f"Expected alpha=0.0 for no favourites, got {alpha}"
    assert debug_info['mode'] == 'cold_start', f"Expected cold_start mode, got {debug_info['mode']}"
    assert debug_info['cf_count'] == 0, "CF should be 0 with no favourites"
    assert debug_info['cbf_count'] == 0, "CBF should be 0 with no favourites"
    if recommendations:
        for rec in recommendations:
            assert rec.get('source') == 'popular', f"Cold start recs should all be 'popular', got {rec.get('source')}"

    print("\n✅ All assertions passed for cold start test")
    print("=" * 60)
    return recommendations, alpha, debug_info


def test_hybrid_with_favourites():
    """Test Case 2: Two favourites → hybrid or CBF-only depending on chart overlap."""
    print("=" * 60)
    print("Test Case 2: Hybrid Recommendations – TWO Favourites")
    print("=" * 60)

    # Simulate favourites as stored by auth.py
    user_favourites = [
        {
            'track_id': '2n1MTLCis6qPSDKdr5XSDI',
            'track_name': 'Test Track 1',
            'artist_name': 'Artist 1',
            'album_name': 'Album 1',
            'album_image': None,
        },
        {
            'track_id': '045sp2JToyTaaKyXkGejPy',
            'track_name': 'Test Track 2',
            'artist_name': 'Artist 2',
            'album_name': 'Album 2',
            'album_image': None,
        },
    ]

    # Check which favourites are in the charts
    cf_engine = CollaborativeFilteringEngine("final_charts_updated.csv")
    print("\n🔍 Checking favourites against charts CSV:")
    for fav in user_favourites:
        tid = fav['track_id']
        in_charts = cf_engine.is_in_charts(tid)
        pop = cf_engine.get_chart_popularity_100(tid)
        print(f"   {tid} → in_charts={in_charts}, popularity_100={pop}")

    # Run hybrid
    recommendations, alpha, debug_info = get_hybrid_recommendations_for_user(
        user_favourites,
        charts_csv_path="final_charts_updated.csv",
        k=6
    )

    print(f"\n📊 Debug Info:")
    print(f"   Mode:            {debug_info.get('mode')}")
    print(f"   Alpha:           {alpha:.3f}")
    print(f"   Total favourites: {debug_info.get('total_favourites', 0)}")
    print(f"   In charts:       {debug_info.get('in_charts', 0)}")
    print(f"   CF returned:     {debug_info.get('cf_returned', 0)}")
    print(f"   CBF returned:    {debug_info.get('cbf_returned', 0)}")
    print(f"   CF count:        {debug_info.get('cf_count', 0)}")
    print(f"   CBF count:       {debug_info.get('cbf_count', 0)}")

    if recommendations:
        print(f"\n✅ Got {len(recommendations)} hybrid recommendations")
        print("-" * 40)
        for i, rec in enumerate(recommendations, 1):
            match_pct = rec['similarity_score'] * 100
            print(f"\n{i}. {rec['track_name']}")
            print(f"   Artists:    {rec['artists']}")
            print(f"   Match:      {match_pct:.1f}%")
            print(f"   Popularity: {rec.get('popularity', 'N/A')}")
            print(f"   Source:     {rec.get('source', 'N/A')}")
            print(f"   Track ID:   {rec['track_id']}")
    else:
        print("\n❌ No recommendations returned")

    # Assertions
    in_charts = debug_info.get('in_charts', 0)
    assert debug_info['total_favourites'] == 2, "Should have 2 favourites"

    if in_charts == 0:
        assert alpha == 0.0, f"Alpha should be 0 when no favourites in charts, got {alpha}"
        assert debug_info['mode'] == 'cbf_only', f"Expected cbf_only, got {debug_info['mode']}"
        assert debug_info['cf_count'] == 0, "CF should be 0 when no overlap"
        print("\n📝 No favourites in charts → pure CBF mode (as expected)")
    else:
        assert alpha > 0.0, f"Alpha should be > 0 with {in_charts} favourites in charts"
        assert debug_info['mode'] == 'hybrid', f"Expected hybrid, got {debug_info['mode']}"
        assert debug_info['cf_count'] > 0, "CF should contribute in hybrid mode"
        print(f"\n📝 {in_charts}/2 favourites in charts → hybrid mode (α={alpha:.3f})")

    # No recommendation should be one of the favourites
    fav_ids = {f['track_id'] for f in user_favourites}
    for rec in recommendations:
        assert rec['track_id'] not in fav_ids, \
            f"Recommendation {rec['track_id']} should not be a favourite"

    print("\n✅ All assertions passed for favourites test")
    print("=" * 60)
    return recommendations, alpha, debug_info


def test_artist_recommendations():
    """
    Test the get_artist_recommendations function with Radiohead's "Creep".
    Checks if it can identify Radiohead in the charts and return other songs by the artist.
    """
    print("=" * 60)
    print("Testing Artist Recommendations for Radiohead")
    print("=" * 60)
    
    # Initialize the CF engine
    cf_engine = CollaborativeFilteringEngine("final_charts_updated.csv")
    
    # Test track: "Creep" by Radiohead
    test_spotify_id = "6b2oQwSGFkzsMtQruIWm2p"
    test_artist = "Radiohead"
    test_track_name = "Creep"
    
    print(f"\n🎵 Test Track: {test_track_name} by {test_artist}")
    print(f"   Spotify ID from CSV: {test_spotify_id}")
    print("-" * 40)
    
    # First, let's see what's actually in the CSV
    print("\n📊 Checking what's in the charts dataset...")
    all_radiohead = cf_engine.charts_df[
        cf_engine.charts_df['artist'].str.lower().str.strip() == 'radiohead'
    ]
    
    if not all_radiohead.empty:
        print(f"\n✅ Found {len(all_radiohead)} Radiohead tracks in charts:")
        for _, row in all_radiohead.iterrows():
            print(f"   • {row['title']} (ID: {row['spotify_id']})")
    else:
        print("❌ No Radiohead tracks found in charts")
        return
    
    print("\n" + "-" * 40)
    print(f"📊 Test 1: Checking if '{test_track_name}' is in charts dataset...")
    
    # Check by title and artist
    creep_track = cf_engine.charts_df[
        (cf_engine.charts_df['title'].str.lower().str.strip() == test_track_name.lower()) &
        (cf_engine.charts_df['artist'].str.lower().str.strip() == test_artist.lower())
    ]
    
    if not creep_track.empty:
        print(f"   ✅ Track found in charts dataset!")
        test_spotify_id = creep_track.iloc[0]['spotify_id']
        test_track_name = creep_track.iloc[0]['title']
        popularity = cf_engine.get_chart_popularity_100(test_spotify_id)
        print(f"   📈 Popularity score (0-100): {popularity:.2f}")
        print(f"   📝 Track title: '{test_track_name}'")
    else:
        print(f"   ❌ Track is NOT in the charts dataset")
        print(f"   ⚠️  Skipping remaining tests as prerequisite failed")
        return
    
    print("\n" + "-" * 40)
    print("📊 Test 2: Getting artist recommendations for Radiohead (excluding by title)")
    print("-" * 40)
    
    # Test 2: Get artist recommendations - exclude the test track by title
    artist_recs = cf_engine.get_artist_recommendations(
        artist_names=[test_artist],
        exclude_titles={test_track_name}  # Exclude Creep by title
    )
    
    if artist_recs:
        print(f"\n✅ Found {len(artist_recs)} Radiohead songs in the charts (excluding '{test_track_name}'):")
        print("-" * 40)
        
        for i, rec in enumerate(artist_recs, 1):
            print(f"\n{i}. {rec['track_name']}")
            print(f"   Artist: {rec['artists']}")
            print(f"   Track ID: {rec['track_id']}")
            print(f"   Popularity (0-100): {rec['popularity']:.2f}")
            print(f"   Similarity score: {rec['similarity_score']:.3f}")
            print(f"   Source: {rec.get('source', 'N/A')}")
            
            # Verify it's actually by Radiohead
            assert rec['artists'].lower() == test_artist.lower(), \
                f"Expected artist '{test_artist}', got '{rec['artists']}'"
            
            # Verify it's not the test track
            assert rec['track_name'].lower() != test_track_name.lower(), \
                f"Should not return the same track ({test_track_name}) as recommendation"
    else:
        print(f"\n❌ No other Radiohead songs found besides '{test_track_name}'")
    
    print("\n" + "-" * 40)
    print("📊 Test 3: Testing with multiple artists including duplicates")
    print("-" * 40)
    
    # Test 3: Test with multiple artists and duplicates
    test_artists = ["Radiohead", "radiohead", "RADIOHEAD", "Radiohead", "The Beatles"]
    print(f"Testing with artists list: {test_artists}")
    
    multi_recs = cf_engine.get_artist_recommendations(
        artist_names=test_artists,
        exclude_titles={test_track_name}  # Exclude Creep
    )
    
    if multi_recs:
        print(f"\n✅ Found {len(multi_recs)} unique artist recommendations:")
        
        # Count artists in results
        artist_counts = {}
        for rec in multi_recs:
            artist = rec['artists'].lower()
            artist_counts[artist] = artist_counts.get(artist, 0) + 1
        
        print("\nBreakdown by artist:")
        for artist, count in artist_counts.items():
            print(f"   {artist}: {count} track(s)")
        
        # Verify no duplicate artists (should be 1 per unique artist)
        assert len(multi_recs) >= 1, "Should have at least 1 recommendation"
        
        # Check if Radiohead appears multiple times (should not)
        radiohead_count = sum(1 for rec in multi_recs if rec['artists'].lower() == 'radiohead')
        print(f"\nRadiohead tracks returned: {radiohead_count} (should be 1)")
        assert radiohead_count <= 1, "Should only return 1 track per unique artist"
        
        # Check if Beatles appears
        beatles_count = sum(1 for rec in multi_recs if rec['artists'].lower() == 'the beatles')
        if beatles_count > 0:
            print(f"Beatles tracks returned: {beatles_count}")
    else:
        print("\n❌ No recommendations found for the artist list")
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    # Summary
    print(f"\n📊 Charts dataset stats:")
    print(f"   Total tracks in charts: {len(cf_engine.charts_df)}")
    print(f"   Total unique artists: {cf_engine.charts_df['artist'].nunique()}")
    
    # Count Radiohead tracks in charts
    radiohead_tracks = cf_engine.charts_df[
        cf_engine.charts_df['artist'].str.lower().str.strip() == 'radiohead'
    ]
    print(f"   Radiohead tracks in charts: {len(radiohead_tracks)}")
    
    if len(radiohead_tracks) > 0:
        print("\n📝 All Radiohead tracks in charts:")
        for _, row in radiohead_tracks.iterrows():
            print(f"   • {row['title']} (popularity: {row['popularity_100']:.1f})")
    
    return artist_recs, multi_recs

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING RECCOBEATS API WITH BATCH PROCESSING")
    print("="*80)
    
    # # Test batch audio features
    # test_batch_audio_features()
    
    # # Test enhanced recommendations with batch processing
    test_enhanced_recommendations_with_batch()

    # #Test hybrid recommendations
    # test_hybrid_cold_start()
    # test_hybrid_with_favourites()

    # # test favourite artists recomendation
    # test_artist_recommendations()


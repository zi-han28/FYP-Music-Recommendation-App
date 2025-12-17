# genius_api.py
"""
Genius API integration for fetching song lyrics.
"""

import os
import re  # Import regex module at the top
from typing import Optional, Dict
import lyricsgenius
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GeniusAPI:
    def __init__(self):
        self.access_token = os.getenv("GENIUS_CLIENT_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("GENIUS_CLIENT_ACCESS_TOKEN not found in environment variables")
        
        self.genius = lyricsgenius.Genius(
            self.access_token,
            # Configuration options
            remove_section_headers=True,
            skip_non_songs=True,
            excluded_terms=["(Remix)", "(Live)", "(Demo)", "(Acoustic)", "(Cover)"],
            timeout=10,
            retries=3
        )
        self.genius.verbose = False  # Disable verbose logging
        self.genius.remove_section_headers = True  # Remove [Chorus], [Verse], etc.
    
    def get_lyrics(self, track_name: str, artist_name: str) -> Optional[str]:
        """
        Search for and retrieve lyrics for a specific track.
        
        Args:
            track_name: Name of the track
            artist_name: Name of the artist
            
        Returns:
            Lyrics text or None if not found
        """
        try:
            # Clean up the track name (remove featured artists, versions, etc.)
            clean_track_name = self._clean_track_name(track_name)
            
            # Search for the song
            song = self.genius.search_song(title=clean_track_name, artist=artist_name)
            
            if song and song.lyrics:
                return self._clean_lyrics(song.lyrics)
            
            # If not found, try with original track name
            song = self.genius.search_song(title=track_name, artist=artist_name)
            if song and song.lyrics:
                return self._clean_lyrics(song.lyrics)
            
            return None
            
        except Exception as e:
            print(f"Error fetching lyrics for {track_name} by {artist_name}: {e}")
            return None
    
    def _clean_track_name(self, track_name: str) -> str:
        """Remove common suffixes and features from track names."""
        # Remove text in parentheses and brackets
        cleaned = re.sub(r'\([^)]*\)', '', track_name)  # Remove (feat. ...)
        cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)    # Remove [feat. ...]
        cleaned = re.sub(r'- .*$', '', cleaned)         # Remove - Radio Edit, etc.
        
        # Remove common suffixes
        suffixes = [
            " - Radio Edit",
            " - Single Version",
            " - Album Version",
            " - Remastered",
            " - Remaster",
            " (Remastered)",
            " (Remaster)",
            " (Single Version)",
            " (Album Version)",
            " (Radio Edit)",
            " (Clean)",
            " (Explicit)",
            " (Official Video)",
            " (Official Audio)",
            " (Music Video)",
            " (Visualizer)",
            " (Lyric Video)"
        ]
        
        for suffix in suffixes:
            cleaned = cleaned.replace(suffix, "")
        
        return cleaned.strip()
    
    def _clean_lyrics(self, lyrics: str) -> str:
        """Clean up lyrics by removing unwanted text."""
        if not lyrics:
            return ""
            
        # Split lyrics into lines
        lines = lyrics.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip lines with these phrases
            skip_phrases = [
                "Lyrics", 
                "You might also like",
                "Embed",
                "Contributors",
                "Translations",
                "See Radiohead Live",
                "Get tickets as low as",
                "Thanks to",
                "for adding these lyrics"
            ]
            
            if any(phrase in line for phrase in skip_phrases):
                continue
            
            # Skip empty lines at the beginning of sections
            if not cleaned_lines and not line.strip():
                continue
                
            cleaned_lines.append(line)
        
        # Join back with line breaks
        result = '\n'.join(cleaned_lines)
        
        # Remove multiple empty lines (3 or more consecutive newlines)
        result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)
        
        return result.strip()
    
    def get_lyrics_with_info(self, track_name: str, artist_name: str) -> Dict:
        """
        Get lyrics along with additional information.
        
        Returns:
            Dictionary with lyrics and metadata
        """
        try:
            # Clean up the track name
            clean_track_name = self._clean_track_name(track_name)
            
            # Search for the song
            song = self.genius.search_song(title=clean_track_name, artist=artist_name)
            
            if not song:
                # Try with original track name
                song = self.genius.search_song(title=track_name, artist=artist_name)
            
            if song and song.lyrics:
                # Get metadata safely (some attributes might not exist)
                result = {
                    'lyrics': self._clean_lyrics(song.lyrics),
                    'title': getattr(song, 'title', track_name),
                    'artist': getattr(song, 'artist', artist_name),
                    'url': getattr(song, 'url', f"https://genius.com/search?q={track_name.replace(' ', '+')}+{artist_name.replace(' ', '+')}"),
                    'thumbnail': getattr(song, 'song_art_image_url', None)
                }
                
                # Try to get album info if available
                try:
                    result['album'] = getattr(song, 'album', None)
                except:
                    result['album'] = None
                
                # Try to get release year if available
                try:
                    result['release_date'] = getattr(song, 'release_date', None)
                    # If release_date is not available, try to get year from other attributes
                    if not result['release_date']:
                        result['release_date'] = getattr(song, 'release_date_for_display', None)
                except:
                    result['release_date'] = None
                
                return result
            
            return {'lyrics': None, 'error': 'Lyrics not found'}
            
        except Exception as e:
            print(f"Error in get_lyrics_with_info: {e}")
            return {'lyrics': None, 'error': str(e)}


# Singleton instance
_genius_api = None

def get_genius_api() -> GeniusAPI:
    """Get or create Genius API instance."""
    global _genius_api
    if _genius_api is None:
        try:
            _genius_api = GeniusAPI()
        except Exception as e:
            print(f"Failed to initialize Genius API: {e}")
            return None
    return _genius_api


def get_lyrics(track_name: str, artist_name: str) -> Optional[str]:
    """Convenience function to get lyrics."""
    genius = get_genius_api()
    if genius:
        return genius.get_lyrics(track_name, artist_name)
    return None


def get_lyrics_with_info(track_name: str, artist_name: str) -> Dict:
    """Convenience function to get lyrics with info."""
    genius = get_genius_api()
    if genius:
        return genius.get_lyrics_with_info(track_name, artist_name)
    return {'lyrics': None, 'error': 'Genius API not initialized'}


# For testing
if __name__ == "__main__":
    # Test with a known song
    lyrics_info = get_lyrics_with_info("Creep", "Radiohead")
    if lyrics_info.get('lyrics'):
        print("Lyrics found!")
        print(f"Title: {lyrics_info.get('title')}")
        print(f"Artist: {lyrics_info.get('artist')}")
        print(f"URL: {lyrics_info.get('url')}")
        print(f"Album: {lyrics_info.get('album')}")
        print(f"Release Date: {lyrics_info.get('release_date')}")
        print("\nFirst 300 characters of lyrics:")
        print(lyrics_info['lyrics'][:300])
    else:
        print(f"No lyrics found. Error: {lyrics_info.get('error')}")
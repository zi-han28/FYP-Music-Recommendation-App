# genius_api.py
import os
import re
from typing import Optional, Dict
import requests as http_requests
import lyricsgenius
from dotenv import load_dotenv

try:
    import bs4
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    from unidecode import unidecode
except ImportError:
    def unidecode(s):
        return s

# Load environment variables
load_dotenv()


class GeniusAPI:
    def __init__(self):
        self.access_token = os.getenv("GENIUS_CLIENT_ACCESS_TOKEN")
        self.genius = None
        self.api_available = False
        
        if self.access_token:
            try:
                self.genius = lyricsgenius.Genius(
                    self.access_token,
                    remove_section_headers=True,
                    skip_non_songs=True,
                    excluded_terms=["(Remix)", "(Live)", "(Demo)", "(Acoustic)", "(Cover)"],
                    timeout=10,
                    retries=3
                )
                self.genius.verbose = False
                self.genius.remove_section_headers = True
                self.api_available = True
                print("Genius API initialized with access token.")
            except Exception as e:
                print(f"Genius API key failed: {e}. Will use web scraping fallback.")
        else:
            print("No Genius API token found. Using web scraping fallback.")
    
    # --- WEB SCRAPING FALLBACK ---
    
    def _scrape_lyrics(self, track_name: str, artist_name: str) -> Optional[str]:
        """
        Fallback: scrape lyrics directly from Genius website.
        Does not require an API key.
        """
        if not BS4_AVAILABLE:
            print("bs4 not installed — cannot scrape lyrics.")
            return None
        
        try:
            # Normalise artist and title for URL construction
            artist = unidecode(artist_name).lower().replace(" ", "-").replace("'", "")
            title = unidecode(track_name).lower()
            title = re.sub(r"\(.*?\)", "", title).strip()
            title = title.replace(" ", "-").replace("'", "")
            
            url = f"https://genius.com/{artist}-{title}-lyrics"
            print(f"Scraping lyrics from: {url}")
            
            r = http_requests.get(url, timeout=10)
            r.raise_for_status()
            
            soup = bs4.BeautifulSoup(r.text, "html.parser")
            
            # Find all lyrics containers
            containers = soup.find_all(attrs={"data-lyrics-container": "true"})
            if not containers:
                return None
            
            # Extract text from each container
            lyrics_parts = []
            for container in containers:
                # Replace <br> tags with newlines before extracting text
                for br in container.find_all("br"):
                    br.replace_with("\n")
                lyrics_parts.append(container.get_text("\n"))
            
            raw_lyrics = "\n".join(lyrics_parts)
            
            # Clean up multiple blank lines
            cleaned = re.sub(r"\n\n+", "\n\n", raw_lyrics).strip()
            
            if cleaned:
                return self._clean_lyrics(cleaned)
            return None
            
        except Exception as e:
            print(f"Scraping fallback failed for {track_name} by {artist_name}: {e}")
            return None
    
    # --- PRIMARY LYRICS RETRIEVAL ---
    
    def get_lyrics(self, track_name: str, artist_name: str) -> Optional[str]:
        # Try API first if available
        if self.api_available:
            try:
                clean_track_name = self._clean_track_name(track_name)
                song = self.genius.search_song(title=clean_track_name, artist=artist_name)
                
                if song and song.lyrics:
                    return self._clean_lyrics(song.lyrics)
                
                song = self.genius.search_song(title=track_name, artist=artist_name)
                if song and song.lyrics:
                    return self._clean_lyrics(song.lyrics)
                    
            except Exception as e:
                print(f"API error for {track_name} by {artist_name}: {e}")
        
        # Fallback to web scraping
        print(f"Falling back to web scraping for: {track_name} by {artist_name}")
        return self._scrape_lyrics(track_name, artist_name)
    
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
        Tries API first, falls back to web scraping.
        """
        # Try API first if available
        if self.api_available:
            try:
                clean_track_name = self._clean_track_name(track_name)
                song = self.genius.search_song(title=clean_track_name, artist=artist_name)
                
                if not song:
                    song = self.genius.search_song(title=track_name, artist=artist_name)
                
                if song and song.lyrics:
                    result = {
                        'lyrics': self._clean_lyrics(song.lyrics),
                        'title': getattr(song, 'title', track_name),
                        'artist': getattr(song, 'artist', artist_name),
                        'url': getattr(song, 'url', f"https://genius.com/search?q={track_name.replace(' ', '+')}+{artist_name.replace(' ', '+')}"),
                        'thumbnail': getattr(song, 'song_art_image_url', None)
                    }
                    
                    try:
                        result['album'] = getattr(song, 'album', None)
                    except:
                        result['album'] = None
                    
                    try:
                        result['release_date'] = getattr(song, 'release_date', None)
                        if not result['release_date']:
                            result['release_date'] = getattr(song, 'release_date_for_display', None)
                    except:
                        result['release_date'] = None
                    
                    return result
                    
            except Exception as e:
                print(f"API error in get_lyrics_with_info: {e}")
        
        # Fallback to web scraping
        print(f"Falling back to web scraping for: {track_name} by {artist_name}")
        scraped_lyrics = self._scrape_lyrics(track_name, artist_name)
        
        if scraped_lyrics:
            # Build URL for reference
            artist_slug = unidecode(artist_name).lower().replace(" ", "-").replace("'", "")
            title_slug = unidecode(track_name).lower()
            title_slug = re.sub(r"\(.*?\)", "", title_slug).strip().replace(" ", "-").replace("'", "")
            
            return {
                'lyrics': scraped_lyrics,
                'title': track_name,
                'artist': artist_name,
                'url': f"https://genius.com/{artist_slug}-{title_slug}-lyrics",
                'thumbnail': None,
                'album': None,
                'release_date': None
            }
        
        return {'lyrics': None, 'error': 'Lyrics not found via API or web scraping'}


# Singleton instance
_genius_api = None

def get_genius_api() -> GeniusAPI:
    """Get or create Genius API instance. Always succeeds — falls back to scraping if no API key."""
    global _genius_api
    if _genius_api is None:
        _genius_api = GeniusAPI()
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
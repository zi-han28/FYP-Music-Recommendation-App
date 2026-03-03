"""
convert_charts.py (v2 - with resume support)

Reads final_charts.csv, searches Spotify for each title+artist combo,
replaces the spotify_id with the current canonical Spotify track ID,
and writes the result to final_charts_updated.csv.

Features:
    - Resumes from where it left off (reads existing output file)
    - Saves progress every 100 tracks
    - Backs off on rate limits automatically
    - Processes in batches of 1500 per run to avoid daily limits

Usage:
    1. Make sure your .env has SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET
    2. Run: python convert_charts.py
    3. If interrupted, just run again - it resumes automatically
    4. Repeat until all rows are processed
"""

import os
import time
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())

INPUT_CSV = "final_charts.csv"
OUTPUT_CSV = "final_charts_updated.csv"
PROGRESS_FILE = "convert_progress.txt"

# How many tracks to process per run (stay under Spotify rate limits)
BATCH_LIMIT = 10000
SAVE_EVERY = 100


def search_spotify_id(title: str, artist: str, retries: int = 2) -> str:
    """
    Search Spotify for a track by title and artist.
    Returns the Spotify track ID of the best match, or empty string on failure.
    """
    query = f"track:{title} artist:{artist}"

    for attempt in range(retries + 1):
        try:
            results = sp.search(q=query, type="track", limit=5)
            tracks = results["tracks"]["items"]

            if not tracks:
                return ""

            title_lower = title.strip().lower()
            artist_lower = artist.strip().lower()

            # Try exact match first
            for track in tracks:
                track_title = track["name"].strip().lower()
                track_artists = [a["name"].strip().lower() for a in track["artists"]]

                if track_title == title_lower and artist_lower in track_artists:
                    return track["id"]

            # Fall back to first result
            return tracks[0]["id"]

        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 30))
                print(f"\n⚠️  Rate limited! Waiting {retry_after} seconds...")
                time.sleep(retry_after + 1)
                continue
            else:
                print(f"  Spotify error for '{title}' by '{artist}': {e}")
                return ""
        except Exception as e:
            print(f"  Error for '{title}' by '{artist}': {e}")
            return ""

    return ""


def load_progress() -> int:
    """Load the last processed index from progress file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return 0
    return 0


def save_progress(idx: int):
    """Save current progress index."""
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(idx))


def main():
    # Load original CSV
    df = pd.read_csv(INPUT_CSV)
    total = len(df)
    print(f"Loaded {total} tracks from {INPUT_CSV}")

    # If output file exists, load it (has partially updated IDs from previous runs)
    if os.path.exists(OUTPUT_CSV):
        df = pd.read_csv(OUTPUT_CSV)
        print(f"Resuming from existing {OUTPUT_CSV}")

    # Load progress
    start_idx = load_progress()
    if start_idx > 0:
        print(f"Resuming from row {start_idx}")

    end_idx = min(start_idx + BATCH_LIMIT, total)
    print(f"Processing rows {start_idx} to {end_idx - 1} ({end_idx - start_idx} tracks)")
    print()

    updated_count = 0
    failed_count = 0
    unchanged_count = 0

    for idx in range(start_idx, end_idx):
        row = df.iloc[idx]
        title = str(row["title"]).strip()
        artist = str(row["artist"]).strip()
        old_id = str(row["spotify_id"]).strip() if pd.notna(row["spotify_id"]) else ""

        new_id = search_spotify_id(title, artist)

        if new_id:
            if new_id != old_id:
                df.at[idx, "spotify_id"] = new_id
                updated_count += 1
                print(f"[{idx+1}/{total}] UPDATED: {title} - {artist}")
                print(f"    Old: {old_id}")
                print(f"    New: {new_id}")
            else:
                unchanged_count += 1
                if (idx + 1) % 200 == 0:
                    print(f"[{idx+1}/{total}] (unchanged so far: {unchanged_count})")
        else:
            failed_count += 1
            print(f"[{idx+1}/{total}] FAILED: {title} - {artist} (keeping old ID)")

        # Save progress periodically
        if (idx + 1) % SAVE_EVERY == 0:
            df.to_csv(OUTPUT_CSV, index=False)
            save_progress(idx + 1)

        # Rate limiting: ~0.15s per request = ~400/min, safe for Spotify
        time.sleep(0.15)

    # Final save
    df.to_csv(OUTPUT_CSV, index=False)
    save_progress(end_idx)

    print()
    print("=" * 60)
    print(f"Batch complete! Results saved to {OUTPUT_CSV}")
    print(f"  Processed:     {end_idx - start_idx}")
    print(f"  Updated:       {updated_count}")
    print(f"  Unchanged:     {unchanged_count}")
    print(f"  Failed:        {failed_count}")
    print(f"  Remaining:     {total - end_idx}")
    print("=" * 60)

    if end_idx < total:
        print(f"\nRun the script again to process the next batch.")
        print(f"Progress saved at row {end_idx}.")
    else:
        print(f"\n✅ All {total} tracks processed!")
        print(f"Rename to use it:")
        print(f"  mv {OUTPUT_CSV} {INPUT_CSV}")
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)


if __name__ == "__main__":
    main()
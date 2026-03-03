# CleanCSV.py
from numpy import delete
import duckdb
import pandas as pd
import os
from pathlib import Path

def clean_charts_dataset(input_file='~/Downloads/charts.csv', output_file='converted_charts.csv'):
    """
    Clean the Spotify charts dataset by:
    - Removing Viral 50 data
    - Removing trend and streams columns
    - Keeping only Top 200 data
    
    Args:
        input_file: Path to input CSV (can use ~ for home directory)
        output_file: Path to output CSV (saved in current directory by default)
    """
    
    # Expand the ~ to full home directory path
    input_file = os.path.expanduser(input_file)
    # output_file = os.path.expanduser(output_file)  # In case output also uses ~
    
    print(f"Input file: {input_file}")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file not found at {input_file}")
        return
    
    print(f"Starting to clean {input_file}...")
    
    # Connect to DuckDB (in-memory for speed)
    conn = duckdb.connect()
    
    try:
        # Register the CSV file as a view
        conn.execute(f"""
            CREATE OR REPLACE VIEW raw_charts AS 
            SELECT * FROM read_csv_auto('{input_file}')
        """)

        # Create cleaned dataset
        print("\nCleaning data...")
        
        conn.execute(f"""
            COPY (
                SELECT 
                    title,
                    rank,
                    date,
                    artist,
                    url,
                    region,
                    chart
                FROM raw_charts
                WHERE LOWER(chart) = 'top200'
                ORDER BY date, region, rank
            ) TO '{output_file}' (HEADER, DELIMITER ',')
        """)
        
        # Verify the output
        result_rows = conn.execute(f"SELECT COUNT(*) FROM read_csv_auto('{output_file}')").fetchone()[0]
        print(f"\n✅ Successfully created cleaned file: {output_file}")
        print(f"Rows in cleaned file: {result_rows:,}")
        
        # Show sample of cleaned data
        print("\nSample of cleaned data (first 5 rows):")
        sample = conn.execute(f"""
            SELECT * FROM read_csv_auto('{output_file}') 
            LIMIT 5
        """).fetchdf()
        print(sample.to_string())
        
        # File size comparison
        original_size = os.path.getsize(input_file) / (1024**3)  # Convert to GB
        new_size = os.path.getsize(output_file) / (1024**3)
        reduction = ((original_size - new_size) / original_size) * 100
        
        print(f"\n📊 Size reduction: {reduction:.1f}% ({original_size:.2f} GB → {new_size:.2f} GB)")
        
        # Show absolute paths
        print(f"\n📁 Files saved:")
        print(f"  Input:  {os.path.abspath(input_file)}")
        print(f"  Output: {os.path.abspath(output_file)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        conn.close()

def convert_charts(input_file='converted_charts.csv', output_file='final_charts.csv'):
    
    print("=" * 60)
    print("CONVERTING CHARTS DATA TO SONG-LEVEL AGGREGATION")
    print("=" * 60)
    
    input_file = os.path.expanduser(input_file)
    output_file = os.path.expanduser(output_file)
    
    print(f"Input file: {input_file}")
    print(f"Output file: {output_file}")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file not found at {input_file}")
        return
    
    # Connect to DuckDB
    conn = duckdb.connect()
    
    try:
        # First, let's get some statistics about the cleaned data
        print("\n📊 Analyzing cleaned data...")
        
        # Count total rows in cleaned data
        total_rows = conn.execute(f"""
            SELECT COUNT(*) FROM read_csv_auto('{input_file}')
        """).fetchone()[0]
        print(f"Total rows in cleaned data: {total_rows:,}")
        
        # Count unique songs (by title + artist)
        unique_songs = conn.execute(f"""
            SELECT COUNT(DISTINCT title || '|' || artist) as unique_songs
            FROM read_csv_auto('{input_file}')
        """).fetchone()[0]
        print(f"Unique songs (by title + artist): {unique_songs:,}")
        
        # Now perform the aggregation
        print("\n🔄 Aggregating data by song...")
        print("   Calculating popularity_weight = 201 - rank for each occurrence")
        print("   Summing weights across all dates, regions, and positions...")
        
        # Create the aggregated dataset
        conn.execute(f"""
            COPY (
                WITH song_data AS (
                    SELECT 
                        title,
                        artist,
                        MIN(url) as sample_url,
                        SUM(201 - rank) as total_popularity_weight,
                    FROM read_csv_auto('{input_file}')
                    GROUP BY title, artist
                )
                SELECT 
                    title,
                    artist,
                    sample_url,
                    total_popularity_weight,
                    ROUND(avg_rank, 2) as avg_rank
                FROM song_data
                ORDER BY total_popularity_weight DESC
            ) TO '{output_file}' (HEADER, DELIMITER ',')
        """)
        
        # Verify the output
        result_rows = conn.execute(f"SELECT COUNT(*) FROM read_csv_auto('{output_file}')").fetchone()[0]
        print(f"\n✅ Successfully created converted file: {output_file}")
        print(f"Rows in converted file (unique songs): {result_rows:,}")
        
        # Show sample of converted data
        print("\n📝 Sample of converted data (top 5 songs by popularity weight):")
        sample = conn.execute(f"""
            SELECT 
                title,
                artist,
                total_popularity_weight,
                appearance_count,
                region_count,
                days_in_charts,
                best_rank,
                avg_rank
            FROM read_csv_auto('{output_file}') 
            LIMIT 5
        """).fetchdf()
        print(sample.to_string())
        
        # Show some statistics about the conversion
        print("\n📊 Conversion Statistics:")
        
        # Total popularity weight sum
        total_weight = conn.execute(f"""
            SELECT SUM(total_popularity_weight) 
            FROM read_csv_auto('{output_file}')
        """).fetchone()[0]
        print(f"Total popularity weight across all songs: {total_weight:,.0f}")
        
        # Average popularity weight per song
        avg_weight = conn.execute(f"""
            SELECT AVG(total_popularity_weight) 
            FROM read_csv_auto('{output_file}')
        """).fetchone()[0]
        print(f"Average popularity weight per song: {avg_weight:,.0f}")
        
        # Song with highest popularity weight
        top_song = conn.execute(f"""
            SELECT title, artist, total_popularity_weight 
            FROM read_csv_auto('{output_file}') 
            ORDER BY total_popularity_weight DESC 
            LIMIT 1
        """).fetchone()
        print(f"\n🏆 Most popular song overall:")
        print(f"   {top_song[0]} by {top_song[1]} (weight: {top_song[2]:,})")
        
        # File size comparison
        original_size = os.path.getsize(input_file) / (1024**2)  # Convert to MB
        new_size = os.path.getsize(output_file) / (1024**2)
        
        print(f"\n📊 File size: {new_size:.2f} MB")
        
        # Show absolute paths
        print(f"\n📁 Files:")
        print(f"  Input:  {os.path.abspath(input_file)}")
        print(f"  Output: {os.path.abspath(output_file)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        conn.close()

def extract_spotify_id(input_file='final_charts_.csv', output_file='final_charts.csv'):
    """
    Extract Spotify ID from the sample_url column by removing the base URL part.
    
    Args:
        input_file: Path to input CSV (final_charts.csv by default)
        output_file: Path to output CSV with extracted Spotify IDs
    """
    print("=" * 60)
    print("EXTRACTING SPOTIFY IDs FROM URLs")
    print("=" * 60)
    
    input_file = os.path.expanduser(input_file)
    output_file = os.path.expanduser(output_file)
    
    print(f"Input file: {input_file}")
    print(f"Output file: {output_file}")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file not found at {input_file}")
        return
    
    try:
        # Read the CSV file
        print("\n📂 Reading CSV file...")
        df = pd.read_csv(input_file)
        
        print(f"Original columns: {list(df.columns)}")
        print(f"Total rows: {len(df):,}")
        
        # Show a sample of URLs before extraction
        print("\n🔗 Sample URLs before extraction:")
        print(df['sample_url'].head().to_string())
        
        # Extract Spotify ID from URL and replace the column
        print("\n🔄 Extracting Spotify IDs from URLs...")
        
        # Replace the sample_url column with just the ID
        df['sample_url'] = df['sample_url'].str.replace('https://open.spotify.com/track/', '', regex=False)
        
        # Rename the column to spotify_id
        df = df.rename(columns={'sample_url': 'spotify_id'})
        
        # Show sample of extracted IDs
        print("\n✅ Extracted Spotify IDs (first 5):")
        result_df = df[['title', 'artist', 'spotify_id', 'total_popularity_weight']].head()
        print(result_df.to_string())
        
        # Verify extraction worked
        if df['spotify_id'].str.len().min() > 0:
            print("\n✓ All IDs successfully extracted")
        else:
            print("\n⚠️ Some rows may have empty IDs - check the data")
        
        # Save to new CSV
        print(f"\n💾 Saving to {output_file}...")
        df.to_csv(output_file, index=False)
        
        # File size info
        new_size = os.path.getsize(output_file) / (1024**2)  # Convert to MB
        print(f"\n📊 File size: {new_size:.2f} MB")
        
        # Show new columns
        print(f"\n📁 Updated columns: {list(df.columns)}")
        print(f"\n✅ Successfully created file with Spotify IDs: {output_file}")
        print(f"  Total songs processed: {len(df):,}")
        
        # Show absolute path
        print(f"\n📁 File saved at: {os.path.abspath(output_file)}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    print("=" * 60)
    print("SPOTIFY CHARTS DATASET CLEANER")
    print("=" * 60)
    
    # Uncomment the steps you want to run
    
    # Step 1: Clean the raw charts data
    # clean_charts_dataset(
    #     input_file='~/Downloads/charts.csv',
    #     output_file='converted_charts.csv'
    # )
    
    # Convert to song-level aggregation
    # convert_charts(
    #     input_file='converted_charts.csv',
    #     output_file='final_charts_.csv'
    # )

    extract_spotify_id(
        input_file='final_charts_.csv',
        output_file='final_charts.csv')
    

    



"""
Test script to verify Soundnet API is working correctly.
"""

import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

def test_soundnet_direct():
    """Test the API directly with the example from RapidAPI"""
    print("=== Testing Soundnet API Directly ===\n")
    
    # Test track: "Bohemian Rhapsody" by Queen
    track_id = "7s25THrKz86DM225dOYwnr"
    url = f"https://track-analysis.p.rapidapi.com/pktx/spotify/{track_id}"
    
    # Get your API key from .env
    api_key = os.getenv("RAPIDAPI_KEY")
    
    if not api_key:
        print("❌ ERROR: RAPIDAPI_KEY not found in .env file")
        print("Please add this line to your .env file:")
        print("RAPIDAPI_KEY=your_api_key_here")
        return False
    
    print(f"Using API Key: {api_key[:10]}...{api_key[-4:]}")  # Show partial key for verification
    print(f"Testing track ID: {track_id}\n")
    
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "track-analysis.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API Request Successful!\n")
            
            data = response.json()
            print("Response Data:")
            print(json.dumps(data, indent=2))
            
            # Check for expected fields
            expected_fields = ['tempo', 'energy', 'danceability', 'key', 'mode', 
                             'acousticness', 'instrumentalness', 'liveness', 
                             'speechiness', 'loudness']
            
            print("\n=== Checking Expected Fields ===")
            missing_fields = []
            for field in expected_fields:
                if field in data:
                    print(f"✅ {field}: {data[field]}")
                else:
                    print(f"❌ {field}: MISSING")
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"\n⚠️  Warning: Missing fields: {missing_fields}")
            else:
                print("\n✅ All expected fields present!")
            
            return True
            
        elif response.status_code == 401:
            print("❌ Authentication Error (401)")
            print("Your API key is invalid or not active.")
            print("Please check:")
            print("1. Your subscription is active on RapidAPI")
            print("2. The API key is correct in your .env file")
            return False
            
        elif response.status_code == 403:
            print("❌ Forbidden (403)")
            print("You don't have permission to access this API.")
            print("Please check your RapidAPI subscription.")
            return False
            
        elif response.status_code == 429:
            print("❌ Rate Limit Exceeded (429)")
            print("You've hit the API rate limit.")
            print("Wait a moment and try again.")
            return False
            
        else:
            print(f"❌ Unexpected Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.Timeout:
        print("❌ Request Timeout")
        print("The API took too long to respond. Try again.")
        return False
        
    except requests.RequestException as e:
        print(f"❌ Request Error: {e}")
        return False
        
    except json.JSONDecodeError:
        print("❌ Invalid JSON Response")
        print(f"Response text: {response.text}")
        return False


def test_soundnet_module():
    """Test your soundnet_api.py module"""
    print("\n\n=== Testing soundnet_api.py Module ===\n")
    
    try:
        from soundnet_api import get_audio_features_from_soundnet
        
        # Test with the same track
        track_id = "7s25THrKz86DM225dOYwnr"
        print(f"Testing track ID: {track_id}")
        print("Calling get_audio_features_from_soundnet()...\n")
        
        features = get_audio_features_from_soundnet(track_id)
        
        if features:
            print("✅ Module works correctly!\n")
            print("Features returned:")
            print(json.dumps(features, indent=2))
            return True
        else:
            print("❌ Module returned None")
            print("Check if the API key in .env is correct")
            return False
            
    except ImportError as e:
        print(f"❌ Cannot import soundnet_api module: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing module: {e}")
        return False


def check_env_file():
    """Check if .env file is properly configured"""
    print("\n\n=== Checking .env Configuration ===\n")
    
    api_key = os.getenv("RAPIDAPI_KEY")
    spotify_id = os.getenv("SPOTIPY_CLIENT_ID")
    spotify_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    
    issues = []
    
    if not api_key:
        print("❌ RAPIDAPI_KEY not found")
        issues.append("RAPIDAPI_KEY")
    else:
        print(f"✅ RAPIDAPI_KEY found: {api_key[:10]}...{api_key[-4:]}")
    
    if not spotify_id:
        print("❌ SPOTIPY_CLIENT_ID not found")
        issues.append("SPOTIPY_CLIENT_ID")
    else:
        print(f"✅ SPOTIPY_CLIENT_ID found")
    
    if not spotify_secret:
        print("❌ SPOTIPY_CLIENT_SECRET not found")
        issues.append("SPOTIPY_CLIENT_SECRET")
    else:
        print(f"✅ SPOTIPY_CLIENT_SECRET found")
    
    if issues:
        print(f"\n⚠️  Missing variables: {', '.join(issues)}")
        print("\nYour .env file should look like this:")
        print("```")
        print("SPOTIPY_CLIENT_ID=your_spotify_client_id")
        print("SPOTIPY_CLIENT_SECRET=your_spotify_client_secret")
        print("RAPIDAPI_KEY=your_rapidapi_key")
        print("```")
        return False
    else:
        print("\n✅ All environment variables configured!")
        return True


def main():
    print("=" * 60)
    print("SOUNDNET API TEST SUITE")
    print("=" * 60)
    
    # Step 1: Check .env
    env_ok = check_env_file()
    
    if not env_ok:
        print("\n❌ Fix your .env file first, then run this test again.")
        return
    
    # Step 2: Test direct API call
    direct_ok = test_soundnet_direct()
    
    # Step 3: Test module
    module_ok = test_soundnet_module()
    
    # Summary
    print("\n\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Environment Configuration: {'✅ PASS' if env_ok else '❌ FAIL'}")
    print(f"Direct API Test: {'✅ PASS' if direct_ok else '❌ FAIL'}")
    print(f"Module Test: {'✅ PASS' if module_ok else '❌ FAIL'}")
    
    if env_ok and direct_ok and module_ok:
        print("\n🎉 All tests passed! Your Soundnet API is working correctly!")
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")


if __name__ == "__main__":
    main()
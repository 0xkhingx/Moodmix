import os
import json
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheHandler
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SCOPE = "playlist-modify-public playlist-modify-private user-read-private"

CONFIG_PATH = BASE_DIR / "config" / "mood_features.json"
with open(CONFIG_PATH, "r") as f:
    MOOD_MAP = json.load(f)

EMOTIONS = list(MOOD_MAP.keys())
EMOTION_TO_INDEX = {e: i for i, e in enumerate(EMOTIONS)}
INDEX_TO_EMOTION = {i: e for i, e in enumerate(EMOTIONS)}


class SessionCacheHandler(CacheHandler):
    def __init__(self):
        self.key = "spotify_token_info"

    def get_cached_token(self):
        return st.session_state.get(self.key)

    def save_token_to_cache(self, token_info):
        st.session_state[self.key] = token_info


def _make_auth(cache_handler=None):
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SCOPE,
        cache_handler=cache_handler or SessionCacheHandler(),
        open_browser=False,
    )


def get_search_query(mood_label):
    data = MOOD_MAP.get(mood_label)
    return data["search_query"] if data else ""

def get_mood_info(mood_label):
    return MOOD_MAP.get(mood_label)

def get_all_moods():
    return list(MOOD_MAP.keys())

def get_spotify():
    auth_manager = _make_auth()
    return spotipy.Spotify(auth_manager=auth_manager)

def get_user_info(sp):
    user = sp.current_user()
    return {
        "id": user["id"],
        "display_name": user.get("display_name", "User"),
        "images": user.get("images", []),
    }

def search_tracks(sp, query, limit=10):
    results = sp.search(q=query, type="track", limit=limit, market="US")
    tracks = []
    for track in results["tracks"]["items"]:
        tracks.append({
            "id": track["id"],
            "name": track["name"],
            "artist": ", ".join(a["name"] for a in track["artists"]),
            "album": track["album"]["name"],
            "album_image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
            "preview_url": track.get("preview_url"),
            "uri": track["uri"],
            "external_url": track["external_urls"]["spotify"],
        })
    return tracks

def create_playlist(sp, user_id, name, description, track_uris):
    if sp._auth:
        token = sp._auth
    elif sp.auth_manager:
        token = sp.auth_manager.get_cached_token()["access_token"]
    else:
        raise ValueError("No auth token available")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    data = {"name": name, "description": description, "public": True}
    r = requests.post("https://api.spotify.com/v1/me/playlists", headers=headers, json=data)
    r.raise_for_status()
    playlist = r.json()
    playlist_id = playlist["id"]

    for i in range(0, len(track_uris), 100):
        batch = track_uris[i:i + 100]
        r2 = requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
            headers=headers, json={"uris": batch}
        )
        r2.raise_for_status()

    return {
        "id": playlist_id,
        "name": playlist["name"],
        "url": playlist["external_urls"]["spotify"],
        "snapshot_id": playlist["snapshot_id"],
    }

def get_auth_url():
    return _make_auth().get_authorize_url()

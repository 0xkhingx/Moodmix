import os
import json
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from spotipy.cache_handler import CacheHandler
from pathlib import Path
from dotenv import load_dotenv
try:
    import streamlit as st
except ImportError:  # FastAPI context: streamlit not required
    st = None

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
    """Legacy Streamlit-session token cache (used only by app.py OAuth flow)."""

    def __init__(self):
        self.key = "spotify_token_info"

    def _require_streamlit(self):
        if st is None:
            raise RuntimeError("SessionCacheHandler requires Streamlit runtime (app.py only).")
        return st.session_state

    def get_cached_token(self):
        return self._require_streamlit().get(self.key)

    def save_token_to_cache(self, token_info):
        self._require_streamlit()[self.key] = token_info


def _make_auth(cache_handler=None):
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SCOPE,
        cache_handler=cache_handler or SessionCacheHandler(),
        open_browser=False,
    )


def get_search_query(mood_label, mode="match"):
    """Spotify search query for a mood.

    mode="match" mirrors the mood; mode="lift" aims to move the listener
    toward a better mood (falls back to the match query if none is set).
    """
    data = MOOD_MAP.get(mood_label)
    if not data:
        return ""
    if mode == "lift":
        return data.get("lift_query") or data["search_query"]
    return data["search_query"]

def get_track_queries(mood_label, mode="match"):
    """Spotify search queries used to fetch tracks for a mood.

    Genre filters return real, recognisable songs; plain mood words mostly
    match song *titles* literally ("Happy Upbeat Music"), so they are only a
    fallback when no genres are configured.
    """
    data = MOOD_MAP.get(mood_label)
    if not data:
        return []
    genres = data.get("lift_genres" if mode == "lift" else "genres") or []
    if genres:
        return [f'genre:"{g}"' for g in genres]
    query = get_search_query(mood_label, mode)
    return [query] if query else []


def get_mood_info(mood_label):
    return MOOD_MAP.get(mood_label)

def get_all_moods():
    return list(MOOD_MAP.keys())

def get_spotify():
    """Legacy user-OAuth client (Streamlit app.py only)."""
    auth_manager = _make_auth()
    return spotipy.Spotify(auth_manager=auth_manager)


_cc_sp = None


def get_client_credentials_sp():
    """Display-only Spotify client (FastAPI): no user login, search only."""
    global _cc_sp
    if _cc_sp is None:
        auth_manager = SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        )
        # Fail fast: spotipy's defaults (3 retries with backoff) can stall a
        # request for a minute on a flaky connection. The API also applies its
        # own time budget, so one quick retry is enough here.
        _cc_sp = spotipy.Spotify(
            auth_manager=auth_manager,
            requests_timeout=5,
            retries=1,
            status_retries=1,
            backoff_factor=0.2,
        )
    return _cc_sp


def search_tracks_cc(query, limit=10, offset=0, market=None):
    """Search tracks via client-credentials client. Raises on failure."""
    sp = get_client_credentials_sp()
    return search_tracks(sp, query, limit=limit, offset=offset, market=market)

def get_user_info(sp):
    user = sp.current_user()
    return {
        "id": user["id"],
        "display_name": user.get("display_name", "User"),
        "images": user.get("images", []),
    }

def search_tracks(sp, query, limit=10, offset=0, market=None):
    market = market or os.getenv("SPOTIFY_MARKET", "US")
    results = sp.search(q=query, type="track", limit=limit, offset=offset, market=market)
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
            "explicit": bool(track.get("explicit", False)),
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

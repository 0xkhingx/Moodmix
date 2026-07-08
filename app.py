import streamlit as st
import numpy as np
import io
from pathlib import Path
import spotipy
from dotenv import load_dotenv
import librosa

from src.spotify_client import get_spotify, get_user_info, search_tracks, create_playlist, get_auth_url, get_mood_info, get_search_query, SessionCacheHandler, _make_auth
from src.predict import predict

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

st.set_page_config(page_title="MoodMix", page_icon=":musical_note:", layout="wide")

MOOD_COLORS = {
    "happy":    {"bg": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)", "card": "#2d1b36"},
    "sad":      {"bg": "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)", "card": "#1a2a3a"},
    "angry":    {"bg": "linear-gradient(135deg, #ff6a88 0%, #ff99ac 100%)", "card": "#3a1a1a"},
    "calm":     {"bg": "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)", "card": "#1a2e1a"},
    "fearful":  {"bg": "linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)", "card": "#2a1a3a"},
    "surprised":{"bg": "linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)", "card": "#2a2a1a"},
    "disgusted":{"bg": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", "card": "#1a1a2a"},
}

st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #0f0f0f;
}

h1, h2, h3 {
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}

div.stButton > button {
    border-radius: 12px;
    font-weight: 600;
    transition: all 0.2s ease;
    border: none;
    padding: 10px 24px;
}

div.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.4);
}

div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1DB954 0%, #1ed760 100%);
    color: #000;
}

div.stTextInput > div > input {
    border-radius: 12px;
    background: #1a1a1a;
    border: 1px solid #333;
    color: #fff;
}

div[data-testid="stImage"] img {
    border-radius: 12px;
}

.mood-card {
    text-align: center;
    padding: 40px 20px;
    border-radius: 24px;
    margin: 10px 0;
    transition: all 0.3s ease;
}

.mood-icon {
    font-size: 72px;
    display: block;
    margin-bottom: 10px;
    animation: float 3s ease-in-out infinite;
}

@keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-10px); }
}

.mood-label {
    font-size: 32px;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.02em;
}

.mood-confidence {
    color: rgba(255,255,255,0.7);
    font-size: 14px;
    margin-top: 4px;
}

.mood-desc {
    color: rgba(255,255,255,0.5);
    font-size: 14px;
    margin-top: 8px;
}

.track-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 16px;
}

.track-card {
    background: #1a1a1a;
    border-radius: 16px;
    padding: 12px;
    transition: all 0.2s ease;
    border: 1px solid #222;
}

.track-card:hover {
    background: #222;
    transform: translateY(-4px);
    border-color: #333;
}

.track-card img {
    width: 100%;
    border-radius: 8px;
    aspect-ratio: 1;
    object-fit: cover;
}

.track-name {
    font-size: 14px;
    font-weight: 600;
    margin-top: 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.track-artist {
    font-size: 12px;
    color: #888;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.spotify-card {
    background: #1a1a1a;
    border-radius: 16px;
    padding: 20px;
    border: 1px solid #222;
    margin-bottom: 16px;
}

.spotify-card .profile-img {
    border-radius: 50%;
    width: 60px;
    height: 60px;
    object-fit: cover;
    border: 2px solid #1DB954;
}

.badge-spotify {
    background: #1DB954;
    color: #000;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    display: inline-block;
}

.success-banner {
    background: linear-gradient(135deg, #1DB954 0%, #1ed760 100%);
    color: #000;
    padding: 20px 24px;
    border-radius: 16px;
    margin: 12px 0;
    font-weight: 600;
}

.success-banner a {
    color: #000;
    text-decoration: underline;
}

div[data-testid="stVerticalBlock"] > div:has(> div > iframe) {
    background: transparent !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: #1a1a1a;
    border-radius: 12px;
    padding: 4px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
}

.stTabs [aria-selected="true"] {
    background: #2a2a2a;
}

.stSpinner > div {
    border-color: #1DB954 !important;
}
</style>
""", unsafe_allow_html=True)

for key in ["spotify_connected", "user_info", "mood_result", "recorded_audio", "playlist_result", "auth_clicked", "auth_code_processed"]:
    if key not in st.session_state:
        st.session_state[key] = False if key in ["spotify_connected", "auth_clicked", "auth_code_processed"] else None

if not st.session_state.spotify_connected and not st.session_state.auth_code_processed:
    params = st.query_params
    if "code" in params:
        st.session_state.auth_code_processed = True
        try:
            auth_manager = _make_auth()
            token_str = auth_manager.get_access_token(params["code"], as_dict=False)
            sp_user = spotipy.Spotify(auth=token_str)
            st.session_state.spotify_connected = True
            st.session_state.user_info = get_user_info(sp_user)
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Auth failed: {e}")

st.markdown("""
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
    <i class="fab fa-spotify" style="font-size: 32px; color: #1DB954;"></i>
    <h1 style="margin: 0; font-size: 36px;">MoodMix</h1>
    <span style="background: #1DB954; color: #000; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 700;">v1.0</span>
</div>
<p style="color: #888; margin-top: -8px; font-size: 16px;">
    Tell me how you feel &mdash; I'll build you a Spotify playlist for your mood.
</p>
""", unsafe_allow_html=True)

left, right = st.columns([1.1, 2.2])

with left:
    st.markdown('<div class="spotify-card">', unsafe_allow_html=True)
    st.markdown('<h3><i class="fab fa-spotify" style="color:#1DB954; margin-right:8px;"></i>Spotify</h3>', unsafe_allow_html=True)

    if st.session_state.spotify_connected and st.session_state.user_info:
        user = st.session_state.user_info
        col_img, col_name = st.columns([1, 2])
        with col_img:
            if user["images"]:
                st.markdown(
                    f"<img class='profile-img' src='{user['images'][0]['url']}' />",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("<div class='profile-img' style='background:#333; width:60px; height:60px; border-radius:50%;'></div>", unsafe_allow_html=True)
        with col_name:
            st.markdown(f"**{user['display_name']}**")
            st.markdown("<span class='badge-spotify'><i class='fas fa-check-circle' style='margin-right:4px;'></i>Connected</span>", unsafe_allow_html=True)

        if st.button("Disconnect", use_container_width=True):
            for k in ["spotify_connected", "user_info", "spotify_token_info"]:
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.markdown("<p style='color:#888; font-size: 14px;'>Link your Spotify to create playlists.</p>", unsafe_allow_html=True)
        if st.button("Connect Spotify", use_container_width=True):
            st.session_state.auth_clicked = True

        if st.session_state.auth_clicked:
            auth_url = get_auth_url()
            st.markdown(f"<p style='margin-top:8px;'><i class='fas fa-arrow-right' style='color:#1DB954;'></i> <a href='{auth_url}' target='_blank' style='color:#1DB954;'>Authorize Spotify</a></p>", unsafe_allow_html=True)

            with st.expander("Trouble connecting? Paste redirect URL manually"):
                callback_url = st.text_input("Redirect URL", placeholder="http://127.0.0.1:8888/callback?code=...", label_visibility="collapsed")
                if callback_url and "code=" in callback_url:
                    from urllib.parse import parse_qs, urlparse
                    parsed = urlparse(callback_url)
                    cb_params = parse_qs(parsed.query)
                    if "code" in cb_params:
                        code = cb_params["code"][0]
                        with st.spinner("Connecting..."):
                            try:
                                auth_manager = _make_auth()
                                token_str = auth_manager.get_access_token(code, as_dict=False)
                                sp_user = spotipy.Spotify(auth=token_str)
                                st.session_state.spotify_connected = True
                                st.session_state.user_info = get_user_info(sp_user)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Auth failed: {e}")
                    else:
                        st.warning("No authorization code found in URL.")

    st.markdown('</div>', unsafe_allow_html=True)

with right:
    tab_speak, tab_type = st.tabs(["Speak", "Type"])

    with tab_speak:
        st.markdown("### Record your voice")
        recorded_bytes = st.audio_input("Click and hold to record", label_visibility="collapsed")

        if recorded_bytes is not None and st.session_state.get("_raw_audio") != recorded_bytes:
            st.session_state._raw_audio = recorded_bytes
            audio_arr, _ = librosa.load(io.BytesIO(recorded_bytes.getvalue()), sr=16000)
            st.session_state.recorded_audio = audio_arr
            st.session_state.mood_result = None
            st.session_state.playlist_result = None

        if recorded_bytes is not None:
            st.audio(recorded_bytes)

        if st.session_state.recorded_audio is not None:
            if st.button("Analyze Mood", use_container_width=True, type="primary", key="analyze_speech"):
                with st.spinner("Analyzing your voice..."):
                    result = predict(audio_data=st.session_state.recorded_audio)
                    if result:
                        st.session_state.mood_result = result
                        st.rerun()

    with tab_type:
        st.markdown("### Type how you feel")
        text_input = st.text_area(
            "What's on your mind?",
            placeholder="e.g., I'm feeling great today! or This is so frustrating...",
            height=90,
            label_visibility="collapsed",
        )
        if st.button("Analyze Mood", type="primary", use_container_width=True, key="analyze_text"):
            if text_input.strip():
                with st.spinner("Analyzing your text..."):
                    result = predict(text=text_input)
                    if result:
                        st.session_state.mood_result = result
                        st.rerun()

if st.session_state.mood_result:
    result = st.session_state.mood_result
    mood_info = get_mood_info(result["emotion"])
    emotion = result["emotion"]
    colors = MOOD_COLORS.get(emotion, {"bg": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", "card": "#1a1a2a"})
    icon_class = mood_info["icon"] if mood_info else "fa-music"

    st.markdown("---")

    col_mood, col_create = st.columns([1.6, 1])

    with col_mood:
        st.markdown(
            f"<div class='mood-card' style='background: {colors['bg']}'>"
            f"<i class='fas {icon_class} mood-icon'></i>"
            f"<div class='mood-label'>{emotion.title()}</div>"
            f"<div class='mood-confidence'>"
            f"Confidence: {result['confidence']:.1%} &nbsp;·&nbsp; detected via {result['source']}"
            f"</div>"
            f"<div class='mood-desc'>{mood_info['description'] if mood_info else ''}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_create:
        st.markdown("### Create Playlist")
        playlist_name = st.text_input("Playlist name", value=f"MoodMix - {emotion.title()}", label_visibility="collapsed")

        if st.session_state.spotify_connected:
            if st.button("Create on Spotify", use_container_width=True, type="primary"):
                with st.spinner("Creating your playlist..."):
                    try:
                        sp_obj = get_spotify()
                        user_id = st.session_state.user_info["id"]
                        query = get_search_query(emotion)
                        if query:
                            tracks = search_tracks(sp_obj, query, limit=10)
                            if tracks:
                                track_uris = [t["uri"] for t in tracks]
                                desc = f"A {emotion} mood playlist created by MoodMix"
                                playlist = create_playlist(sp_obj, user_id, playlist_name, desc, track_uris)
                                st.session_state.playlist_result = {"playlist": playlist, "tracks": tracks}
                                st.rerun()
                            else:
                                st.warning("No tracks found. Try a different mood.")
                    except Exception as e:
                        st.error(f"Failed: {e}")
        else:
            st.info("Connect Spotify first to create playlists.")

    if st.session_state.playlist_result:
        pr = st.session_state.playlist_result
        playlist = pr["playlist"]
        tracks = pr["tracks"]

        st.markdown(
            f"<div class='success-banner'>"
            f"<i class='fas fa-check-circle' style='margin-right:8px;'></i>"
            f"Playlist created: <strong>{playlist['name']}</strong> &nbsp;·&nbsp; "
            f"<a href='{playlist['url']}' target='_blank'>Open in Spotify <i class='fas fa-external-link-alt' style='font-size:12px;'></i></a>"
            f"</div>",
            unsafe_allow_html=True,
        )

        html = "<div class='track-grid'>"
        for track in tracks[:10]:
            art = track["album_image"] or ""
            html += f"""
            <div class='track-card'>
                <img src="{art}" alt="{track['name']}" loading="lazy" onerror="this.style.display='none'" />
                <div class='track-name' title="{track['name']}">{track['name']}</div>
                <div class='track-artist' title="{track['artist']}">{track['artist']}</div>
            </div>
            """
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #444; font-size: 13px;'>"
    "Built with Streamlit, PyTorch, librosa &amp; Spotify API</div>",
    unsafe_allow_html=True,
)

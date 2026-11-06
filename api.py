"""MoodMix FastAPI wrapper (case-study upgrade).

Exposes the existing ML in src/predict.py over HTTP:
  POST /predict/text   {text: str}          -> emotion + Spotify track recs
  POST /predict/speech multipart {file: audio} -> emotion + Spotify track recs
  GET  /health

Spotify is display-only via client-credentials (no user OAuth, no
playlist creation). If Spotify creds are missing/unreachable, the
endpoints still return the detected emotion with tracks=[].
"""

import hmac
import logging
import os
import random
import tempfile
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import asynccontextmanager
from pathlib import Path

import librosa
import numpy as np
from dotenv import load_dotenv
from typing import Literal

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from src import feedback as feedback_store  # noqa: E402
from src.predict import _load_speech, _load_text, predict  # noqa: E402
from src.spotify_client import (  # noqa: E402
    EMOTIONS,
    get_mood_info,
    get_search_query,
    get_track_queries,
    search_tracks_cc,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("moodmix.api")

MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".oga", ".webm", ".m4a", ".mp4", ".flac"}
MIN_AUDIO_SECONDS = 0.5
SILENCE_PEAK = 1e-3
SR = 16000

TRACK_LIMIT = 10
# Spotify search pages to rotate through so repeat visits get variety.
TRACK_OFFSETS = (0, 10, 20, 30)
TRACK_CACHE_TTL = int(os.getenv("TRACK_CACHE_TTL", "3600"))
# Max seconds a prediction waits on Spotify. Past this the mood is returned
# with tracks=[] and the client fetches tracks via GET /tracks.
SPOTIFY_BUDGET_S = float(os.getenv("SPOTIFY_BUDGET_S", "6"))
# Explicit tracks are filtered out unless ALLOW_EXPLICIT=1 (public, all-ages app).
ALLOW_EXPLICIT = os.getenv("ALLOW_EXPLICIT", "0") == "1"
MIN_TRACKS = 6
_spotify_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="spotify")

RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))


Mood = Literal["happy", "sad", "angry", "calm", "fearful", "surprised", "disgusted"]
Mode = Literal["match", "lift"]
assert set(Mood.__args__) == set(EMOTIONS), "Mood literal out of sync with config/mood_features.json"


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    mode: Mode = "match"


class FeedbackRequest(BaseModel):
    source: Literal["text", "speech"]
    predicted: str = Field(max_length=32)
    corrected: Mood
    confidence: float | None = Field(default=None, ge=0, le=1)
    # Only sent when the user ticks "share my text"; never audio.
    text: str | None = Field(default=None, max_length=2000)


class TracksResponse(BaseModel):
    mood: str
    mode: Mode
    query: str
    description: str
    tracks: list["Track"]


class Track(BaseModel):
    id: str
    name: str
    artist: str
    album: str = ""
    album_image: str | None = None
    preview_url: str | None = None
    uri: str = ""
    external_url: str = ""
    explicit: bool = False


class PredictResponse(BaseModel):
    emotion: str
    confidence: float
    probabilities: dict[str, float] = {}
    source: str
    mode: Mode = "match"
    icon: str
    description: str
    query: str
    tracks: list[Track]


TracksResponse.model_rebuild()


# --------------------------------------------------------------------------
# Spotify track cache: 7 moods x a few offsets, so cache aggressively.
# --------------------------------------------------------------------------
_track_cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}
_track_cache_lock = threading.Lock()


def _cached_search(query: str, offset: int) -> list[dict]:
    key = (query, offset)
    now = time.monotonic()
    with _track_cache_lock:
        hit = _track_cache.get(key)
        if hit and now - hit[0] < TRACK_CACHE_TTL:
            return hit[1]
    tracks = search_tracks_cc(query, limit=TRACK_LIMIT, offset=offset)
    if tracks:
        with _track_cache_lock:
            _track_cache[key] = (now, tracks)
    return tracks


def _enrich(emotion: str, mode: str = "match") -> tuple[str, list[dict]]:
    """Return (human-readable query for the Spotify search link, tracks)."""
    query = get_search_query(emotion, mode) or ""
    track_queries = get_track_queries(emotion, mode)
    if not track_queries:
        return query, []
    tq = random.choice(track_queries)
    offset = random.choice(TRACK_OFFSETS)

    def clean(tracks):
        return tracks if ALLOW_EXPLICIT else [t for t in tracks if not t.get("explicit")]

    def fetch():
        tracks = clean(_cached_search(tq, offset) or _cached_search(tq, 0))
        # Spotify returns at most 10 per page here; top up from the next page
        # when filtering left the list short.
        if len(tracks) < MIN_TRACKS:
            seen = {t["id"] for t in tracks}
            more = clean(_cached_search(tq, (offset + TRACK_LIMIT) % 50))
            tracks += [t for t in more if t["id"] not in seen]
        return tracks[:TRACK_LIMIT]

    try:
        return query, _spotify_pool.submit(fetch).result(timeout=SPOTIFY_BUDGET_S)
    except FutureTimeout:
        log.warning("Spotify search exceeded %.1fs budget; returning emotion without tracks", SPOTIFY_BUDGET_S)
        return query, []
    except Exception as e:
        log.warning("Spotify search failed (%s); returning emotion without tracks", e)
        return query, []


def _to_response(result: dict, mode: str = "match") -> PredictResponse:
    query, tracks = _enrich(result["emotion"], mode)
    labels = result.get("labels") or []
    probs = result.get("probabilities") or []
    return PredictResponse(
        emotion=result["emotion"],
        confidence=result["confidence"],
        probabilities={label: round(float(p), 4) for label, p in zip(labels, probs)},
        source=result["source"],
        mode=mode,
        icon=result.get("icon") or "fa-music",
        description=result.get("description") or "",
        query=query,
        tracks=[Track(**t) for t in tracks],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_speech()
    _load_text()
    log.info("Models preloaded")
    yield


# Interactive docs are off in production (they advertise every endpoint);
# set ENABLE_DOCS=1 locally.
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "0") == "1"
app = FastAPI(
    title="MoodMix API",
    version="1.2.0",
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
frontend_urls_extra = os.getenv("FRONTEND_URLS", "")
allow_origins = [
    origin.strip()
    for origin in f"{frontend_url},{frontend_urls_extra}".split(",")
    if origin.strip()
]
# Always allow the production Vercel frontend unless explicitly disabled.
PROD_FRONTEND = "https://themoodmix.vercel.app"
if os.getenv("ALLOW_PROD_FRONTEND", "1") == "1" and PROD_FRONTEND not in allow_origins:
    allow_origins.append(PROD_FRONTEND)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Per-IP sliding-window rate limit on prediction endpoints (in-memory; fine
# for the single-worker deployment). RATE_LIMIT_PER_MIN=0 disables it.
# --------------------------------------------------------------------------
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(ip: str) -> bool:
    if RATE_LIMIT_PER_MIN <= 0:
        return False
    now = time.monotonic()
    with _hits_lock:
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT_PER_MIN:
            return True
        q.append(now)
        if len(_hits) > 10_000:  # bound memory under many distinct IPs
            for k in [k for k, v in _hits.items() if not v]:
                del _hits[k]
        return False


@app.middleware("http")
async def log_and_limit(request: Request, call_next):
    start = time.perf_counter()
    if request.method == "POST" and request.url.path.startswith(("/predict", "/feedback")):
        if _rate_limited(_client_ip(request)):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again in a minute."},
                headers={"Retry-After": "60"},
            )
    response = await call_next(request)
    # Basic hardening for a JSON API.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    log.info(
        "%s %s -> %s (%.0f ms)",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - start) * 1000,
    )
    return response


@app.get("/")
def root():
    return {
        "name": "MoodMix API",
        "version": app.version,
        "docs": "/docs" if ENABLE_DOCS else None,
        "health": "/health",
    }


@app.get("/health")
def health():
    try:
        _load_speech()
        speech_ok = True
    except Exception:
        log.exception("Speech model failed to load")
        speech_ok = False
    try:
        _load_text()
        text_ok = True
    except Exception:
        log.exception("Text model failed to load")
        text_ok = False
    ok = speech_ok and text_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ok" if ok else "degraded",
            "speech_model_loaded": speech_ok,
            "text_model_loaded": text_ok,
        },
    )


@app.post("/predict/text", response_model=PredictResponse)
def predict_text_endpoint(body: TextRequest):
    result = predict(text=body.text)
    if result is None:
        raise HTTPException(status_code=422, detail="Empty text")
    return _to_response(result, body.mode)


def _read_upload_capped(file: UploadFile) -> bytes:
    """Read at most MAX_AUDIO_BYTES (+1 to detect overflow) without buffering more."""
    chunks, total = [], 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio file too large (max 10MB)")
        chunks.append(chunk)
    return b"".join(chunks)


# Plain `def` so FastAPI runs decoding + inference in its threadpool instead
# of blocking the event loop (the deployment runs a single worker).
@app.post("/predict/speech", response_model=PredictResponse)
def predict_speech_endpoint(file: UploadFile = File(...), mode: Mode = Form("match")):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported audio type: {suffix}")
    data = _read_upload_capped(file)
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if not suffix:
        suffix = ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            audio_arr, _ = librosa.load(tmp_path, sr=SR)
        except Exception as e:
            log.info("Audio decode failed for %s: %s", suffix, e)
            raise HTTPException(status_code=400, detail="Could not decode audio. Try recording again.")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    if audio_arr.size < int(MIN_AUDIO_SECONDS * SR):
        raise HTTPException(status_code=400, detail="Recording too short. Speak for at least a second.")
    if float(np.max(np.abs(audio_arr))) < SILENCE_PEAK:
        raise HTTPException(status_code=400, detail="No speech detected. Check your microphone.")
    result = predict(audio_data=audio_arr)
    if result is None:
        raise HTTPException(status_code=422, detail="Prediction failed")
    return _to_response(result, mode)


@app.get("/tracks", response_model=TracksResponse)
def tracks_endpoint(mood: Mood = Query(...), mode: Mode = Query("match")):
    """Tracks for a mood without re-running the model (mood correction, mode toggle)."""
    query, tracks = _enrich(mood, mode)
    info = get_mood_info(mood) or {}
    return TracksResponse(
        mood=mood,
        mode=mode,
        query=query,
        description=info.get("description", ""),
        tracks=[Track(**t) for t in tracks],
    )


@app.post("/feedback", status_code=201)
def feedback_endpoint(body: FeedbackRequest):
    text = (body.text or "").strip() or None
    if body.source == "speech":
        text = None  # nothing to share for voice; audio is never stored
    row_id = feedback_store.add(body.source, body.predicted, body.corrected, body.confidence, text)
    log.info("feedback #%d: %s -> %s (%s)", row_id, body.predicted, body.corrected, body.source)
    return {"id": row_id}


@app.get("/feedback/export")
def feedback_export(authorization: str | None = Header(default=None), limit: int = Query(10_000, ge=1, le=100_000)):
    """Download collected corrections for retraining. Requires FEEDBACK_EXPORT_TOKEN."""
    token = os.getenv("FEEDBACK_EXPORT_TOKEN", "")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(supplied, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"rows": feedback_store.export(limit)}

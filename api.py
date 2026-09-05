"""MoodMix FastAPI wrapper (case-study upgrade).

Exposes the existing ML in src/predict.py over HTTP without changing it:
  POST /predict/text   {text: str}          -> emotion + Spotify track recs
  POST /predict/speech multipart {file: audio} -> emotion + Spotify track recs
  GET  /health

Spotify is display-only via client-credentials (no user OAuth, no
playlist creation). If Spotify creds are missing/unreachable, the
endpoints still return the detected emotion with tracks=[].
"""

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import librosa
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from src.predict import _load_speech, _load_text, predict  # noqa: E402
from src.spotify_client import get_search_query, search_tracks_cc  # noqa: E402

log = logging.getLogger("moodmix.api")

MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".oga", ".webm", ".m4a", ".flac"}

TRACK_LIMIT = 10


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class Track(BaseModel):
    id: str
    name: str
    artist: str
    album: str = ""
    album_image: str | None = None
    preview_url: str | None = None
    uri: str = ""
    external_url: str = ""


class PredictResponse(BaseModel):
    emotion: str
    confidence: float
    source: str
    icon: str
    description: str
    query: str
    tracks: list[Track]


def _enrich(emotion: str) -> tuple[str, list[dict]]:
    query = get_search_query(emotion) or ""
    if not query:
        return query, []
    try:
        return query, search_tracks_cc(query, limit=TRACK_LIMIT)
    except Exception as e:
        log.warning("Spotify search failed (%s); returning emotion without tracks", e)
        return query, []


def _to_response(result: dict) -> PredictResponse:
    query, tracks = _enrich(result["emotion"])
    return PredictResponse(
        emotion=result["emotion"],
        confidence=result["confidence"],
        source=result["source"],
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


app = FastAPI(title="MoodMix API", version="1.0.0", lifespan=lifespan)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    try:
        _load_speech()
        speech_ok = True
    except Exception:
        speech_ok = False
    try:
        _load_text()
        text_ok = True
    except Exception:
        text_ok = False
    return {"status": "ok", "speech_model_loaded": speech_ok, "text_model_loaded": text_ok}


@app.post("/predict/text", response_model=PredictResponse)
def predict_text_endpoint(body: TextRequest):
    result = predict(text=body.text)
    if result is None:
        raise HTTPException(status_code=422, detail="Empty text")
    return _to_response(result)


@app.post("/predict/speech", response_model=PredictResponse)
async def predict_speech_endpoint(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported audio type: {suffix}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file too large (max 10MB)")
    if not suffix:
        suffix = ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            audio_arr, _ = librosa.load(tmp_path, sr=16000)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not decode audio: {e}")
        if audio_arr.size == 0:
            raise HTTPException(status_code=400, detail="Could not decode audio")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    result = predict(audio_data=audio_arr)
    if result is None:
        raise HTTPException(status_code=422, detail="Prediction failed")
    return _to_response(result)

import io
import sys
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)

FAKE_TRACKS = [
    {
        "id": "t1",
        "name": "Test Song",
        "artist": "Test Artist",
        "album": "Test Album",
        "album_image": None,
        "preview_url": None,
        "uri": "spotify:track:t1",
        "external_url": "https://open.spotify.com/track/t1",
    }
]


def _sine_wav_bytes(sr=16000, secs=1.0, freq=440.0):
    n = int(sr * secs)
    audio = (0.5 * np.sin(2 * np.pi * freq * np.arange(n) / sr) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
    buf.seek(0)
    return buf.read()


class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["speech_model_loaded"] is True
        assert body["text_model_loaded"] is True


class TestPredictText:
    def test_happy_path(self):
        with patch.object(api, "search_tracks_cc", return_value=FAKE_TRACKS):
            r = client.post("/predict/text", json={"text": "I am feeling great today"})
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "text"
        assert isinstance(body["emotion"], str) and body["emotion"]
        assert 0 <= body["confidence"] <= 1
        assert isinstance(body["tracks"], list) and len(body["tracks"]) == 1
        assert body["tracks"][0]["name"] == "Test Song"

    def test_empty_text_rejected(self):
        r = client.post("/predict/text", json={"text": ""})
        assert r.status_code == 422

    def test_spotify_failure_falls_back_to_empty_tracks(self):
        with (
            patch.object(api, "search_tracks_cc", side_effect=Exception("no network")),
            patch.dict("os.environ", {}, clear=False),
        ):
            import os

            os.environ.pop("SPOTIFY_CLIENT_ID", None)
            os.environ.pop("SPOTIFY_CLIENT_SECRET", None)
            r = client.post("/predict/text", json={"text": "I am happy"})
        assert r.status_code == 200
        assert r.json()["tracks"] == []


class TestPredictSpeech:
    def test_happy_path(self):
        wav = _sine_wav_bytes()
        with patch.object(api, "search_tracks_cc", return_value=FAKE_TRACKS):
            r = client.post(
                "/predict/speech",
                files={"file": ("clip.wav", wav, "audio/wav")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "speech"
        assert isinstance(body["emotion"], str) and body["emotion"]
        assert isinstance(body["tracks"], list)

    def test_unsupported_extension(self):
        r = client.post(
            "/predict/speech",
            files={"file": ("clip.txt", b"not audio", "text/plain")},
        )
        assert r.status_code == 400

    def test_empty_file(self):
        r = client.post(
            "/predict/speech",
            files={"file": ("clip.wav", b"", "audio/wav")},
        )
        assert r.status_code == 400

    def test_corrupt_audio(self):
        r = client.post(
            "/predict/speech",
            files={"file": ("clip.wav", b"\x00\x01\x02" * 100, "audio/wav")},
        )
        assert r.status_code in (400, 422)

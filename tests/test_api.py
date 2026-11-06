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


class TestProbabilities:
    def test_text_probabilities_keyed_by_label(self):
        with patch.object(api, "search_tracks_cc", return_value=FAKE_TRACKS):
            r = client.post("/predict/text", json={"text": "I am feeling great today"})
        probs = r.json()["probabilities"]
        assert body_emotion_in(probs, r.json()["emotion"])
        assert abs(sum(probs.values()) - 1.0) < 0.01

    def test_speech_probabilities_cover_seven_moods(self):
        with patch.object(api, "search_tracks_cc", return_value=FAKE_TRACKS):
            r = client.post("/predict/speech", files={"file": ("clip.wav", _sine_wav_bytes(), "audio/wav")})
        assert len(r.json()["probabilities"]) == 7


def body_emotion_in(probs, emotion):
    return emotion in probs and probs[emotion] == max(probs.values())


class TestSpeechValidation:
    def test_too_short_rejected(self):
        r = client.post("/predict/speech", files={"file": ("clip.wav", _sine_wav_bytes(secs=0.2), "audio/wav")})
        assert r.status_code == 400
        assert "short" in r.json()["detail"].lower()

    def test_silence_rejected(self):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(np.zeros(16000, dtype=np.int16).tobytes())
        r = client.post("/predict/speech", files={"file": ("clip.wav", buf.getvalue(), "audio/wav")})
        assert r.status_code == 400
        assert "no speech" in r.json()["detail"].lower()

    def test_oversized_rejected(self):
        with patch.object(api, "MAX_AUDIO_BYTES", 1000):
            r = client.post("/predict/speech", files={"file": ("clip.wav", _sine_wav_bytes(), "audio/wav")})
        assert r.status_code == 413

    def test_decode_error_does_not_leak_internals(self):
        r = client.post("/predict/speech", files={"file": ("clip.wav", b"\x00\x01\x02" * 100, "audio/wav")})
        assert r.status_code == 400
        assert "Error" not in r.json()["detail"]


class TestTrackCache:
    def test_spotify_called_once_per_query_offset(self):
        with (
            patch.object(api, "search_tracks_cc", return_value=[dict(FAKE_TRACKS[0], id=f"t{i}") for i in range(10)]) as m,
            patch.object(api.random, "choice", side_effect=lambda seq: seq[0]),
        ):
            client.post("/predict/text", json={"text": "I am feeling great today"})
            client.post("/predict/text", json={"text": "I am feeling great today"})
        assert m.call_count == 1


class TestRateLimit:
    def test_429_after_limit(self):
        with (
            patch.object(api, "RATE_LIMIT_PER_MIN", 2),
            patch.object(api, "search_tracks_cc", return_value=[]),
        ):
            codes = [client.post("/predict/text", json={"text": "hi there"}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]


class TestHealthDegraded:
    def test_503_when_model_missing(self):
        with patch.object(api, "_load_text", side_effect=RuntimeError("boom")):
            r = client.get("/health")
        assert r.status_code == 503
        assert r.json()["status"] == "degraded"


class TestLiftMode:
    def test_lift_uses_lift_query(self):
        with patch.object(api, "search_tracks_cc", return_value=FAKE_TRACKS) as m:
            r = client.get("/tracks", params={"mood": "sad", "mode": "lift"})
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "lift"
        assert body["query"] == api.get_search_query("sad", "lift")
        assert body["query"] != api.get_search_query("sad", "match")
        assert m.call_args.args[0] in api.get_track_queries("sad", "lift")

    def test_text_predict_accepts_mode(self):
        with patch.object(api, "search_tracks_cc", return_value=FAKE_TRACKS):
            r = client.post("/predict/text", json={"text": "i feel so alone", "mode": "lift"})
        assert r.status_code == 200 and r.json()["mode"] == "lift"

    def test_speech_predict_accepts_mode(self):
        with patch.object(api, "search_tracks_cc", return_value=FAKE_TRACKS):
            r = client.post(
                "/predict/speech",
                files={"file": ("clip.wav", _sine_wav_bytes(), "audio/wav")},
                data={"mode": "lift"},
            )
        assert r.status_code == 200 and r.json()["mode"] == "lift"

    def test_unknown_mood_rejected(self):
        assert client.get("/tracks", params={"mood": "bored"}).status_code == 422


class TestFeedback:
    def test_store_and_export(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FEEDBACK_DB", str(tmp_path / "fb.sqlite3"))
        monkeypatch.setenv("FEEDBACK_EXPORT_TOKEN", "s3cret")
        r = client.post("/feedback", json={
            "source": "text", "predicted": "happy", "corrected": "calm",
            "confidence": 0.51, "text": "what is for lunch",
        })
        assert r.status_code == 201
        client.post("/feedback", json={
            "source": "speech", "predicted": "sad", "corrected": "angry", "text": "should be dropped",
        })
        assert client.get("/feedback/export").status_code == 401
        assert client.get("/feedback/export", headers={"Authorization": "Bearer wrong"}).status_code == 401
        rows = client.get("/feedback/export", headers={"Authorization": "Bearer s3cret"}).json()["rows"]
        assert [(x["predicted"], x["corrected"]) for x in rows] == [("sad", "angry"), ("happy", "calm")]
        assert rows[0]["text"] is None  # speech never stores text
        assert rows[1]["text"] == "what is for lunch"

    def test_export_disabled_without_token(self, monkeypatch):
        monkeypatch.delenv("FEEDBACK_EXPORT_TOKEN", raising=False)
        assert client.get("/feedback/export", headers={"Authorization": "Bearer "}).status_code == 401

    def test_invalid_correction_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FEEDBACK_DB", str(tmp_path / "fb.sqlite3"))
        r = client.post("/feedback", json={"source": "text", "predicted": "happy", "corrected": "bored"})
        assert r.status_code == 422


class TestSpotifyBudget:
    def test_slow_spotify_does_not_block_prediction(self):
        import time as _t

        def slow(*a, **k):
            _t.sleep(1.0)
            return FAKE_TRACKS

        fake_result = {
            "emotion": "happy", "confidence": 0.9, "probabilities": [0.9], "labels": ["happy"],
            "source": "text", "icon": "", "description": "",
        }
        with (
            patch.object(api, "SPOTIFY_BUDGET_S", 0.2),
            patch.object(api, "search_tracks_cc", side_effect=slow),
            patch.object(api, "predict", return_value=fake_result),  # isolate the Spotify wait
        ):
            start = _t.perf_counter()
            r = client.post("/predict/text", json={"text": "I am happy"})
            elapsed = _t.perf_counter() - start
        assert r.status_code == 200
        assert r.json()["tracks"] == []
        assert elapsed < 0.9


class TestProdHardening:
    def test_docs_disabled_by_default(self):
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/").json()["docs"] is None

    def test_security_headers(self):
        r = client.get("/health")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer"


class TestExplicitFilter:
    def test_explicit_tracks_are_filtered_and_list_topped_up(self):
        page1 = [dict(FAKE_TRACKS[0], id=f"e{i}", explicit=True) for i in range(7)] + \
                [dict(FAKE_TRACKS[0], id=f"c{i}", explicit=False) for i in range(3)]
        page2 = [dict(FAKE_TRACKS[0], id=f"d{i}", explicit=False) for i in range(10)]

        def fake(query, limit=10, offset=0, market=None):
            return page1 if offset == 0 else page2

        with patch.object(api, "search_tracks_cc", side_effect=fake), patch.object(api.random, "choice", side_effect=lambda seq: seq[0]):
            r = client.get("/tracks", params={"mood": "happy"})
        tracks = r.json()["tracks"]
        assert tracks and not any(t["explicit"] for t in tracks)
        assert len(tracks) == 10  # 3 clean from page 1 + 7 from page 2

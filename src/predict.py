import json
import logging
from pathlib import Path

import librosa
import numpy as np

from src.features import (  # noqa: F401  (re-exported for callers/tests)
    HOP_LENGTH,
    N_FFT,
    N_MELS,
    SR,
    TARGET_FRAMES,
    clean_text,
    mel_from_array,
)
from src.spotify_client import INDEX_TO_EMOTION, get_mood_info

log = logging.getLogger("moodmix.predict")

BASE_DIR = Path(__file__).resolve().parent.parent
SPEECH_MODEL_PATH = BASE_DIR / "models" / "speech_mood_model.pth"
SPEECH_ONNX_PATH = BASE_DIR / "models" / "speech_mood_model.onnx"
SPEECH_LABELS_PATH = BASE_DIR / "models" / "speech_labels.json"

# Inference-time audio handling. TESS training clips are ~2s, so we score
# overlapping ~2.5s windows across the whole (silence-trimmed) recording and
# average them instead of only looking at the first 4.1s.
TRIM_TOP_DB = 30
WINDOW_SECONDS = 2.5
HOP_SECONDS = 1.25
MAX_WINDOWS = 8
MIN_SPEECH_SECONDS = 0.3

_speech_model = None
_speech_labels = None
_text_model = None


def _load_speech_labels():
    """Label order the speech model was trained with.

    Prefers the labels file written by train.py; falls back to the
    config/mood_features.json order the shipped model was trained against.
    """
    global _speech_labels
    if _speech_labels is None:
        if SPEECH_LABELS_PATH.exists():
            _speech_labels = json.loads(SPEECH_LABELS_PATH.read_text(encoding="utf-8"))
        else:
            _speech_labels = [INDEX_TO_EMOTION[i] for i in range(len(INDEX_TO_EMOTION))]
    return _speech_labels


class _OnnxSpeech:
    """Speech CNN served by ONNX Runtime (no torch needed in production)."""

    def __init__(self, path):
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        so.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])

    def logits(self, batch):  # (B, 3, F, T) float32
        return self.session.run(None, {"mel": batch.astype(np.float32)})[0]


class _TorchSpeech:
    """Fallback for training/dev environments where only the .pth exists."""

    def __init__(self, path, num_classes):
        import torch

        from src.train import MoodCNN

        self.torch = torch
        self.model = MoodCNN(num_classes=num_classes)
        self.model.load_state_dict(torch.load(str(path), map_location="cpu", weights_only=True))
        self.model.eval()

    def logits(self, batch):
        with self.torch.no_grad():
            return self.model(self.torch.from_numpy(batch.astype(np.float32))).numpy()


def _load_speech():
    global _speech_model
    if _speech_model is None:
        if SPEECH_ONNX_PATH.exists():
            _speech_model = _OnnxSpeech(SPEECH_ONNX_PATH)
        else:
            log.warning("%s missing; falling back to torch (run src/export_onnx.py)", SPEECH_ONNX_PATH.name)
            _speech_model = _TorchSpeech(SPEECH_MODEL_PATH, len(_load_speech_labels()))
    return _speech_model


def _load_text():
    global _text_model
    if _text_model is None:
        from src.text_model import TextEmotionModel

        _text_model = TextEmotionModel()
        log.info("Text model mode: %s", _text_model.mode)
    return _text_model


# Backwards-compatible aliases (tests and older callers use these names).
_extract_mel_spectrogram = mel_from_array
_clean_text = clean_text


def _speech_windows(audio_data):
    """Trim silence and split into overlapping windows at SR."""
    audio = np.asarray(audio_data, dtype=np.float32)
    if audio.size and np.max(np.abs(audio)) > 0:
        trimmed, _ = librosa.effects.trim(audio, top_db=TRIM_TOP_DB)
        if trimmed.size >= int(MIN_SPEECH_SECONDS * SR):
            audio = trimmed
    win = int(WINDOW_SECONDS * SR)
    hop = int(HOP_SECONDS * SR)
    if audio.size <= win:
        return [audio]
    starts = list(range(0, audio.size - win + 1, hop))
    if len(starts) > MAX_WINDOWS:
        idx = np.linspace(0, len(starts) - 1, MAX_WINDOWS).round().astype(int)
        starts = [starts[i] for i in idx]
    return [audio[s:s + win] for s in starts]


def _softmax(x):
    e = np.exp(x - x.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def predict_speech(audio_data, sr=SR):
    model = _load_speech()
    labels = _load_speech_labels()
    if sr != SR:
        audio_data = librosa.resample(np.asarray(audio_data, dtype=np.float32), orig_sr=sr, target_sr=SR)
    windows = _speech_windows(audio_data)
    # (B, F, T, 3) -> (B, 3, F, T)
    batch = np.stack([mel_from_array(w, SR) for w in windows]).transpose(0, 3, 1, 2)
    probs = _softmax(model.logits(batch)).mean(axis=0)
    idx = int(np.argmax(probs))
    return labels[idx], float(probs[idx]), probs.tolist()


def predict_text(text):
    model = _load_text()
    probs = model.predict_proba(text)
    idx = int(np.argmax(probs))
    return model.labels[idx], float(probs[idx]), [float(p) for p in probs]


def class_labels(source):
    """Label order matching the `probabilities` list for a given source."""
    if source == "speech":
        return list(_load_speech_labels())
    return list(_load_text().labels)


def predict(audio_data=None, text=None, sr=16000):
    if audio_data is not None:
        emotion, confidence, probs = predict_speech(audio_data, sr)
        source = "speech"
    elif text and text.strip():
        emotion, confidence, probs = predict_text(text)
        source = "text"
    else:
        return None
    mood_info = get_mood_info(emotion)
    return {
        "emotion": emotion,
        "confidence": confidence,
        "probabilities": probs,
        "labels": class_labels(source),
        "source": source,
        "icon": mood_info["icon"] if mood_info else "fa-music",
        "description": mood_info["description"] if mood_info else "",
    }

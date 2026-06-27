import re
import string
import pickle
import numpy as np
import torch
import librosa
from pathlib import Path
from src.spotify_client import EMOTIONS, INDEX_TO_EMOTION, get_mood_info

BASE_DIR = Path(__file__).resolve().parent.parent
SPEECH_MODEL_PATH = BASE_DIR / "models" / "speech_mood_model.pth"
TEXT_MODEL_PATH = BASE_DIR / "models" / "text_mood_pipeline.pkl"

SR = 16000
N_MELS = 128
HOP_LENGTH = 512
N_FFT = 2048
TARGET_FRAMES = 128

_speech_model = None
_text_pipeline = None
_device = None

def _build_speech_model():
    from src.train import MoodCNN
    model = MoodCNN(num_classes=7)
    model.load_state_dict(torch.load(str(SPEECH_MODEL_PATH), map_location="cpu"))
    model.eval()
    return model

def _load_speech():
    global _speech_model, _device
    if _speech_model is None:
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _speech_model = _build_speech_model().to(_device)
        _speech_model.eval()
    return _speech_model

def _load_text():
    global _text_pipeline
    if _text_pipeline is None:
        with open(str(TEXT_MODEL_PATH), "rb") as f:
            _text_pipeline = pickle.load(f)
    return _text_pipeline

def _extract_mel_spectrogram(audio_data, sr=SR):
    if sr != SR:
        audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=SR)
    mel_spec = librosa.feature.melspectrogram(
        y=audio_data, sr=SR, n_mels=N_MELS, hop_length=HOP_LENGTH, n_fft=N_FFT
    )
    mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
    if mel_spec_db.shape[1] < TARGET_FRAMES:
        pad_width = TARGET_FRAMES - mel_spec_db.shape[1]
        mel_spec_db = np.pad(mel_spec_db, ((0, 0), (0, pad_width)), mode="constant")
    else:
        mel_spec_db = mel_spec_db[:, :TARGET_FRAMES]
    mel_spec_db = mel_spec_db.astype(np.float32)
    mel_spec_db = (mel_spec_db - mel_spec_db.mean()) / (mel_spec_db.std() + 1e-8)
    mel_spec_3ch = np.stack([mel_spec_db] * 3, axis=-1)
    return mel_spec_3ch

def _clean_text(text):
    text = text.lower()
    text = re.sub(f"[{re.escape(string.punctuation)}]", " ", text)
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def predict_speech(audio_data, sr=SR):
    model = _load_speech()
    mel = _extract_mel_spectrogram(audio_data, sr)
    mel_tensor = torch.tensor(mel, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
    with torch.no_grad():
        outputs = model(mel_tensor.to(_device))
        probs = torch.softmax(outputs, dim=1)[0]
        idx = int(torch.argmax(probs).item())
        confidence = float(probs[idx].item())
    return INDEX_TO_EMOTION[idx], confidence, probs.tolist()

def predict_text(text):
    pipeline = _load_text()
    vectorizer = pipeline["vectorizer"]
    model = pipeline["model"]
    emotions = pipeline["emotions"]
    cleaned = _clean_text(text)
    vec = vectorizer.transform([cleaned])
    probs = model.predict_proba(vec)[0]
    idx = int(np.argmax(probs))
    confidence = float(probs[idx])
    return emotions[idx], confidence, probs.tolist()

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
        "source": source,
        "icon": mood_info["icon"] if mood_info else "fa-music",
        "description": mood_info["description"] if mood_info else "",
    }

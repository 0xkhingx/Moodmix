"""Feature extraction shared by training (preprocess.py) and serving (predict.py).

Keeping a single implementation guarantees the model sees identically
processed inputs at train and inference time.
"""

import re
import string

import librosa
import numpy as np

SR = 16000
N_MELS = 128
HOP_LENGTH = 512
N_FFT = 2048
TARGET_FRAMES = 128

_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")
_DIGITS_RE = re.compile(r"\d+")
_SPACE_RE = re.compile(r"\s+")


def mel_from_array(audio_data, sr=SR):
    """Return a normalized (N_MELS, TARGET_FRAMES, 3) log-mel spectrogram."""
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
    return np.stack([mel_spec_db] * 3, axis=-1)


def mel_from_file(file_path):
    y, sr = librosa.load(file_path, sr=SR, mono=True)
    return mel_from_array(y, sr)


def clean_text(text):
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _DIGITS_RE.sub("", text)
    return _SPACE_RE.sub(" ", text).strip()

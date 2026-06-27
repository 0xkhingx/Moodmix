import os
import re
import string
import zipfile
import numpy as np
import pandas as pd
import librosa
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
import argparse

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

SR = 16000
N_MELS = 128
HOP_LENGTH = 512
N_FFT = 2048
TARGET_FRAMES = 128

TESS_DIR = DATA_DIR / "TESS"

TESS_EMOTION_MAP = {
    "happy": 0,
    "sad": 1,
    "angry": 2,
    "calm": 3,
    "neutral": 3,
    "fearful": 4,
    "fear": 4,
    "surprised": 5,
    "surprise": 5,
    "ps": 5,
    "disgust": 6,
}

TEXT_LABEL_MAP = {
    "joy": "happy",
    "happiness": "happy",
    "sadness": "sad",
    "sad": "sad",
    "anger": "angry",
    "angry": "angry",
    "fear": "fearful",
    "fearful": "fearful",
    "surprise": "surprised",
    "surprised": "surprised",
    "disgust": "disgusted",
    "disgusted": "disgusted",
    "calm": "calm",
    "calmness": "calm",
    "neutral": "calm",
    "love": "happy",
    "shame": "sad",
    "guilt": "sad",
}

def extract_mel_spectrogram(file_path):
    y, sr = librosa.load(file_path, sr=SR, mono=True)
    mel_spec = librosa.feature.melspectrogram(
        y=y, sr=sr, n_mels=N_MELS, hop_length=HOP_LENGTH, n_fft=N_FFT
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

def load_tess():
    X, y = [], []
    tess_path = Path(TESS_DIR)
    if not tess_path.exists():
        zip_path = DATA_DIR / "TESS.zip"
        if zip_path.exists():
            print("Extracting TESS.zip...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(DATA_DIR)
        else:
            raise FileNotFoundError(f"TESS not found at {tess_path} or {zip_path}")
    wav_files = list(tess_path.rglob("*.wav"))
    if not wav_files:
        subdirs = [d for d in tess_path.iterdir() if d.is_dir()]
        for sub in subdirs:
            wav_files.extend(list(sub.rglob("*.wav")))
    if not wav_files:
        raise FileNotFoundError(f"No .wav files in {tess_path}")
    for fpath in wav_files:
        parts = fpath.stem.lower().split("_")
        label = None
        for emotion_key in TESS_EMOTION_MAP:
            if emotion_key in parts:
                label = TESS_EMOTION_MAP[emotion_key]
                break
        if label is None:
            continue
        mel = extract_mel_spectrogram(str(fpath))
        X.append(mel)
        y.append(label)
    return np.array(X), np.array(y)

def clean_text(text):
    text = text.lower()
    text = re.sub(f"[{re.escape(string.punctuation)}]", " ", text)
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def load_text_dataset():
    text_dir = DATA_DIR / "text_emotion"
    df_list = []
    source_dir = None
    for candidate in [text_dir, DATA_DIR / "text_emotion_txt"]:
        if candidate.exists() and list(candidate.glob("*.txt")):
            source_dir = candidate
            break
    if source_dir:
        for txt_file in sorted(source_dir.glob("*.txt")):
            lines = txt_file.read_text(encoding="utf-8", errors="replace").strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line or ";" not in line:
                    continue
                parts = line.rsplit(";", 1)
                if len(parts) != 2:
                    continue
                text, label = parts
                df_list.append({"text": text.strip(), "emotion": label.strip().lower()})
        if df_list:
            df = pd.DataFrame(df_list)
        else:
            raise ValueError("Could not parse any lines from .txt files")
    else:
        possible_csv = [
            DATA_DIR / "text_emotion.csv",
            DATA_DIR / "emotion_dataset.csv",
            DATA_DIR / "isear.csv",
        ]
        df = None
        for p in possible_csv:
            if p.exists():
                df = pd.read_csv(p)
                break
        if df is None:
            raise FileNotFoundError("No text emotion dataset found")
        text_col = label_col = None
        for col in df.columns:
            cl = col.lower()
            if any(x in cl for x in ["text", "sentence", "tweet", "content"]):
                text_col = col
            if any(x in cl for x in ["emotion", "label", "sentiment"]):
                label_col = col
        if text_col is None or label_col is None:
            raise ValueError(f"Could not find columns in {list(df.columns)}")
        df = df[[text_col, label_col]].dropna()
        df.columns = ["text", "emotion"]
    df["emotion"] = df["emotion"].str.lower().map(TEXT_LABEL_MAP)
    df = df.dropna(subset=["emotion"])
    df["text"] = df["text"].apply(clean_text)
    df = df[df["text"].str.len() > 3]
    return df

def preprocess_speech():
    print("Loading TESS dataset...")
    X, y = load_tess()
    print(f"Loaded {len(X)} samples, shape: {X.shape}")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=0.15 / 0.85, random_state=42, stratify=y_train
    )
    np.save(str(PROCESSED_DIR / "X_train.npy"), X_train)
    np.save(str(PROCESSED_DIR / "X_val.npy"), X_val)
    np.save(str(PROCESSED_DIR / "X_test.npy"), X_test)
    np.save(str(PROCESSED_DIR / "y_train.npy"), y_train)
    np.save(str(PROCESSED_DIR / "y_val.npy"), y_val)
    np.save(str(PROCESSED_DIR / "y_test.npy"), y_test)
    print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

def preprocess_text():
    print("Loading text emotion dataset...")
    df = load_text_dataset()
    if len(df) == 0:
        raise ValueError("No samples after processing")
    print(f"Loaded {len(df)} samples")
    emotions = sorted(df["emotion"].unique())
    emotion_to_idx = {e: i for i, e in enumerate(emotions)}
    df["label_idx"] = df["emotion"].map(emotion_to_idx)
    print(f"Emotions: {emotions}")
    print(df["emotion"].value_counts())
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"], df["label_idx"], test_size=0.2, random_state=42, stratify=df["label_idx"]
    )
    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    import scipy.sparse
    with open(str(PROCESSED_DIR / "text_train.npz"), "wb") as f:
        scipy.sparse.save_npz(f, X_train_vec)
    with open(str(PROCESSED_DIR / "text_test.npz"), "wb") as f:
        scipy.sparse.save_npz(f, X_test_vec)
    np.save(str(PROCESSED_DIR / "text_y_train.npy"), y_train.to_numpy())
    np.save(str(PROCESSED_DIR / "text_y_test.npy"), y_test.to_numpy())
    with open(str(PROCESSED_DIR / "text_vectorizer.pkl"), "wb") as f:
        pickle.dump(vectorizer, f)
    with open(str(PROCESSED_DIR / "text_emotions.pkl"), "wb") as f:
        pickle.dump(emotions, f)
    print(f"Train: {X_train_vec.shape[0]}, Test: {X_test_vec.shape[0]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["speech", "text", "all"], default="all")
    args = parser.parse_args()
    if args.mode in ("speech", "all"):
        preprocess_speech()
    if args.mode in ("text", "all"):
        preprocess_text()
    print("Preprocessing complete.")

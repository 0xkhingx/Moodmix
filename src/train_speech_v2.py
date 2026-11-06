"""Retrain the speech CNN on CREMA-D (91 actors) + TESS, with speaker-held-out evaluation.

Why: the shipped model was trained on TESS alone (2 speakers, random split), so
its 96% test accuracy says little about new voices. CREMA-D adds 91 actors of
varied age/ethnicity; we split it BY ACTOR so test voices are never heard in
training. TESS (2 speakers, cannot be speaker-split) stays in training mainly
to supply the "surprised" class, which CREMA-D lacks.

Pre-processing mirrors inference exactly (src/predict.py): trim silence, cut
2.5s windows, log-mel per window; clip-level predictions average the windows.

Usage:
  python src/train_speech_v2.py            # extract features (cached), train, evaluate
  python src/train_speech_v2.py --promote  # ...and replace the shipped model if it wins

Data (git-ignored):
  data/CREMA-D/*.wav   https://github.com/CheyneyComputerScience/CREMA-D (ODbL)
  data/TESS/**/*.wav   https://doi.org/10.5683/SP2/E8H2MF (CC BY-NC 4.0 — non-commercial)
"""

import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
CREMA_DIR = DATA_DIR / "CREMA-D"
TESS_DIR = DATA_DIR / "TESS"
CACHE = DATA_DIR / "processed" / "speech_v2_features.npz"
MODELS_DIR = BASE_DIR / "models"
CANDIDATE = MODELS_DIR / "speech_mood_model.candidate.pth"

MOODS = ["happy", "sad", "angry", "calm", "fearful", "surprised", "disgusted"]
CREMA_MAP = {"HAP": "happy", "SAD": "sad", "ANG": "angry", "NEU": "calm",
             "FEA": "fearful", "DIS": "disgusted"}
TESS_MAP = {"happy": "happy", "sad": "sad", "angry": "angry", "neutral": "calm",
            "fear": "fearful", "ps": "surprised", "disgust": "disgusted"}
SEED = 0


def list_clips():
    clips = []  # (path, mood, dataset, speaker)
    for p in sorted(CREMA_DIR.glob("*.wav")):
        actor, _, emo, _ = p.stem.split("_")
        clips.append((str(p), CREMA_MAP[emo], "crema", f"crema_{actor}"))
    for p in sorted(TESS_DIR.rglob("*.wav")):
        parts = p.stem.lower().split("_")
        mood = TESS_MAP.get(parts[-1])
        if mood:
            clips.append((str(p), mood, "tess", f"tess_{parts[0]}"))
    return clips


def split_clips(clips):
    """CREMA-D by actor (70/15/15); TESS stratified at random (only 2 speakers)."""
    rng = np.random.default_rng(SEED)
    actors = sorted({c[3] for c in clips if c[2] == "crema"})
    rng.shuffle(actors)
    n = len(actors)
    a_val = set(actors[int(0.70 * n):int(0.85 * n)])
    a_test = set(actors[int(0.85 * n):])
    split = []
    tess_idx = [i for i, c in enumerate(clips) if c[2] == "tess"]
    tess_split = {}
    for mood in MOODS:
        idx = [i for i in tess_idx if clips[i][1] == mood]
        rng.shuffle(idx)
        k = len(idx)
        for j, i in enumerate(idx):
            tess_split[i] = "train" if j < 0.70 * k else ("val" if j < 0.85 * k else "test")
    for i, c in enumerate(clips):
        if c[2] == "crema":
            split.append("val" if c[3] in a_val else "test" if c[3] in a_test else "train")
        else:
            split.append(tess_split[i])
    return np.array(split)


def _features(path):
    import librosa

    from src.features import mel_from_array
    from src.predict import SR, _speech_windows

    y, _ = librosa.load(path, sr=SR, mono=True)
    return [mel_from_array(w, SR)[:, :, 0].astype(np.float16) for w in _speech_windows(y)]


def extract(clips):
    if CACHE.exists():
        z = np.load(CACHE)
        if len(z["clip_y"]) == len(clips):
            return z["X"], z["win_clip"], z["clip_y"]
    t0 = time.perf_counter()
    X, win_clip = [], []
    with Pool(4) as pool:
        for ci, mels in enumerate(pool.imap(_features, [c[0] for c in clips], chunksize=16)):
            X.extend(mels)
            win_clip.extend([ci] * len(mels))
            if ci and ci % 1000 == 0:
                print(f"  features {ci}/{len(clips)} ({time.perf_counter() - t0:.0f}s)", flush=True)
    X = np.stack(X)
    win_clip = np.array(win_clip)
    clip_y = np.array([MOODS.index(c[1]) for c in clips])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE, X=X, win_clip=win_clip, clip_y=clip_y)
    return X, win_clip, clip_y


def clip_probs(logits_fn, X, win_clip, clip_ids, bs=128):
    """Average window softmax per clip (same as inference)."""
    mask = np.isin(win_clip, clip_ids)
    Xw, cw = X[mask], win_clip[mask]
    probs = []
    for i in range(0, len(Xw), bs):
        b = np.repeat(Xw[i:i + bs, None].astype(np.float32), 3, axis=1)
        z = logits_fn(b)
        e = np.exp(z - z.max(1, keepdims=True))
        probs.append(e / e.sum(1, keepdims=True))
    probs = np.concatenate(probs)
    out = np.zeros((len(clip_ids), probs.shape[1]))
    pos = {c: i for i, c in enumerate(clip_ids)}
    counts = np.zeros(len(clip_ids))
    for p, c in zip(probs, cw):
        out[pos[c]] += p
        counts[pos[c]] += 1
    return out / counts[:, None]


def scores(probs, y, labels=None):
    from sklearn.metrics import accuracy_score, f1_score

    pred = probs.argmax(1)
    labels = labels if labels is not None else sorted(set(y))
    return {"macro_f1": float(f1_score(y, pred, average="macro", labels=labels)),
            "accuracy": float(accuracy_score(y, pred)), "n": int(len(y))}


def main():
    import torch
    import torch.nn as nn
    from sklearn.utils.class_weight import compute_class_weight

    from src.train import MoodCNN, spec_augment

    ap = argparse.ArgumentParser()
    ap.add_argument("--promote", action="store_true")
    ap.add_argument("--epochs", type=int, default=40)
    args = ap.parse_args()
    torch.manual_seed(SEED)
    torch.set_num_threads(4)

    clips = list_clips()
    if not any(c[2] == "crema" for c in clips):
        sys.exit("No CREMA-D clips in data/CREMA-D")
    split = split_clips(clips)
    datasets = np.array([c[2] for c in clips])
    print(f"clips: {len(clips)} (crema {sum(datasets == 'crema')}, tess {sum(datasets == 'tess')})")
    for s in ["train", "val", "test"]:
        print(f"  {s}: {sum(split == s)} clips")

    X, win_clip, clip_y = extract(clips)
    print(f"windows: {len(X)}")
    clip_split = split
    train_w = np.isin(win_clip, np.where(clip_split == "train")[0])
    Xtr = torch.from_numpy(X[train_w].astype(np.float32))
    ytr = torch.from_numpy(clip_y[win_clip[train_w]]).long()

    model = MoodCNN(num_classes=len(MOODS))
    weights = compute_class_weight("balanced", classes=np.arange(len(MOODS)), y=ytr.numpy())
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float32))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", factor=0.5, patience=3)

    def logits_np(b):
        model.eval()
        with torch.no_grad():
            return model(torch.from_numpy(b)).numpy()

    val_ids = np.where(clip_split == "val")[0]
    best, bad, patience = -1.0, 0, 7
    for epoch in range(args.epochs):
        model.train()
        t0 = time.perf_counter()
        perm = torch.randperm(len(Xtr))
        total = 0.0
        for i in range(0, len(perm), 64):
            idx = perm[i:i + 64]
            xb = Xtr[idx].unsqueeze(1).repeat(1, 3, 1, 1)
            opt.zero_grad()
            loss = criterion(model(spec_augment(xb)), ytr[idx])
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        v = scores(clip_probs(logits_np, X, win_clip, val_ids), clip_y[val_ids])
        sched.step(v["macro_f1"])
        print(f"epoch {epoch + 1}: loss {total / len(perm):.3f}  val macro-F1 {v['macro_f1']:.3f} "
              f"acc {v['accuracy']:.3f}  ({time.perf_counter() - t0:.0f}s)", flush=True)
        if v["macro_f1"] > best:
            best, bad = v["macro_f1"], 0
            torch.save(model.state_dict(), CANDIDATE)
        else:
            bad += 1
            if bad >= patience:
                print("early stop")
                break

    model.load_state_dict(torch.load(CANDIDATE, weights_only=True))

    # Baseline: the currently shipped model, scored on the same clips.
    from src.predict import _load_speech

    shipped = _load_speech()
    report = {}
    for name, sel in [("crema_test_heldout_speakers", (clip_split == "test") & (datasets == "crema")),
                      ("tess_test", (clip_split == "test") & (datasets == "tess"))]:
        ids = np.where(sel)[0]
        y = clip_y[ids]
        new = scores(clip_probs(logits_np, X, win_clip, ids), y)
        old = scores(clip_probs(shipped.logits, X, win_clip, ids), y)
        report[name] = {"new": new, "shipped": old}
        print(f"{name}: shipped macro-F1 {old['macro_f1']:.3f} acc {old['accuracy']:.3f}  ->  "
              f"new macro-F1 {new['macro_f1']:.3f} acc {new['accuracy']:.3f}  (n={new['n']})")

    out = MODELS_DIR / "speech_v2_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    wins = report["crema_test_heldout_speakers"]["new"]["macro_f1"] > \
        report["crema_test_heldout_speakers"]["shipped"]["macro_f1"]
    print(f"new model {'BEATS' if wins else 'does NOT beat'} shipped model on held-out speakers")

    if args.promote and wins:
        import shutil

        from src.train import _update_manifest

        shutil.copy(CANDIDATE, MODELS_DIR / "speech_mood_model.pth")
        (MODELS_DIR / "speech_labels.json").write_text(json.dumps(MOODS), encoding="utf-8")
        from src.export_onnx import export

        export()
        _update_manifest("speech", {
            "file": "speech_mood_model.onnx",
            "labels": MOODS,
            "dataset": "CREMA-D (split by actor) + TESS",
            "test_crema_heldout_speakers": report["crema_test_heldout_speakers"]["new"],
            "test_tess": report["tess_test"]["new"],
            "previous_model_same_test": report["crema_test_heldout_speakers"]["shipped"],
            "best_val_macro_f1": best,
        })
        print("Promoted: models/speech_mood_model.pth + .onnx updated")


if __name__ == "__main__":
    main()

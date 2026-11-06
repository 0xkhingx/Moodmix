"""Fit the text stacker that fuses TF-IDF/LR with GoEmotions RoBERTa.

Leakage rules:
  * The stacker is fit ONLY on validation splits (dair-ai val.txt + GoEmotions
    validation). Neither base model saw those rows during its own training.
  * Reported metrics use the test splits (dair-ai test.txt + GoEmotions test).

Usage:
  python scripts/fetch_models.py          # GoEmotions ONNX model
  python src/train_text_combiner.py       # 1000 rows per split (~10 min on a laptop CPU)
  python src/train_text_combiner.py --all # every row (slower, slightly better)

Writes models/text_combiner.pkl and a "text_combiner" entry in models/manifest.json.
Training-only deps: pandas, pyarrow (to read the GoEmotions parquet files).
"""

import argparse
import hashlib
import json
import pickle
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import accuracy_score, f1_score  # noqa: E402

from src.text_model import (  # noqa: E402
    COMBINER_PATH,
    GOEMO_GROUPS,
    MOODS,
    GoEmotions,
    TextEmotionModel,
    stack_features,
)

DATA_DIR = BASE_DIR / "data"
DAIR_DIR = DATA_DIR / "text_emotion"
GO_DIR = DATA_DIR / "goemotions"
CACHE_DIR = DATA_DIR / "processed" / "combiner_features"
MANIFEST_PATH = BASE_DIR / "models" / "manifest.json"

# google-research-datasets/go_emotions ("simplified" config), Apache-2.0.
GO_REPO = "google-research-datasets/go_emotions"
GO_REVISION = "add492243ff905527e67aeb8b80c082af02207c3"
GO_FILES = {
    "validation": "d46ad5633c4fa41829d22d549743a7bf858d94129536a02af7280c281db5e63a",
    "test": "fd0953e535ba2569edc6a1daaa1133f8e4b9071691d540c9bab812fda132bc26",
}

DAIR_TO_MOOD = {"joy": "happy", "love": "happy", "sadness": "sad", "anger": "angry",
                "fear": "fearful", "surprise": "surprised"}
GO_LABEL_TO_MOOD = {l: m for m, ls in GOEMO_GROUPS.items() for l in ls}

STACKER_C = 1.0  # selected on validation mean macro-F1 (grid 0.1 / 0.3 / 1.0)


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fetch_goemotions():
    GO_DIR.mkdir(parents=True, exist_ok=True)
    for split, expected in GO_FILES.items():
        target = GO_DIR / f"{split}.parquet"
        if target.exists() and _sha256(target) == expected:
            continue
        url = (f"https://huggingface.co/datasets/{GO_REPO}/resolve/{GO_REVISION}"
               f"/simplified/{split}-00000-of-00001.parquet")
        print(f"fetch {url}")
        urllib.request.urlretrieve(url, target)
        if _sha256(target) != expected:
            target.unlink()
            sys.exit(f"Checksum mismatch for GoEmotions {split}")


def load_dair(split):
    rows = []
    for line in (DAIR_DIR / f"{split}.txt").read_text(encoding="utf-8").splitlines():
        if ";" in line:
            text, label = line.rsplit(";", 1)
            rows.append((text, DAIR_TO_MOOD[label.strip()]))
    return [r[0] for r in rows], [r[1] for r in rows]


def load_go(split, go_labels):
    import pandas as pd

    df = pd.read_parquet(GO_DIR / f"{split}.parquet")
    texts, ys = [], []
    for text, labs in zip(df.text, df.labels):
        moods = {GO_LABEL_TO_MOOD[go_labels[i]] for i in labs}
        if len(moods) == 1:  # unambiguous rows only
            texts.append(text)
            ys.append(moods.pop())
    return texts, ys


def subsample(texts, ys, n, seed=0):
    if n is None or len(texts) <= n:
        return texts, ys
    idx = np.random.default_rng(seed).choice(len(texts), n, replace=False)
    return [texts[i] for i in idx], [ys[i] for i in idx]


def features(name, texts, base: TextEmotionModel, goemo: GoEmotions):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()[:16]
    cache = CACHE_DIR / f"{name}_{digest}.npz"
    if cache.exists():
        z = np.load(cache)
        return z["L"], z["G"]
    L = np.zeros((len(texts), len(base.lr_labels)), dtype=np.float32)
    G = np.zeros((len(texts), len(goemo.labels)), dtype=np.float32)
    for i, t in enumerate(texts):
        if i and i % 250 == 0:
            print(f"  {name}: {i}/{len(texts)}", flush=True)
        L[i] = base.lr_probs(t)
        G[i] = goemo.sigmoid(t)
    np.savez(cache, L=L, G=G)
    return L, G


def evaluate(stacker, L, G, y):
    order = [list(stacker.classes_).index(m) for m in MOODS]
    P = stacker.predict_proba(np.stack([stack_features(l, g) for l, g in zip(L, G)]))[:, order]
    pred = [MOODS[i] for i in P.argmax(1)]
    return {
        "macro_f1": float(f1_score(y, pred, average="macro", labels=sorted(set(y)))),
        "accuracy": float(accuracy_score(y, pred)),
        "n": len(y),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="use every row instead of 1000 per split")
    args = ap.parse_args()
    n = None if args.all else 1000

    fetch_goemotions()
    base = TextEmotionModel.__new__(TextEmotionModel)  # LR part only
    with open(BASE_DIR / "models" / "text_mood_pipeline.pkl", "rb") as f:
        pipe = pickle.load(f)
    base.vectorizer, base.lr, base.lr_labels = pipe["vectorizer"], pipe["model"], list(pipe["emotions"])
    goemo = GoEmotions(threads=4)

    splits = {}
    for name, loader, split in [("dair_val", load_dair, "val"), ("dair_test", load_dair, "test")]:
        X, y = subsample(*loader(split), n)
        splits[name] = (*features(name, X, base, goemo), y)
    for name, split in [("go_val", "validation"), ("go_test", "test")]:
        X, y = subsample(*load_go(split, goemo.labels), n)
        splits[name] = (*features(name, X, base, goemo), y)

    Lv = np.vstack([splits["dair_val"][0], splits["go_val"][0]])
    Gv = np.vstack([splits["dair_val"][1], splits["go_val"][1]])
    yv = splits["dair_val"][2] + splits["go_val"][2]
    stacker = LogisticRegression(C=STACKER_C, max_iter=3000, class_weight="balanced")
    stacker.fit(np.stack([stack_features(l, g) for l, g in zip(Lv, Gv)]), yv)

    metrics = {name: evaluate(stacker, *splits[name]) for name in ["dair_test", "go_test"]}
    for name, m in metrics.items():
        print(f"{name}: macro-F1={m['macro_f1']:.3f} acc={m['accuracy']:.3f} (n={m['n']})")

    with open(COMBINER_PATH, "wb") as f:
        pickle.dump({"model": stacker, "moods": MOODS, "lr_labels": base.lr_labels,
                     "go_labels": goemo.labels}, f)

    import sklearn

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    manifest["text_combiner"] = {
        "file": COMBINER_PATH.name,
        "method": f"LogisticRegression stacker (C={STACKER_C}, balanced) on [log LR probs, log GoEmotions sigmoids]",
        "base_models": {
            "tfidf_lr": "text_mood_pipeline.pkl",
            "goemotions": "SamLowe/roberta-base-go_emotions-onnx (int8, MIT), see scripts/fetch_models.py",
        },
        "fit_on": "dair-ai val.txt + GoEmotions validation" + ("" if args.all else " (1000 rows each, seed 0)"),
        "test_metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scikit_learn": sklearn.__version__,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Saved {COMBINER_PATH.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()

"""Text emotion model: TF-IDF/LR + GoEmotions RoBERTa (ONNX), fused by a stacker.

Why a combination: the TF-IDF/LR model is very strong on the dair-ai "i feel…"
style it was trained on but has no neutral/disgust classes and collapses on
general text; GoEmotions RoBERTa handles neutral, disgust, negation and
everyday text but is weaker on the dair-ai style. A small logistic-regression
stacker, fit on held-out validation data from both domains, learns how much to
trust each. See src/train_text_combiner.py and models/manifest.json.

Falls back to TF-IDF/LR alone if the GoEmotions files or the stacker are
missing (e.g. scripts/fetch_models.py was not run).
"""

import json
import logging
import pickle
from pathlib import Path

import numpy as np

from src.features import clean_text

log = logging.getLogger("moodmix.text_model")

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
LR_PATH = MODELS_DIR / "text_mood_pipeline.pkl"
GOEMO_DIR = MODELS_DIR / "goemotions"
COMBINER_PATH = MODELS_DIR / "text_combiner.pkl"

MOODS = ["happy", "sad", "angry", "calm", "fearful", "surprised", "disgusted"]

# GoEmotions' 28 labels grouped into the app's 7 moods (neutral -> calm).
GOEMO_GROUPS = {
    "happy": ["admiration", "amusement", "approval", "caring", "excitement", "gratitude",
              "joy", "love", "optimism", "pride", "relief", "desire"],
    "sad": ["sadness", "grief", "disappointment", "remorse", "embarrassment"],
    "angry": ["anger", "annoyance", "disapproval"],
    "calm": ["neutral"],
    "fearful": ["fear", "nervousness"],
    "surprised": ["surprise", "realization", "confusion", "curiosity"],
    "disgusted": ["disgust"],
}

MAX_TOKENS = 128


class GoEmotions:
    """Minimal ONNX Runtime + tokenizers runner (no torch/transformers needed)."""

    def __init__(self, model_dir: Path = GOEMO_DIR, threads: int = 2):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        self.labels = [cfg["id2label"][str(i)] for i in range(len(cfg["id2label"]))]
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(model_dir / "model_quantized.onnx"), so, providers=["CPUExecutionProvider"]
        )
        self.group_idx = {m: [self.labels.index(l) for l in GOEMO_GROUPS[m]] for m in MOODS}

    def sigmoid(self, text: str) -> np.ndarray:
        """Per-label sigmoid scores (multi-label model), shape (28,)."""
        enc = self.tokenizer.encode(text)
        feeds = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
        }
        logits = self.session.run(None, feeds)[0][0]
        return 1.0 / (1.0 + np.exp(-logits))

    def moods(self, sig: np.ndarray) -> np.ndarray:
        agg = np.array([sig[self.group_idx[m]].max() for m in MOODS])
        return agg / agg.sum()


def stack_features(lr_probs: np.ndarray, goemo_sig: np.ndarray) -> np.ndarray:
    """Stacker input: log-probs from LR (5) and log-sigmoids from GoEmotions (28)."""
    return np.hstack([np.log(lr_probs + 1e-6), np.log(goemo_sig + 1e-6)])


class TextEmotionModel:
    def __init__(self):
        with open(LR_PATH, "rb") as f:
            pipe = pickle.load(f)
        self.vectorizer = pipe["vectorizer"]
        self.lr = pipe["model"]
        self.lr_labels = list(pipe["emotions"])

        self.goemo = None
        self.stacker = None
        try:
            self.goemo = GoEmotions()
            with open(COMBINER_PATH, "rb") as f:
                combiner = pickle.load(f)
            self.stacker = combiner["model"]
            if combiner.get("lr_labels") != self.lr_labels:
                raise ValueError("text_combiner.pkl was fit against a different LR label order")
            self._order = [list(self.stacker.classes_).index(m) for m in MOODS]
            self.labels = list(MOODS)
            self.mode = "ensemble"
        except Exception as e:  # missing files -> degrade gracefully
            log.warning("Text ensemble unavailable (%s); using TF-IDF/LR only", e)
            self.goemo = self.stacker = None
            self.labels = list(self.lr_labels)
            self.mode = "lr"

    def lr_probs(self, text: str) -> np.ndarray:
        return self.lr.predict_proba(self.vectorizer.transform([clean_text(text)]))[0]

    def predict_proba(self, text: str) -> np.ndarray:
        """Probabilities aligned with self.labels."""
        lr_p = self.lr_probs(text)
        if self.mode != "ensemble":
            return lr_p
        sig = self.goemo.sigmoid(text)
        x = stack_features(lr_p, sig)[None, :]
        return self.stacker.predict_proba(x)[0][self._order]

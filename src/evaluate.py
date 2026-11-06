import sys
import numpy as np
import torch
import pickle
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.metrics import (
    confusion_matrix, classification_report, f1_score, precision_score,
    recall_score, accuracy_score
)
from torch.utils.data import DataLoader, TensorDataset

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.size": 12, "axes.titlesize": 14})

EMOTIONS = ["happy", "sad", "angry", "calm", "fearful", "surprised", "disgusted"]

def plot_confusion_matrix(y_true, y_pred, labels, title, filename):
    cm = confusion_matrix(y_true, y_pred)
    cm_norm = cm.astype("float") / cm.sum(axis=1, keepdims=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    sns.heatmap(cm, annot=True, fmt="d", xticklabels=labels, yticklabels=labels,
                cmap="Blues", ax=ax1, cbar_kws={"shrink": 0.8})
    ax1.set_xlabel("Predicted")
    ax1.set_ylabel("True")
    ax1.set_title(f"{title} - Raw Counts")

    sns.heatmap(cm_norm, annot=True, fmt=".2%", xticklabels=labels, yticklabels=labels,
                cmap="Blues", ax=ax2, cbar_kws={"shrink": 0.8}, vmin=0, vmax=1)
    ax2.set_xlabel("Predicted")
    ax2.set_ylabel("True")
    ax2.set_title(f"{title} - Normalized")

    plt.tight_layout()
    plt.savefig(str(REPORTS_DIR / filename), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {filename}")

def plot_per_class_metrics(y_true, y_pred, labels, title, filename):
    precision = precision_score(y_true, y_pred, average=None, zero_division=0)
    recall = recall_score(y_true, y_pred, average=None, zero_division=0)
    f1 = f1_score(y_true, y_pred, average=None, zero_division=0)
    acc_per_class = np.array([
        accuracy_score(y_true[y_true == i], y_pred[y_true == i])
        for i in range(len(labels))
    ])

    x = np.arange(len(labels))
    width = 0.2

    fig, ax = plt.subplots(figsize=(14, 6))
    bars1 = ax.bar(x - 1.5*width, precision, width, label="Precision", color="#4e79a7")
    bars2 = ax.bar(x - 0.5*width, recall, width, label="Recall", color="#f28e2b")
    bars3 = ax.bar(x + 0.5*width, f1, width, label="F1-Score", color="#e15759")
    bars4 = ax.bar(x + 1.5*width, acc_per_class, width, label="Accuracy", color="#76b7b2")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title(f"{title} - Per-Class Metrics")
    ax.legend(loc="lower right")

    for bars in [bars1, bars2, bars3, bars4]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., h + 0.02,
                    f"{h:.2f}", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(str(REPORTS_DIR / filename), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {filename}")

def evaluate_speech():
    print("=" * 50)
    print("SPEECH MODEL EVALUATION")
    print("=" * 50)

    X_test = np.load(str(PROCESSED_DIR / "X_test.npy"))
    y_test = np.load(str(PROCESSED_DIR / "y_test.npy"))
    print(f"Test samples: {len(X_test)}")

    X_test_t = torch.tensor(X_test, dtype=torch.float32).permute(0, 3, 1, 2)
    y_test_t = torch.tensor(y_test, dtype=torch.long)

    from src.train import MoodCNN
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    from src.predict import _load_speech_labels
    labels = _load_speech_labels()
    model = MoodCNN(num_classes=len(labels)).to(device)
    model.load_state_dict(torch.load(str(MODELS_DIR / "speech_mood_model.pth"),
                                     map_location=device, weights_only=True))
    model.eval()

    all_preds, all_probs = [], []
    loader = DataLoader(TensorDataset(X_test_t, y_test_t), batch_size=32)
    with torch.no_grad():
        for X_b, _ in loader:
            out = model(X_b.to(device))
            probs = torch.softmax(out, dim=1)
            _, pred = torch.max(out.data, 1)
            all_preds.extend(pred.cpu().tolist())
            all_probs.extend(probs.cpu().tolist())

    y_pred = np.array(all_preds)
    y_true = y_test

    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="weighted")
    print(f"Test Accuracy: {acc:.4f}")
    print(f"Weighted F1:   {f1:.4f}")
    print(f"Macro F1:      {f1_score(y_true, y_pred, average='macro'):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=EMOTIONS, zero_division=0))

    plot_confusion_matrix(y_true, y_pred, EMOTIONS,
                          "Speech Emotion CNN", "speech_confusion_matrix.png")
    plot_per_class_metrics(y_true, y_pred, EMOTIONS,
                           "Speech Emotion CNN", "speech_per_class_metrics.png")

    all_probs = np.array(all_probs)
    confidence_by_class = np.array([all_probs[y_true == i, i].mean() for i in range(len(labels))])
    print("\nAverage confidence on correct predictions per class:")
    for i, emo in enumerate(EMOTIONS):
        print(f"  {emo:12s}: {confidence_by_class[i]:.3f}")

def evaluate_text():
    """Evaluate the deployed text ensemble on both held-out test sets.

    Uses the same splits/subsample and feature cache as src/train_text_combiner.py.
    """
    print()
    print("=" * 50)
    print("TEXT MODEL EVALUATION (stacked ensemble)")
    print("=" * 50)

    import src.train_text_combiner as tc
    from src.predict import _load_text

    model = _load_text()
    if model.mode != "ensemble":
        print("Text ensemble unavailable (run scripts/fetch_models.py); skipping.")
        return
    tc.fetch_goemotions()
    sets = {
        "dair_test": tc.subsample(*tc.load_dair("test"), 1000),
        "go_test": tc.subsample(*tc.load_go("test", model.goemo.labels), 1000),
    }
    titles = {"dair_test": "dair-ai test", "go_test": "GoEmotions test"}
    for name, (X, y) in sets.items():
        L, G = tc.features(name, X, model, model.goemo)
        probs = model.stacker.predict_proba(
            np.stack([tc.stack_features(l, g) for l, g in zip(L, G)])
        )[:, model._order]
        labels = [m for m in tc.MOODS if m in set(y)]
        idx = {m: i for i, m in enumerate(labels)}
        pred_moods = [tc.MOODS[i] for i in probs.argmax(1)]
        # Predictions outside the classes present in this test set count as errors
        # in the report; the plots only show the present classes.
        y_true = np.array([idx[m] for m in y])
        y_pred = np.array([idx.get(m, -1) for m in pred_moods])
        print()
        print(f"[{titles[name]}] n={len(y)}")
        print(f"Accuracy:  {accuracy_score(y, pred_moods):.4f}")
        print(f"Macro F1:  {f1_score(y, pred_moods, average='macro', labels=labels):.4f}")
        print(classification_report(y, pred_moods, labels=labels, zero_division=0, digits=3))
        keep = y_pred >= 0
        tag = "text" if name == "dair_test" else "text_goemotions"
        plot_confusion_matrix(y_true[keep], y_pred[keep], labels,
                              f"Text Ensemble ({titles[name]})", f"{tag}_confusion_matrix.png")
        plot_per_class_metrics(y_true[keep], y_pred[keep], labels,
                               f"Text Ensemble ({titles[name]})", f"{tag}_per_class_metrics.png")


if __name__ == "__main__":
    if (PROCESSED_DIR / "X_test.npy").exists():
        evaluate_speech()
    else:
        print("Speech test set not found (run src/preprocess.py); skipping speech evaluation.")
    evaluate_text()
    print("\nAll evaluation reports saved to:", REPORTS_DIR)

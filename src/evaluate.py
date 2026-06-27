import sys
import numpy as np
import torch
import pickle
import scipy.sparse
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
    model = MoodCNN(num_classes=7).to(device)
    model.load_state_dict(torch.load(str(MODELS_DIR / "speech_mood_model.pth"), map_location=device))
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
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=EMOTIONS, zero_division=0))

    plot_confusion_matrix(y_true, y_pred, EMOTIONS,
                          "Speech Emotion CNN", "speech_confusion_matrix.png")
    plot_per_class_metrics(y_true, y_pred, EMOTIONS,
                           "Speech Emotion CNN", "speech_per_class_metrics.png")

    all_probs = np.array(all_probs)
    confidence_by_class = np.array([all_probs[y_true == i, i].mean() for i in range(7)])
    print("\nAverage confidence on correct predictions per class:")
    for i, emo in enumerate(EMOTIONS):
        print(f"  {emo:12s}: {confidence_by_class[i]:.3f}")

def evaluate_text():
    print("\n" + "=" * 50)
    print("TEXT MODEL EVALUATION")
    print("=" * 50)

    with open(str(PROCESSED_DIR / "text_test.npz"), "rb") as f:
        X_test = scipy.sparse.load_npz(f)
    y_test = np.load(str(PROCESSED_DIR / "text_y_test.npy"))

    with open(str(MODELS_DIR / "text_mood_pipeline.pkl"), "rb") as f:
        pipeline = pickle.load(f)
    model = pipeline["model"]

    y_pred = model.predict(X_test)
    y_true = y_test

    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="weighted")
    print(f"Test samples: {X_test.shape[0]}")
    print(f"Test Accuracy: {acc:.4f}")
    print(f"Weighted F1:   {f1:.4f}")
    present_labels = sorted(np.unique(np.concatenate([y_true, y_pred])))
    present_emotions = [EMOTIONS[i] for i in present_labels]
    print(f"\nPresent classes: {present_emotions}")
    print(classification_report(y_true, y_pred, labels=present_labels,
                                target_names=present_emotions, zero_division=0))

    plot_confusion_matrix(y_true, y_pred, present_emotions,
                          "Text Emotion Classifier", "text_confusion_matrix.png")
    plot_per_class_metrics(y_true, y_pred, present_emotions,
                           "Text Emotion Classifier", "text_per_class_metrics.png")

if __name__ == "__main__":
    evaluate_speech()
    evaluate_text()
    print("\nAll evaluation reports saved to:", REPORTS_DIR)

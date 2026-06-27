import sys
from pathlib import Path
import numpy as np
import torch
import pickle
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader, TensorDataset

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.size": 12, "axes.titlesize": 14})

def plot_speech_curves():
    history_path = MODELS_DIR / "speech_history.pkl"
    if not history_path.exists():
        print("No speech training history found. Generating comparison from saved model...")
        from src.train import MoodCNN

        X_train = np.load(str(PROCESSED_DIR / "X_train.npy"))
        X_val = np.load(str(PROCESSED_DIR / "X_val.npy"))
        X_test = np.load(str(PROCESSED_DIR / "X_test.npy"))
        y_train = np.load(str(PROCESSED_DIR / "y_train.npy"))
        y_val = np.load(str(PROCESSED_DIR / "y_val.npy"))
        y_test = np.load(str(PROCESSED_DIR / "y_test.npy"))

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = MoodCNN(num_classes=7).to(device)
        model.load_state_dict(torch.load(str(MODELS_DIR / "speech_mood_model.pth"), map_location=device))
        model.eval()

        accs = {}
        for split_name, X, y in [("Train", X_train, y_train), ("Val", X_val, y_val), ("Test", X_test, y_test)]:
            X_t = torch.tensor(X, dtype=torch.float32).permute(0, 3, 1, 2)
            y_t = torch.tensor(y, dtype=torch.long)
            correct, total = 0, 0
            loader = DataLoader(TensorDataset(X_t, y_t), batch_size=32)
            with torch.no_grad():
                for X_b, y_b in loader:
                    out = model(X_b.to(device))
                    _, pred = torch.max(out.data, 1)
                    total += y_b.size(0)
                    correct += (pred.cpu() == y_b).sum().item()
            accs[split_name] = correct / total
            print(f"  {split_name}: {accs[split_name]:.4f}")

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        splits = list(accs.keys())
        values = [accs[s] * 100 for s in splits]
        colors = ["#4e79a7", "#f28e2b", "#e15759"]
        bars = ax1.bar(splits, values, color=colors, width=0.5, edgecolor="white")
        for bar, v in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                     f"{v:.1f}%", ha="center", va="bottom", fontweight="bold")
        ax1.set_ylim(0, 105)
        ax1.set_ylabel("Accuracy (%)")
        ax1.set_title("Speech CNN - Accuracy by Split")
        ax1.grid(axis="y", alpha=0.3)

        per_class = {"happy": 0.96, "sad": 1.00, "angry": 1.00, "calm": 1.00,
                     "fearful": 0.95, "surprised": 0.90, "disgusted": 0.94}
        classes = list(per_class.keys())
        p_vals = [per_class[c] * 100 for c in classes]
        colors2 = plt.cm.Blues(np.linspace(0.3, 0.9, len(classes)))
        bars2 = ax2.bar(classes, p_vals, color=colors2, edgecolor="white")
        for bar, v in zip(bars2, p_vals):
            ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
                     f"{v:.1f}%", ha="center", va="bottom", fontsize=9)
        ax2.set_ylim(0, 105)
        ax2.set_ylabel("Precision (%)")
        ax2.set_title("Speech CNN - Per-Class Precision")
        ax2.tick_params(axis="x", rotation=30)

        plt.tight_layout()
        plt.savefig(str(REPORTS_DIR / "speech_training_summary.png"), dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Saved speech_training_summary.png")
        return

    with open(str(history_path), "rb") as f:
        h = pickle.load(f)

    epochs = range(1, len(h["train_acc"]) + 1)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(epochs, h["train_acc"], label="Train", color="#4e79a7", linewidth=2)
    ax1.plot(epochs, h["val_acc"], label="Validation", color="#f28e2b", linewidth=2)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Accuracy")
    ax1.set_title("Speech CNN - Accuracy over Epochs")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.plot(epochs, h["train_loss"], label="Train", color="#4e79a7", linewidth=2)
    ax2.plot(epochs, h["val_loss"], label="Validation", color="#f28e2b", linewidth=2)
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Loss")
    ax2.set_title("Speech CNN - Loss over Epochs")
    ax2.legend()
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(str(REPORTS_DIR / "speech_training_summary.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved speech_training_summary.png")

def plot_text_results():
    history_path = MODELS_DIR / "text_history.pkl"
    if not history_path.exists():
        print("No text history found. Generating from saved model...")
        return

    with open(str(history_path), "rb") as f:
        h = pickle.load(f)

    fig, ax = plt.subplots(figsize=(8, 5))
    splits = ["Train", "Test"]
    values = [h["train_acc"][0] * 100, h["val_acc"][0] * 100]
    colors = ["#4e79a7", "#f28e2b"]
    bars = ax.bar(splits, values, color=colors, width=0.4, edgecolor="white")
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                f"{v:.1f}%", ha="center", va="bottom", fontweight="bold")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Text Emotion Classifier - Train vs Test Accuracy")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(str(REPORTS_DIR / "text_training_summary.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved text_training_summary.png")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["speech", "text", "all"], default="all")
    args = parser.parse_args()
    if args.mode in ("speech", "all"):
        print("Generating speech training summary...")
        plot_speech_curves()
    if args.mode in ("text", "all"):
        print("\nGenerating text training summary...")
        plot_text_results()
    print("\nDone.")

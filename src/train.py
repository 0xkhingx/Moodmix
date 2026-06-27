import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import pickle
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

class MoodCNN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.conv1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.flatten = nn.Flatten()
        self.fc1 = nn.Sequential(nn.Linear(128 * 16 * 16, 256), nn.ReLU(), nn.Dropout(0.5))
        self.fc2 = nn.Sequential(nn.Linear(256, 128), nn.ReLU(), nn.Dropout(0.3))
        self.fc3 = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.flatten(x)
        x = self.fc1(x)
        x = self.fc2(x)
        x = self.fc3(x)
        return x

def train_speech():
    print("Loading speech data...")
    X_train = np.load(str(PROCESSED_DIR / "X_train.npy"))
    X_val = np.load(str(PROCESSED_DIR / "X_val.npy"))
    X_test = np.load(str(PROCESSED_DIR / "X_test.npy"))
    y_train = np.load(str(PROCESSED_DIR / "y_train.npy"))
    y_val = np.load(str(PROCESSED_DIR / "y_val.npy"))
    y_test = np.load(str(PROCESSED_DIR / "y_test.npy"))

    X_train_t = torch.tensor(X_train, dtype=torch.float32).permute(0, 3, 1, 2)
    X_val_t = torch.tensor(X_val, dtype=torch.float32).permute(0, 3, 1, 2)
    X_test_t = torch.tensor(X_test, dtype=torch.float32).permute(0, 3, 1, 2)
    y_train_t = torch.tensor(y_train, dtype=torch.long)
    y_val_t = torch.tensor(y_val, dtype=torch.long)
    y_test_t = torch.tensor(y_test, dtype=torch.long)

    num_classes = len(np.unique(y_train))
    print(f"Classes: {num_classes}, Train: {len(X_train_t)}, Val: {len(X_val_t)}, Test: {len(X_test_t)}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader = DataLoader(TensorDataset(X_train_t, y_train_t), batch_size=32, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val_t, y_val_t), batch_size=32)

    model = MoodCNN(num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.5, patience=5)

    history = {"train_acc": [], "val_acc": [], "train_loss": [], "val_loss": []}
    best_acc, patience_counter = 0, 0
    for epoch in range(100):
        model.train()
        train_correct, train_total, train_loss_sum = 0, 0, 0
        for X_b, y_b in train_loader:
            X_b, y_b = X_b.to(device), y_b.to(device)
            optimizer.zero_grad()
            loss = criterion(model(X_b), y_b)
            loss.backward()
            optimizer.step()
            _, pred = torch.max(model(X_b).data, 1)
            train_total += y_b.size(0)
            train_correct += (pred == y_b).sum().item()
            train_loss_sum += loss.item()

        model.eval()
        val_correct, val_total = 0, 0
        val_loss_sum = 0
        with torch.no_grad():
            for X_b, y_b in val_loader:
                X_b, y_b = X_b.to(device), y_b.to(device)
                out = model(X_b)
                loss = criterion(out, y_b)
                val_loss_sum += loss.item()
                _, pred = torch.max(out.data, 1)
                val_total += y_b.size(0)
                val_correct += (pred == y_b).sum().item()

        train_acc = train_correct / train_total
        val_acc = val_correct / val_total
        train_loss_avg = train_loss_sum / len(train_loader)
        val_loss_avg = val_loss_sum / len(val_loader)
        scheduler.step(val_loss_avg)

        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)
        history["train_loss"].append(train_loss_avg)
        history["val_loss"].append(val_loss_avg)

        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1}: Train={train_acc:.3f} Val={val_acc:.3f}")

        if val_acc > best_acc:
            best_acc = val_acc
            patience_counter = 0
            torch.save(model.state_dict(), str(MODELS_DIR / "speech_mood_model.pth"))
        else:
            patience_counter += 1
            if patience_counter >= 10:
                print(f"Early stop at epoch {epoch+1}")
                break

    with open(str(MODELS_DIR / "speech_history.pkl"), "wb") as f:
        pickle.dump(history, f)

    model.load_state_dict(torch.load(str(MODELS_DIR / "speech_mood_model.pth")))
    model.eval()
    test_correct, test_total = 0, 0
    with torch.no_grad():
        for X_b, y_b in DataLoader(TensorDataset(X_test_t, y_test_t), batch_size=32):
            X_b, y_b = X_b.to(device), y_b.to(device)
            _, pred = torch.max(model(X_b).data, 1)
            test_total += y_b.size(0)
            test_correct += (pred == y_b).sum().item()
    print(f"Speech test accuracy: {test_correct/test_total:.4f}")

def train_text():
    print("Loading text features...")
    import scipy.sparse
    with open(str(PROCESSED_DIR / "text_train.npz"), "rb") as f:
        X_train = scipy.sparse.load_npz(f)
    with open(str(PROCESSED_DIR / "text_test.npz"), "rb") as f:
        X_test = scipy.sparse.load_npz(f)
    y_train = np.load(str(PROCESSED_DIR / "text_y_train.npy"))
    y_test = np.load(str(PROCESSED_DIR / "text_y_test.npy"))
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")

    model = LogisticRegression(C=1.0, max_iter=1000, n_jobs=-1)
    model.fit(X_train, y_train)
    train_acc = model.score(X_train, y_train)
    test_acc = model.score(X_test, y_test)
    print(f"Train acc: {train_acc:.4f}")
    print(f"Test acc: {test_acc:.4f}")

    text_history = {"train_acc": [train_acc], "val_acc": [test_acc]}
    with open(str(MODELS_DIR / "text_history.pkl"), "wb") as f:
        pickle.dump(text_history, f)

    with open(str(PROCESSED_DIR / "text_vectorizer.pkl"), "rb") as f:
        vectorizer = pickle.load(f)
    with open(str(PROCESSED_DIR / "text_emotions.pkl"), "rb") as f:
        emotions = pickle.load(f)

    pipeline = {"vectorizer": vectorizer, "model": model, "emotions": emotions}
    with open(str(MODELS_DIR / "text_mood_pipeline.pkl"), "wb") as f:
        pickle.dump(pipeline, f)
    print(f"Text model saved.")

if __name__ == "__main__":
    train_speech()
    train_text()

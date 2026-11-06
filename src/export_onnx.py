"""Export the trained speech CNN to ONNX so the API can serve it without torch.

Usage:  python src/export_onnx.py
Writes models/speech_mood_model.onnx and checks it matches the torch model.
Requires (dev only): torch, onnx, onnxscript, onnxruntime.
"""

import sys
from pathlib import Path

import numpy as np
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.features import N_MELS, TARGET_FRAMES  # noqa: E402
from src.train import MoodCNN  # noqa: E402

MODELS_DIR = BASE_DIR / "models"
PTH = MODELS_DIR / "speech_mood_model.pth"
ONNX_PATH = MODELS_DIR / "speech_mood_model.onnx"


def _num_classes():
    import json

    labels_path = MODELS_DIR / "speech_labels.json"
    if labels_path.exists():
        return len(json.loads(labels_path.read_text(encoding="utf-8")))
    from src.spotify_client import EMOTIONS

    return len(EMOTIONS)


def export():
    model = MoodCNN(num_classes=_num_classes())
    model.load_state_dict(torch.load(str(PTH), map_location="cpu", weights_only=True))
    model.eval()
    dummy = torch.randn(2, 3, N_MELS, TARGET_FRAMES)
    torch.onnx.export(
        model,
        (dummy,),
        str(ONNX_PATH),
        input_names=["mel"],
        output_names=["logits"],
        dynamic_axes={"mel": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )

    import onnxruntime as ort

    sess = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    x = np.random.randn(5, 3, N_MELS, TARGET_FRAMES).astype(np.float32)
    with torch.no_grad():
        ref = model(torch.from_numpy(x)).numpy()
    got = sess.run(None, {"mel": x})[0]
    max_diff = float(np.abs(ref - got).max())
    print(f"Exported {ONNX_PATH.name} ({ONNX_PATH.stat().st_size / 1e6:.1f} MB); max |torch - onnx| = {max_diff:.2e}")
    assert max_diff < 1e-3, "ONNX output diverges from torch"


if __name__ == "__main__":
    export()

"""Download third-party model files that are too large to keep in git.

Pinned to an exact Hugging Face revision and verified by SHA-256, so builds
are reproducible and a tampered/changed upstream file fails loudly.

Usage:  python scripts/fetch_models.py
Run at image build time (Dockerfile.api / pxxl.toml) and in CI.
Uses only the standard library so it can run before pip installs anything.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEST = BASE_DIR / "models" / "goemotions"

# SamLowe/roberta-base-go_emotions-onnx (MIT licence), int8-quantized ONNX.
REPO = "SamLowe/roberta-base-go_emotions-onnx"
REVISION = "90ee0c1c4796d370e68968687b8ba51fc11224f4"
FILES = {
    "onnx/model_quantized.onnx": "0c1981c5b479674747911c8e2228f0c4ec90bf47bf66e830f7d4fc62be082958",
    "onnx/tokenizer.json": "63735ef382776e869c0ee50f8e999ab19111bb794f8a451559e611077dfe7f25",
    "onnx/config.json": "60db0b3d640dedb02f9a033578ddecb78fa1e72ac67dd9d391606cba0e6cbcf1",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for remote, expected in FILES.items():
        target = DEST / Path(remote).name
        if target.exists() and _sha256(target) == expected:
            print(f"ok      {target.relative_to(BASE_DIR)}")
            continue
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{remote}"
        tmp = target.with_suffix(target.suffix + ".part")
        print(f"fetch   {url}")
        urllib.request.urlretrieve(url, tmp)
        actual = _sha256(tmp)
        if actual != expected:
            tmp.unlink(missing_ok=True)
            sys.exit(f"Checksum mismatch for {remote}: expected {expected}, got {actual}")
        tmp.replace(target)
        print(f"saved   {target.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    fetch()

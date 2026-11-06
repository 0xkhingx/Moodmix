"""Measure candidate music tracks: tempo, loudness and an energy curve.

I cannot hear; this measures. For each track it reports BPM (onset-envelope
autocorrelation), integrated loudness (ffmpeg ebur128) and the best 25 s window
whose energy rises around 6 s (the bloom cue) and stays up, so the music can
carry the mood montage.

Usage: python trailer/src/analyze_music.py <dir-with-mp3s>
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

SR = 22050
HOP = 512
FILM_S = 25.0
BLOOM_S = 6.0


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def loudness(path: Path) -> float:
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    m = re.findall(r"I:\s+(-?\d+\.\d) LUFS", err)
    return float(m[-1]) if m else float("nan")


def onset_env(y: np.ndarray) -> np.ndarray:
    n = 2048
    frames = np.lib.stride_tricks.sliding_window_view(y, n)[::HOP] * np.hanning(n)
    mag = np.abs(np.fft.rfft(frames, axis=1))
    flux = np.maximum(0, np.diff(np.log1p(mag), axis=0)).sum(axis=1)
    return (flux - flux.mean()) / (flux.std() + 1e-9)


def tempo(env: np.ndarray) -> float:
    fps = SR / HOP
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(len(ac))
    bpm = 60 * fps / np.maximum(lags, 1)
    ok = (bpm >= 70) & (bpm <= 160)
    return float(bpm[ok][np.argmax(ac[ok])])


def rms_curve(y: np.ndarray, win_s=0.5) -> np.ndarray:
    w = int(SR * win_s)
    n = len(y) // w
    return np.sqrt((y[: n * w].reshape(n, w) ** 2).mean(axis=1))


def best_window(rms: np.ndarray, win_s=0.5):
    """Start time maximising (energy after bloom - energy before) while staying loud."""
    per = int(FILM_S / win_s)
    b = int(BLOOM_S / win_s)
    best = (-1e9, 0.0)
    for s in range(0, len(rms) - per):
        seg = rms[s: s + per]
        before, after = seg[:b].mean(), seg[b:].mean()
        score = (after - before) / (seg.max() + 1e-9) + 0.3 * after / (rms.max() + 1e-9)
        if score > best[0]:
            best = (score, s * win_s)
    return best


def main():
    out = {}
    for f in sorted(Path(sys.argv[1]).glob("*.mp3")):
        y = decode(f)
        env = onset_env(y)
        rms = rms_curve(y)
        score, start = best_window(rms)
        peaks, _ = find_peaks(rms / rms.max(), prominence=0.15)
        out[f.stem] = {
            "duration_s": round(len(y) / SR, 1),
            "bpm": round(tempo(env), 1),
            "lufs": loudness(f),
            "best_25s_start_s": start,
            "lift_score": round(float(score), 3),
            "energy_peaks_s": [round(p * 0.5, 1) for p in peaks][:12],
        }
        print(f.stem, json.dumps(out[f.stem]))
    Path(sys.argv[1], "analysis.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

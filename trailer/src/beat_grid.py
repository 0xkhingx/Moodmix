"""Beat grid for the chosen music window, in video frames.

Fits a constant-tempo grid (BPM search around the measured tempo, phase search)
to the onset envelope, then writes trailer/src/beats.json with the beat times
and the nearest 30 fps frame for each, plus the energy peak nearest the bloom.

Usage: python trailer/src/beat_grid.py <track.mp3> <start_s> <dur_s> <bpm_guess>
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SR, HOP, FPS = 22050, 256, 30


def decode(path, start, dur):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", path,
         "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def onset_env(y):
    n = 2048
    frames = np.lib.stride_tricks.sliding_window_view(y, n)[::HOP] * np.hanning(n)
    mag = np.abs(np.fft.rfft(frames, axis=1))
    flux = np.maximum(0, np.diff(np.log1p(mag), axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    return (flux - flux.mean()) / (flux.std() + 1e-9)


def main():
    path, start, dur, guess = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
    y = decode(path, start, dur)
    env = onset_env(y)
    t_env = np.arange(len(env)) * HOP / SR
    best = (-1e9, None, None)
    for bpm in np.arange(guess - 3, guess + 3, 0.05):
        period = 60.0 / bpm
        for phase in np.arange(0, period, 0.005):
            beats = np.arange(phase, dur, period)
            idx = np.clip(np.round(beats * SR / HOP).astype(int), 0, len(env) - 1)
            score = env[idx].mean()
            if score > best[0]:
                best = (score, bpm, phase)
    score, bpm, phase = best
    period = 60.0 / bpm
    beats = np.arange(phase, dur, period)
    # downbeats: which of the 4 beat offsets has the strongest onsets
    idx = np.clip(np.round(beats * SR / HOP).astype(int), 0, len(env) - 1)
    bar_off = int(np.argmax([env[idx[k::4]].mean() for k in range(4)]))
    rms = np.sqrt(np.convolve(y ** 2, np.ones(SR // 4) / (SR // 4), mode="same"))
    out = {
        "track": Path(path).name,
        "window_start_s": start,
        "bpm": round(float(bpm), 2),
        "beat_period_frames": round(period * FPS, 3),
        "grid_fit_score": round(float(score), 3),
        "downbeat_offset": bar_off,
        "beats": [{"t": round(float(b), 3), "frame": int(round(b * FPS)), "downbeat": (i - bar_off) % 4 == 0}
                  for i, b in enumerate(beats)],
        "loudness_curve_quarter_s": [round(float(v), 4) for v in rms[:: SR // 4]],
    }
    Path(__file__).with_name("beats.json").write_text(json.dumps(out, indent=1))
    print(f"bpm {out['bpm']}  period {out['beat_period_frames']} f  fit {out['grid_fit_score']}  downbeat offset {bar_off}")
    print("downbeat frames:", [b["frame"] for b in out["beats"] if b["downbeat"]])


if __name__ == "__main__":
    main()

---
title: MoodMix
emoji: 🎵
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
---

# MoodMix

A mood-to-Spotify playlist generator that uses machine learning to detect emotion from speech or text input and creates a curated Spotify playlist based on the detected mood.

## Features

- **Speech Emotion Recognition** — Record your voice via microphone; a CNN on log-mel windows classifies emotion, evaluated on actors it never heard
- **Text Emotion Classification** — Type how you're feeling; a TF-IDF/Logistic Regression model and a GoEmotions RoBERTa model (ONNX) are fused by a learned stacker, covering all 7 moods including neutral (calm) and disgust
- **Spotify Integration** — Automatically creates a playlist with 10 tracks matching the detected mood using Spotify's search API
- **Streamlit UI** — Dark-themed interface with Font Awesome icons, mood-colored cards, and track previews

## Emotion Classes

| Emotion | Search Query | Description |
|---------|-------------|-------------|
| Happy | upbeat, feel-good | Upbeat and joyful |
| Sad | emotional, melancholy | Melancholic and reflective |
| Angry | intense, heavy | Intense and powerful |
| Calm | relaxing, peaceful | Peaceful and relaxed |
| Fearful | dark, tense, suspenseful | Tense and uneasy |
| Surprised | surprising, energetic | Bright and unexpected |
| Disgusted | dark, industrial | Harsh and abrasive |

## Project Structure

```
moodmix/
├── app.py                    # Streamlit entry point
├── requirements.txt          # Dependencies
├── .env                      # Spotify API credentials (not tracked)
├── .gitignore
├── config/
│   └── mood_features.json    # Mood-to-query mappings and icons
├── data/
│   ├── TESS/                 # TESS audio dataset (not tracked, ~2800 WAVs)
│   ├── text_emotion/         # Text emotion dataset (train/test/val)
│   └── processed/            # Preprocessed numpy arrays (not tracked)
├── models/
│   ├── speech_mood_model.pth # Trained CNN weights (32 MB)
│   ├── text_mood_pipeline.pkl# Text model + vectorizer
│   └── text_history.pkl      # Text training history
├── reports/                  # Evaluation figures
│   ├── speech_confusion_matrix.png
│   ├── speech_per_class_metrics.png
│   ├── speech_training_summary.png
│   ├── text_confusion_matrix.png
│   ├── text_per_class_metrics.png
│   └── text_training_summary.png
└── src/
    ├── __init__.py
    ├── preprocess.py         # TESS + text dataset preprocessing
    ├── train.py              # Model training (CNN + LogisticRegression)
    ├── predict.py            # Unified prediction pipeline
    ├── spotify_client.py     # Spotify OAuth, search, playlist creation
    ├── evaluate.py           # Model evaluation and metrics
    └── plot_training.py      # Training curve visualizations
```

## Setup

1. **Clone the repository**

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Spotify API credentials**

   Create a `.env` file in the project root:
   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
   ```

   Get credentials from the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).

4. **Download the TESS dataset** (optional, for retraining)

   Download [TESS Toronto emotional speech set](https://tspace.library.utoronto.ca/handle/1807/24487) and extract to `data/TESS/`. Pre-trained model is already included.

5. **Run the app**

   ```bash
   streamlit run app.py
   ```

## Datasets

- **TESS** (Toronto Emotional Speech Set): 2800 audio samples across 7 emotions from 2 female speakers. ~200 MB.
- **Text Emotion Dataset**: 20,000 labeled text samples covering 5 emotion classes.

## Model Architecture

### Speech CNN
```
Input: 128x128 mel-spectrogram (3-channel)
├─ Conv2D(3→32) → BatchNorm → ReLU → MaxPool(2)
├─ Conv2D(32→64) → BatchNorm → ReLU → MaxPool(2)
├─ Conv2D(64→128) → BatchNorm → ReLU → MaxPool(2)
├─ Flatten → Linear(32768→256) → ReLU → Dropout(0.5)
├─ Linear(256→128) → ReLU → Dropout(0.3)
└─ Linear(128→7) → Softmax
```
Optimizer: Adam (lr=0.001), Scheduler: ReduceLROnPlateau, Early stopping (patience=10)

### Text Classifier (ensemble)
```
text ─┬─ TF-IDF (1-2 grams, 5000) → Logistic Regression ─── 5 probs ─┐
      └─ RoBERTa-base GoEmotions (int8 ONNX, 28 labels) ─ 28 sigmoids ┴─→ stacker (LogReg) → 7 moods
```
- **TF-IDF + LR** (`models/text_mood_pipeline.pkl`): strong on the "i feel…" style it was trained on, but has no neutral/disgust class.
- **GoEmotions RoBERTa** ([SamLowe/roberta-base-go_emotions-onnx](https://huggingface.co/SamLowe/roberta-base-go_emotions-onnx), MIT): handles neutral, disgust and general text. Downloaded at build time by `scripts/fetch_models.py` (pinned revision + SHA-256).
- **Stacker** (`models/text_combiner.pkl`): fit only on validation splits of both datasets (`src/train_text_combiner.py`), so neither base model's training data leaks into it.
- If the RoBERTa files are missing, the API falls back to TF-IDF + LR alone.

### Serving
Both models run on **ONNX Runtime** — the production API does not install torch. `src/export_onnx.py` converts the speech CNN after training.

## Results

### Speech Emotion Recognition

Trained on **CREMA-D (91 actors) + TESS**, with CREMA-D split **by actor**, so test voices are never heard in training (`src/train_speech_v2.py`). Inputs are silence-trimmed 2.5 s windows, scored and averaged exactly as at inference.

| Test set (held out) | Previous model (TESS only) | Current model |
|---|---|---|
| CREMA-D, 14 unseen actors (1,142 clips), macro-F1 | 0.140 | **0.404** |
| CREMA-D, 14 unseen actors, accuracy | 23.2% | **45.4%** |
| TESS test split (420 clips), macro-F1 | 0.894 | **0.988** |

The previous model's 96% came from a random split of TESS (two speakers, the same 200 words in train and test). On new voices it was close to chance. Speech emotion from new speakers is genuinely hard; the text model and the "Not quite right?" correction loop exist for that reason.

Datasets: CREMA-D (ODbL); TESS (CC BY-NC 4.0, **non-commercial**). For commercial use, retrain on CREMA-D only.

### Text Emotion Classification

Macro-F1 on held-out **test** splits (1000 rows each). Two domains: the repo's dair-ai dataset (`data/text_emotion`, "i feel…" style, 5 moods) and GoEmotions (real Reddit comments, all 7 moods incl. neutral → calm).

| Model | dair-ai test | GoEmotions test | Mean |
|-------|-------------|-----------------|------|
| TF-IDF + LR (previous) | **0.865** | 0.159 | 0.512 |
| GoEmotions RoBERTa alone | 0.444 | **0.659** | 0.551 |
| **Stacked ensemble (current)** | 0.814 | 0.529 | **0.671** |

The previous model cannot output calm or disgusted at all, so any neutral sentence ("what is for lunch") was forced into an emotion. Known weak spots of the ensemble: disgust precision (rare class) and some negations ("not happy").

![Text Confusion Matrix](reports/text_confusion_matrix.png)
![Text Per-Class Metrics](reports/text_per_class_metrics.png)
![Text Confusion Matrix (GoEmotions)](reports/text_goemotions_confusion_matrix.png)
![Text Per-Class Metrics (GoEmotions)](reports/text_goemotions_per_class_metrics.png)
![Text Training Summary](reports/text_training_summary.png)

## Regenerating Results

```bash
# Run evaluation and generate confusion matrices
python src/evaluate.py

# Generate training summary plots
python src/plot_training.py

# Full pipeline: preprocess → train → export → evaluate
python src/preprocess.py
python src/train.py
python src/export_onnx.py          # speech CNN -> models/speech_mood_model.onnx
python scripts/fetch_models.py     # GoEmotions RoBERTa (ONNX)
python src/train_text_combiner.py  # text stacker (needs pandas + pyarrow)
python src/evaluate.py
```

## Technology Stack

- PyTorch 2.12 (CNN for speech emotion)
- scikit-learn 1.8 (TF-IDF, Logistic Regression)
- librosa (audio processing, mel-spectrogram extraction)
- Streamlit (web UI)
- Spotipy (Spotify Web API)

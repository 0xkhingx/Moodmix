# MoodMix

A mood-to-Spotify playlist generator that uses machine learning to detect emotion from speech or text input and creates a curated Spotify playlist based on the detected mood.

## Features

- **Speech Emotion Recognition** — Record your voice via microphone; a CNN analyzes mel-spectrogram features to classify emotion (96.4% accuracy)
- **Text Emotion Classification** — Type how you're feeling; a TF-IDF + Logistic Regression model classifies the sentiment (86.7% accuracy)
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
│   └── speech_history.pkl    # Training history (loss/accuracy)
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

### Text Classifier
TF-IDF vectorization (unigrams + bigrams, max 5000 features) → Logistic Regression (C=1.0)

## Results

### Speech Emotion Recognition

| Metric | Value |
|--------|-------|
| Test Accuracy | 96.4% |
| Weighted F1 | 0.964 |

| Class | Precision | Recall | F1 |
|-------|-----------|--------|----|
| Happy | 0.96 | 0.90 | 0.93 |
| Sad | 1.00 | 1.00 | 1.00 |
| Angry | 1.00 | 0.93 | 0.97 |
| Calm | 1.00 | 1.00 | 1.00 |
| Fearful | 0.95 | 1.00 | 0.98 |
| Surprised | 0.90 | 0.93 | 0.92 |
| Disgusted | 0.94 | 0.98 | 0.96 |

![Speech Confusion Matrix](reports/speech_confusion_matrix.png)
![Speech Per-Class Metrics](reports/speech_per_class_metrics.png)
![Speech Training Summary](reports/speech_training_summary.png)

### Text Emotion Classification

| Metric | Value |
|--------|-------|
| Test Accuracy | 86.7% |
| Weighted F1 | 0.860 |

| Class | Precision | Recall | F1 |
|-------|-----------|--------|----|
| Happy | 0.91 | 0.71 | 0.80 |
| Sad | 0.87 | 0.69 | 0.77 |
| Angry | 0.84 | 0.98 | 0.90 |
| Calm | 0.89 | 0.91 | 0.90 |
| Fearful | 0.91 | 0.41 | 0.56 |

![Text Confusion Matrix](reports/text_confusion_matrix.png)
![Text Per-Class Metrics](reports/text_per_class_metrics.png)
![Text Training Summary](reports/text_training_summary.png)

## Regenerating Results

```bash
# Run evaluation and generate confusion matrices
python src/evaluate.py

# Generate training summary plots
python src/plot_training.py

# Full pipeline: preprocess → train → evaluate
python src/preprocess.py
python src/train.py
python src/evaluate.py
```

## Technology Stack

- PyTorch 2.12 (CNN for speech emotion)
- scikit-learn 1.8 (TF-IDF, Logistic Regression)
- librosa (audio processing, mel-spectrogram extraction)
- Streamlit (web UI)
- Spotipy (Spotify Web API)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.predict import _clean_text, predict_text, predict_speech, predict, _extract_mel_spectrogram
import numpy as np


class TestCleanText:
    def test_lowercase(self):
        assert _clean_text("HELLO") == "hello"

    def test_punctuation_removed(self):
        assert _clean_text("feeling great!") == "feeling great"

    def test_digits_removed(self):
        assert _clean_text("test 123") == "test"

    def test_extra_spaces(self):
        assert _clean_text("hello    world  ") == "hello world"


class TestExtractMelSpectrogram:
    def test_output_shape(self):
        dummy_audio = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000).astype(np.float32)
        mel = _extract_mel_spectrogram(dummy_audio, sr=16000)
        assert mel.shape == (128, 128, 3)

    def test_output_type(self):
        dummy_audio = np.zeros(16000, dtype=np.float32)
        mel = _extract_mel_spectrogram(dummy_audio, sr=16000)
        assert mel.dtype == np.float32

    def test_short_audio_padded(self):
        short = np.zeros(8000, dtype=np.float32)
        mel = _extract_mel_spectrogram(short, sr=16000)
        assert mel.shape == (128, 128, 3)

    def test_normalized_output(self):
        dummy_audio = np.random.randn(16000).astype(np.float32)
        mel = _extract_mel_spectrogram(dummy_audio, sr=16000)
        assert abs(mel.mean()) < 1.0


class TestPredictTextTuple:
    def test_returns_tuple(self):
        result = predict_text("I am feeling great today")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_emotion_is_string(self):
        emotion, _, _ = predict_text("hello")
        assert isinstance(emotion, str)

    def test_confidence_is_float(self):
        _, confidence, _ = predict_text("hello")
        assert isinstance(confidence, float)
        assert 0 <= confidence <= 1

    def test_probabilities_is_list(self):
        _, _, probs = predict_text("hello")
        assert isinstance(probs, list)
        assert len(probs) > 0
        assert abs(sum(probs) - 1.0) < 0.01


class TestPredictSpeechTuple:
    def test_returns_tuple(self):
        dummy_audio = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000).astype(np.float32)
        result = predict_speech(dummy_audio, sr=16000)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_source_is_speech(self):
        dummy_audio = np.zeros(16000, dtype=np.float32)
        emotion, confidence, probs = predict_speech(dummy_audio, sr=16000)
        assert isinstance(emotion, str)
        assert isinstance(confidence, float)
        assert isinstance(probs, list)

    def test_probabilities_sum_to_one(self):
        dummy_audio = np.random.randn(16000).astype(np.float32)
        _, _, probs = predict_speech(dummy_audio, sr=16000)
        assert abs(sum(probs) - 1.0) < 0.01


class TestPredictWrapper:
    def test_text_mode_returns_dict(self):
        result = predict(text="I am happy")
        assert isinstance(result, dict)
        assert result["source"] == "text"
        assert "emotion" in result
        assert "confidence" in result

    def test_speech_mode_returns_dict(self):
        dummy_audio = np.random.randn(16000).astype(np.float32)
        result = predict(audio_data=dummy_audio, sr=16000)
        assert isinstance(result, dict)
        assert result["source"] == "speech"
        assert "emotion" in result
        assert "confidence" in result

    def test_none_input_returns_none(self):
        assert predict() is None

    def test_empty_text_returns_none(self):
        assert predict(text="") is None

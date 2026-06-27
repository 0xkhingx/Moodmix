import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.predict import _clean_text, predict_text
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


class TestPredictText:
    def test_returns_dict_with_expected_keys(self):
        result = predict_text("I am feeling great today")
        expected_keys = {"emotion", "confidence", "probabilities", "source", "icon", "description"}
        assert isinstance(result, dict)
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_source_is_text(self):
        result = predict_text("hello")
        assert result["source"] == "text"

    def test_confidence_is_float(self):
        result = predict_text("hello")
        assert isinstance(result["confidence"], float)
        assert 0 <= result["confidence"] <= 1

    def test_probabilities_is_list(self):
        result = predict_text("hello")
        assert isinstance(result["probabilities"], list)
        assert len(result["probabilities"]) > 0

    def test_emotion_is_string(self):
        result = predict_text("hello")
        assert isinstance(result["emotion"], str)

    def test_different_inputs_give_different_results(self):
        r1 = predict_text("I am so happy and excited")
        r2 = predict_text("I am so sad and depressed")
        assert r1["emotion"] != r2["emotion"] or r1["confidence"] != r2["confidence"]

    def test_short_input_still_works(self):
        result = predict_text("hi")
        assert result["emotion"] is not None


class TestPredictSpeech:
    def test_returns_dict_with_expected_keys(self):
        from src.predict import predict_speech
        dummy_audio = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000).astype(np.float32)
        result = predict_speech(dummy_audio, sr=16000)
        expected_keys = {"emotion", "confidence", "probabilities", "source", "icon", "description"}
        assert isinstance(result, dict)
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_source_is_speech(self):
        from src.predict import predict_speech
        dummy_audio = np.zeros(16000, dtype=np.float32)
        result = predict_speech(dummy_audio, sr=16000)
        assert result["source"] == "speech"

    def test_confidence_in_range(self):
        from src.predict import predict_speech
        dummy_audio = np.random.randn(16000).astype(np.float32)
        result = predict_speech(dummy_audio, sr=16000)
        assert 0 <= result["confidence"] <= 1

    def test_probabilities_sum_to_one(self):
        from src.predict import predict_speech
        dummy_audio = np.random.randn(16000).astype(np.float32)
        result = predict_speech(dummy_audio, sr=16000)
        assert abs(sum(result["probabilities"]) - 1.0) < 0.01

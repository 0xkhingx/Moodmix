import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.preprocess import clean_text, TESS_EMOTION_MAP, TEXT_LABEL_MAP


class TestCleanText:
    def test_lowercase(self):
        assert clean_text("HELLO WORLD") == "hello world"

    def test_punctuation_removed(self):
        assert clean_text("hello, world!") == "hello world"

    def test_digits_removed(self):
        assert clean_text("test123") == "test"

    def test_extra_spaces_removed(self):
        assert clean_text("hello    world") == "hello world"

    def test_empty_after_clean(self):
        result = clean_text("!!! 123")
        assert result == ""


class TestTESSMapping:
    def test_happy(self):
        assert TESS_EMOTION_MAP["happy"] == 0

    def test_calm_and_neutral_same(self):
        assert TESS_EMOTION_MAP["calm"] == TESS_EMOTION_MAP["neutral"] == 3

    def test_ps_maps_to_surprised(self):
        assert TESS_EMOTION_MAP["ps"] == 5
        assert TESS_EMOTION_MAP["surprised"] == 5

    def test_all_expected_keys(self):
        expected = ["happy", "sad", "angry", "calm", "neutral", "fearful", "fear", "surprised", "surprise", "ps", "disgust"]
        for k in expected:
            assert k in TESS_EMOTION_MAP


class TestTextLabelMap:
    def test_joy_to_happy(self):
        assert TEXT_LABEL_MAP["joy"] == "happy"

    def test_sadness_to_sad(self):
        assert TEXT_LABEL_MAP["sadness"] == "sad"

    def test_love_maps_to_happy(self):
        assert TEXT_LABEL_MAP["love"] == "happy"

    def test_calmness(self):
        assert TEXT_LABEL_MAP["calmness"] == "calm"

    def test_disgusted(self):
        assert TEXT_LABEL_MAP["disgusted"] == "disgusted"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spotify_client import get_mood_info, get_search_query, get_all_moods, EMOTIONS, EMOTION_TO_INDEX, INDEX_TO_EMOTION


class TestEmotionMappings:
    def test_emotion_count(self):
        assert len(EMOTIONS) == 7

    def test_expected_emotions(self):
        expected = {"happy", "sad", "angry", "calm", "fearful", "surprised", "disgusted"}
        assert set(EMOTIONS) == expected

    def test_index_roundtrip(self):
        for i, emotion in enumerate(EMOTIONS):
            assert EMOTION_TO_INDEX[emotion] == i
            assert INDEX_TO_EMOTION[i] == emotion

    def test_get_all_moods(self):
        moods = get_all_moods()
        assert moods == EMOTIONS


class TestGetMoodInfo:
    def test_happy_has_icon(self):
        info = get_mood_info("happy")
        assert info["icon"] == "fa-smile"

    def test_sad_has_description(self):
        info = get_mood_info("sad")
        assert "melancholic" in info["description"].lower()

    def test_unknown_mood_returns_none(self):
        assert get_mood_info("nonexistent") is None

    def test_all_moods_have_required_keys(self):
        required = {"search_query", "icon", "description"}
        for mood in EMOTIONS:
            info = get_mood_info(mood)
            for key in required:
                assert key in info, f"{mood} missing key: {key}"


class TestGetSearchQuery:
    def test_happy_query(self):
        q = get_search_query("happy")
        assert isinstance(q, str)
        assert len(q) > 0

    def test_unknown_mood_empty(self):
        assert get_search_query("bogus") == ""

    def test_all_moods_have_nonempty_query(self):
        for mood in EMOTIONS:
            q = get_search_query(mood)
            assert len(q) > 0, f"{mood} has empty search query"

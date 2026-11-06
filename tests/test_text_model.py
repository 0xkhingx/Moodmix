import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import text_model  # noqa: E402
from src.predict import _load_text  # noqa: E402

ensemble_only = pytest.mark.skipif(
    _load_text().mode != "ensemble",
    reason="GoEmotions model not fetched (run scripts/fetch_models.py)",
)


@ensemble_only
class TestEnsemble:
    def test_covers_all_seven_moods(self):
        assert _load_text().labels == text_model.MOODS

    @pytest.mark.parametrize(
        "text,mood",
        [
            ("what is for lunch today", "calm"),
            ("the train leaves at nine", "calm"),
            ("ew, that is absolutely gross", "disgusted"),
            ("I finally got the job!!", "happy"),
            ("i feel so alone lately", "sad"),
        ],
    )
    def test_known_examples(self, text, mood):
        probs = _load_text().predict_proba(text)
        assert text_model.MOODS[int(np.argmax(probs))] == mood

    def test_probabilities_sum_to_one(self):
        assert abs(_load_text().predict_proba("hello there").sum() - 1.0) < 1e-6


class TestFallback:
    def test_missing_goemotions_falls_back_to_lr(self, tmp_path):
        with patch.object(text_model, "GOEMO_DIR", tmp_path):
            with patch.object(text_model.GoEmotions.__init__, "__defaults__", (tmp_path, 1)):
                m = text_model.TextEmotionModel()
        assert m.mode == "lr"
        assert m.labels == ["angry", "fearful", "happy", "sad", "surprised"]
        assert abs(m.predict_proba("I am happy").sum() - 1.0) < 1e-6

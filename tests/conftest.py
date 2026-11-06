import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _isolate_api_state():
    """Clear in-memory API caches/limits so tests don't leak into each other."""
    import api

    api._track_cache.clear()
    api._hits.clear()
    yield
    api._track_cache.clear()
    api._hits.clear()

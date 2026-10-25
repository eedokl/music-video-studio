"""Shared test setup.

The studio reads its projects folder at import time, so point it at a throw-away folder BEFORE any
studio module is imported: tests must never see or touch the real projects/.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ["STUDIO_PROJECTS"] = tempfile.mkdtemp(prefix="studio-test-projects-")

# the analysis scripts run as standalone files (not a package): make them importable for tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "studio" / "scripts"))


@pytest.fixture
def projects(tmp_path, monkeypatch):
    """An empty projects folder for one test."""
    from studio import store

    monkeypatch.setattr(store, "PROJECTS", tmp_path)
    return tmp_path


def make_line(lid: str, text: str, t0: float = 0.0, step: float = 0.5, **extra) -> dict:
    """A lyrics line as the pipeline writes it: one entry per word with start/end times."""
    words = [{"w": w, "t": round(t0 + k * step, 3), "e": round(t0 + (k + 1) * step - 0.05, 3)} for k, w in enumerate(text.split(" "))]
    return {"id": lid, "text": text, "words": words, **extra}

"""Time machine and twin-versus-twin endpoints."""
import os
import tempfile
from pathlib import Path

# Same throwaway-database trick as the other test files (first module to import the app wins).
_db_file = Path(tempfile.mkdtemp()) / "test_twin_extra.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_file.as_posix()}")

import pytest
from fastapi.testclient import TestClient

from app.main import app  # also puts the repo root on sys.path

# Skip these tests (instead of failing) if Ravneet's modules cannot be imported here.
pytest.importorskip("ml.age_progression")
pytest.importorskip("ml.twin_comparison")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


LIFESTYLE = {"sex": "male", "sleep": 7, "exercise": 3, "smoking": 0, "diet": 3}


def _profile(**changes):
    return dict({"age": 40, **LIFESTYLE}, **changes)


def test_timeline_returns_data(client):
    r = client.post("/twin/timeline", json=LIFESTYLE)
    assert r.status_code == 200
    assert r.json()


def test_timeline_custom_range(client):
    r = client.post("/twin/timeline", json=dict(LIFESTYLE, start_age=30, end_age=60, step=10))
    assert r.status_code == 200


def test_timeline_validation(client):
    assert client.post("/twin/timeline", json=dict(LIFESTYLE, start_age=60, end_age=30)).status_code == 422
    assert client.post("/twin/timeline", json=dict(LIFESTYLE, sex="robot")).status_code == 422
    assert client.post("/twin/timeline", json=dict(LIFESTYLE, diet=9)).status_code == 422


def test_compare_two_profiles(client):
    body = {"profile_a": _profile(), "profile_b": _profile(smoking=20), "name_a": "Non-smoker", "name_b": "Smoker"}
    r = client.post("/twin/compare", json=body)
    assert r.status_code == 200
    assert r.json()


def test_compare_validation(client):
    assert client.post("/twin/compare", json={"profile_a": _profile()}).status_code == 422

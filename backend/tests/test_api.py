"""Smoke tests for the skeleton. Run from the backend folder:  pytest"""
import os
import tempfile
from pathlib import Path

# Use a throwaway database; must be set before the app is imported.
_db_file = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.as_posix()}"

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import User

ORGANS = {
    "brain", "heart", "lungs", "liver", "stomach", "intestines",
    "kidneys", "bladder", "pancreas", "spleen", "thyroid", "reproductive",
}
PREDICT_BODY = {"age": 40, "sex": "male", "sleep": 7, "exercise": 3, "smoking": 0, "diet": 3}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_pro(email):
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == email).first().role = "pro"
        db.commit()
    finally:
        db.close()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_body_both_sexes(client):
    for sex in ("male", "female"):
        data = client.get(f"/body/{sex}").json()
        assert data["sex"] == sex
        assert {o["id"] for o in data["organs"]} == ORGANS
        assert len(data["systems"]) == 11
    assert client.get("/body/other").status_code == 422


def test_predict_has_all_organs(client):
    data = client.post("/twin/predict", json=PREDICT_BODY).json()
    assert set(data) == ORGANS
    assert all(0 <= v["score"] <= 100 and v["vitals"] for v in data.values())


def test_predict_reacts_to_smoking(client):
    heavy = dict(PREDICT_BODY, smoking=30)
    low = client.post("/twin/predict", json=PREDICT_BODY).json()["lungs"]["score"]
    high = client.post("/twin/predict", json=heavy).json()["lungs"]["score"]
    assert high < low


def test_predict_validation(client):
    assert client.post("/twin/predict", json=dict(PREDICT_BODY, age=5)).status_code == 422
    assert client.post("/twin/predict", json=dict(PREDICT_BODY, diet=9)).status_code == 422


def test_register_login_me(client):
    headers = _login(client, "a@example.com")
    assert client.get("/auth/me", headers=headers).json()["email"] == "a@example.com"
    dup = client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    assert dup.status_code == 400
    bad = client.post("/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    assert bad.status_code == 401


def test_pro_endpoints_are_protected(client):
    body = {"age": 30, "sex": "female", "height_cm": 165, "weight_kg": 60}
    assert client.post("/twin/personal", json=body).status_code == 401
    headers = _login(client, "public@example.com")
    assert client.post("/twin/personal", json=body, headers=headers).status_code == 403
    _make_pro("public@example.com")
    r = client.post("/twin/personal", json=body, headers=headers)
    assert r.status_code == 200
    assert "morph" in r.json() and "heart" in r.json()


def test_pathogens_public_vs_pro(client):
    public = client.get("/pathogens").json()
    assert {p["id"] for p in public} == {"respiratory_virus", "gut_virus", "bloodstream_bacterium"}
    headers = _login(client, "pro1@example.com")
    _make_pro("pro1@example.com")
    assert len(client.get("/pathogens", headers=headers).json()) == 4


def test_simulate(client):
    body = {"pathogen_id": "respiratory_virus", "day": 6, "treatment": 0}
    data = client.post("/pathogens/simulate", json=body).json()
    assert len(data["curve"]) == 31 and "lungs" in data["organs"]
    treated = client.post("/pathogens/simulate", json=dict(body, treatment=1)).json()
    assert treated["load"] < data["load"]
    assert client.post("/pathogens/simulate", json=dict(body, pathogen_id="nope")).status_code == 404
    assert client.post("/pathogens/simulate", json=dict(body, pathogen_id="novel_virus_demo")).status_code == 401


def test_upload_validation(client):
    headers = _login(client, "pro2@example.com")
    _make_pro("pro2@example.com")
    bad = client.post("/pathogens/upload", headers=headers, files={"file": ("x.csv", b"day,load\n1,2\n")})
    assert bad.status_code == 200 and bad.json()["parameters"] is None
    good_csv = b"day,load\n0,1\n1,2\n2,4\n3,5\n4,4\n5,2\n"
    good = client.post("/pathogens/upload", headers=headers, files={"file": ("x.csv", good_csv)})
    assert good.json()["parameters"] is not None and good.json()["validation_errors"] == []


def test_sources_limit(client):
    assert len(client.get("/research/sources").json()) == 5
    headers = _login(client, "pro3@example.com")
    _make_pro("pro3@example.com")
    assert len(client.get("/research/sources", headers=headers).json()) == 8

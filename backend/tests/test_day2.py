"""Day 2 tests: experiments, uploads, function adapter. (Billing is owned by Saket.)"""
import os
import tempfile
from datetime import timedelta
from pathlib import Path

# Same throwaway-database trick as test_api.py (first module to import the app wins).
_db_file = Path(tempfile.mkdtemp()) / "test_day2.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_file.as_posix()}")

import pytest
from fastapi.testclient import TestClient

from app import config, functions
from app.db import SessionLocal
from app.main import app
from app.models import User, utcnow

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user(email):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        db.expunge(u)
        return u
    finally:
        db.close()


def _make_pro(email):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        u.role = "pro"
        db.commit()
    finally:
        db.close()


def _pro_headers(client, email):
    h = _login(client, email)
    _make_pro(email)
    return h


def test_expired_pro_counts_as_public(client):
    h = _pro_headers(client, "w4@example.com")
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == "w4@example.com").first()
        u.pro_expires_at = utcnow() - timedelta(days=1)
        db.commit()
    finally:
        db.close()
    assert client.get("/experiments", headers=h).status_code == 403


# ---------- experiments ----------

def test_experiments_need_pro(client):
    assert client.get("/experiments").status_code == 401
    h = _login(client, "e0@example.com")
    assert client.get("/experiments", headers=h).status_code == 403
    assert client.post("/experiments", json={"name": "x"}, headers=h).status_code == 403


def test_experiment_save_get_list(client):
    h = _pro_headers(client, "e1@example.com")
    body = {"name": "Flu run", "pathogen_id": "respiratory_virus",
            "parameters": {"treatment": 0.3, "day": 5}, "seed": 42}
    r = client.post("/experiments", json=body, headers=h)
    assert r.status_code == 201
    e = r.json()
    assert e["seed"] == 42 and e["model_version"] == config.MODEL_VERSION and e["fork_of"] is None
    assert e["parameters"] == body["parameters"]
    assert client.get(f"/experiments/{e['id']}", headers=h).json()["name"] == "Flu run"
    assert [x["id"] for x in client.get("/experiments", headers=h).json()] == [e["id"]]


def test_experiment_seed_defaults_and_validation(client):
    h = _pro_headers(client, "e2@example.com")
    r = client.post("/experiments", json={"name": "auto seed"}, headers=h)
    assert isinstance(r.json()["seed"], int)
    assert client.post("/experiments", json={"name": ""}, headers=h).status_code == 422
    assert client.post("/experiments", json={"name": "x", "seed": -1}, headers=h).status_code == 422


def test_experiment_fork(client):
    h = _pro_headers(client, "e3@example.com")
    src = client.post("/experiments", json={"name": "base", "parameters": {"a": 1}, "seed": 7}, headers=h).json()
    plain = client.post(f"/experiments/{src['id']}/fork", headers=h)
    assert plain.status_code == 201
    f = plain.json()
    assert f["fork_of"] == src["id"] and f["seed"] == 7 and f["parameters"] == {"a": 1}
    assert f["name"] == "base (fork)"
    changed = client.post(f"/experiments/{src['id']}/fork", json={"name": "v2", "parameters": {"a": 2}}, headers=h).json()
    assert changed["name"] == "v2" and changed["parameters"] == {"a": 2}
    # contract style: fork_of in the create body
    via_body = client.post("/experiments", json={"name": "c", "fork_of": src["id"]}, headers=h)
    assert via_body.status_code == 201 and via_body.json()["fork_of"] == src["id"]
    assert client.post("/experiments", json={"name": "c", "fork_of": 99999}, headers=h).status_code == 404


def test_experiment_export(client):
    h = _pro_headers(client, "e4@example.com")
    e = client.post("/experiments", json={"name": "exp", "seed": 1}, headers=h).json()
    r = client.get(f"/experiments/{e['id']}/export", headers=h)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.json()["seed"] == 1 and r.json()["model_version"] == config.MODEL_VERSION


def test_experiments_are_private(client):
    ha = _pro_headers(client, "e5@example.com")
    hb = _pro_headers(client, "e6@example.com")
    e = client.post("/experiments", json={"name": "mine"}, headers=ha).json()
    assert client.get(f"/experiments/{e['id']}", headers=hb).status_code == 404
    assert client.post(f"/experiments/{e['id']}/fork", headers=hb).status_code == 404
    assert client.get(f"/experiments/{e['id']}/export", headers=hb).status_code == 404
    assert client.get("/experiments", headers=hb).json() == []


# ---------- uploads ----------

def test_uploads_need_pro(client):
    files = {"file": ("a.csv", b"day,load\n1,2\n")}
    assert client.post("/uploads", files=files).status_code == 401
    h = _login(client, "u0@example.com")
    assert client.post("/uploads", files=files, headers=h).status_code == 403


def test_upload_roundtrip_and_delete(client):
    h = _pro_headers(client, "u1@example.com")
    data = b"day,load\n0,1\n1,2\n"
    r = client.post("/uploads", files={"file": ("my data.csv", data, "text/csv")}, headers=h)
    assert r.status_code == 201
    up = r.json()
    assert up["filename"] == "my data.csv" and up["size_bytes"] == len(data)
    assert client.get(f"/uploads/{up['id']}", headers=h).content == data
    assert [u["id"] for u in client.get("/uploads", headers=h).json()] == [up["id"]]
    assert client.delete(f"/uploads/{up['id']}", headers=h).status_code == 204
    assert client.get(f"/uploads/{up['id']}", headers=h).status_code == 404


def test_upload_rules(client, monkeypatch):
    h = _pro_headers(client, "u2@example.com")
    bad_type = client.post("/uploads", files={"file": ("virus.exe", b"x")}, headers=h)
    assert bad_type.status_code == 400
    assert client.post("/uploads", files={"file": ("empty.csv", b"")}, headers=h).status_code == 400
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    assert client.post("/uploads", files={"file": ("big.csv", b"x" * 11)}, headers=h).status_code == 400


def test_upload_path_traversal_is_harmless(client):
    h = _pro_headers(client, "u3@example.com")
    r = client.post("/uploads", files={"file": ("../../evil.csv", b"a,b\n1,2\n")}, headers=h)
    assert r.status_code == 201 and r.json()["filename"] == "evil.csv"
    assert not (config.UPLOAD_DIR.parent / "evil.csv").exists()


def test_uploads_are_private(client):
    ha = _pro_headers(client, "u4@example.com")
    hb = _pro_headers(client, "u5@example.com")
    up = client.post("/uploads", files={"file": ("a.csv", b"1,2\n")}, headers=ha).json()
    assert client.get(f"/uploads/{up['id']}", headers=hb).status_code == 404
    assert client.delete(f"/uploads/{up['id']}", headers=hb).status_code == 404
    assert client.get("/uploads", headers=hb).json() == []


# ---------- function adapter ----------

def test_health_functions_reports_sources(client):
    data = client.get("/health/functions").json()
    assert set(data) == {"predict_health", "simulate_pathogen", "fit_pathogen", "get_sources"}
    assert all(v == "dummy" or v.startswith("real:") for v in data.values())


def test_adapter_functions_keep_contract_shape():
    out = functions.predict_health(40, "male", 7, 3, 0, 3)
    assert len(out) == 12 and all("score" in v and "vitals" in v for v in out.values())


def test_vitals_split_contract_v1_1():
    out = functions.predict_health(40, "male", 7, 3, 0, 3)
    assert set(out["liver"]["vitals"]) == {"alt", "ast", "bilirubin"}
    for organ in ("stomach", "intestines", "pancreas"):
        assert set(out[organ]["vitals"]) == {"gut_inflammation"}
    assert all(isinstance(v["score"], int) for v in out.values())
    assert out["spleen"]["vitals"]["pathogen_load"] == 0.0

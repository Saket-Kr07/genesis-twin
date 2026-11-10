"""Admin approval linked to the model version registry."""
import os
import tempfile
from pathlib import Path

# Same throwaway-database trick as the other test files (first module to import the app wins).
_db_file = Path(tempfile.mkdtemp()) / "test_admin_registry_link.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_file.as_posix()}")

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import User


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin(client, email):
    headers = _login(client, email)
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        u.role = "admin"
        db.commit()
    finally:
        db.close()
    return headers


def _register(client, headers, version):
    r = client.post(
        "/admin/model-versions",
        headers=headers,
        json={"version": version, "change_log": f"Candidate {version}", "papers": ["10.1000/x"]},
    )
    assert r.status_code == 201
    return r.json()


def _find(client, headers, version):
    rows = client.get("/research/model-versions", headers=headers).json()
    return next(r for r in rows if r["version"] == version)


def test_approving_a_registered_version_updates_the_registry(client):
    headers = _admin(client, "link-admin1@example.com")
    _register(client, headers, "v20.0")
    assert _find(client, headers, "v20.0")["status"] == "candidate"
    r = client.post(
        "/admin/models/approve", headers=headers, json={"model_version": "v20.0", "approve": True}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "approved"
    assert data["registry_updated"] is True and data["registry_status"] == "approved"
    row = _find(client, headers, "v20.0")
    assert row["status"] == "approved" and row["approved_at"] is not None


def test_rejecting_a_registered_version(client):
    headers = _admin(client, "link-admin2@example.com")
    _register(client, headers, "v21.0")
    r = client.post(
        "/admin/models/approve",
        headers=headers,
        json={"model_version": "v21.0", "approve": False, "note": "Failed validation"},
    )
    assert r.status_code == 200
    assert r.json()["registry_status"] == "rejected"
    row = _find(client, headers, "v21.0")
    assert row["status"] == "rejected" and row["approved_at"] is None


def test_an_unregistered_version_is_still_logged(client):
    headers = _admin(client, "link-admin3@example.com")
    r = client.post(
        "/admin/models/approve", headers=headers, json={"model_version": "v99.9", "approve": True}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["registry_updated"] is False and data["registry_status"] is None
    logged = client.get("/admin/models", headers=headers).json()
    assert any(d["model_version"] == "v99.9" for d in logged)


def test_the_newest_approval_becomes_the_current_version(client):
    headers = _admin(client, "link-admin4@example.com")
    for v in ("v30.0", "v30.1"):
        _register(client, headers, v)
        client.post("/admin/models/approve", headers=headers, json={"model_version": v, "approve": True})
    public = client.get("/research/model-versions").json()  # no login: public view
    assert public[0]["version"] == "v30.1" and public[0]["status"] == "approved"


def test_rolling_back_makes_the_previous_version_current(client):
    headers = _admin(client, "link-admin5@example.com")
    for v in ("v40.0", "v40.1"):
        _register(client, headers, v)
        client.post("/admin/models/approve", headers=headers, json={"model_version": v, "approve": True})
    client.post("/admin/models/approve", headers=headers, json={"model_version": "v40.1", "approve": False})
    public = client.get("/research/model-versions").json()
    approved = [r for r in public if r["status"] == "approved"]
    assert approved and approved[0]["version"] == "v40.0"


def test_only_admins_can_approve(client):
    headers = _login(client, "link-plain@example.com")
    r = client.post(
        "/admin/models/approve", headers=headers, json={"model_version": "v1.0", "approve": True}
    )
    assert r.status_code == 403

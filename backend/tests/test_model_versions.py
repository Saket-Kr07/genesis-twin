
"""Tests for the model version registry."""

import os
import tempfile
from pathlib import Path

_db_file = Path(tempfile.mkdtemp()) / "test_model_versions.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_file.as_posix()}")

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import User


def _login(client, email, password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _set_role(email, role):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.role = role
        db.commit()
    finally:
        db.close()


def test_model_versions_are_public(client=None):
    with TestClient(app) as client:
        response = client.get("/research/model-versions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_register_model_version_requires_admin():
    with TestClient(app) as client:
        body = {
            "version": "v-test-unauthorized",
            "change_log": "Test candidate",
            "papers": ["10.1234/example"],
            "metrics": {"mae": 2.5},
        }

        assert client.post("/admin/model-versions", json=body).status_code == 401

        headers = _login(client, "version_user@example.com")
        response = client.post(
            "/admin/model-versions", headers=headers, json=body
        )
        assert response.status_code == 403


def test_admin_can_register_candidate_version():
    with TestClient(app) as client:
        headers = _login(client, "version_admin@example.com")
        _set_role("version_admin@example.com", "admin")

        body = {
            "version": "v-test-admin",
            "change_log": "Improved validation metrics",
            "papers": ["10.1234/example"],
            "metrics": {"mae": 2.5, "r2": 0.85},
        }

        response = client.post(
            "/admin/model-versions", headers=headers, json=body
        )

        assert response.status_code == 201
        data = response.json()
        assert data["version"] == "v-test-admin"
        assert data["status"] == "candidate"
        assert data["papers"] == ["10.1234/example"]
        assert data["metrics"]["mae"] == 2.5

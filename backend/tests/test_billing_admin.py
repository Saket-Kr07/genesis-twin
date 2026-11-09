"""Billing (test mode) and admin tests."""
import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path

# Same throwaway-database trick as the other test files (first module to import the app wins).
_db_file = Path(tempfile.mkdtemp()) / "test_billing_admin.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_file.as_posix()}")

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import User, utcnow
from app.routers.billing import WEBHOOK_SECRET


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


def _set_role(email, role):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        u.role = role
        db.commit()
    finally:
        db.close()


def _signed(payload, secret=WEBHOOK_SECRET):
    raw = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {"X-Signature": sig, "Content-Type": "application/json"}


# ---------- billing ----------

def test_checkout_needs_login(client):
    assert client.post("/billing/checkout").status_code == 401


def test_checkout_sets_pro_with_expiry_and_says_test_mode(client):
    headers = _login(client, "buyer1@example.com")
    assert _user("buyer1@example.com").role == "public"
    r = client.post("/billing/checkout", headers=headers, json={"plan": "pro_monthly"})
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "test" and "TEST MODE" in data["note"]
    assert data["role"] == "pro"
    u = _user("buyer1@example.com")
    assert u.role == "pro" and u.pro_expires_at > utcnow()


def test_checkout_works_without_a_body(client):
    headers = _login(client, "buyer2@example.com")
    assert client.post("/billing/checkout", headers=headers).status_code == 200
    assert _user("buyer2@example.com").role == "pro"


def test_checkout_does_not_downgrade_an_admin(client):
    headers = _login(client, "boss@example.com")
    _set_role("boss@example.com", "admin")
    assert client.post("/billing/checkout", headers=headers).status_code == 200
    assert _user("boss@example.com").role == "admin"


def test_webhook_rejects_a_bad_signature(client):
    _login(client, "buyer3@example.com")
    uid = _user("buyer3@example.com").id
    raw, headers = _signed({"event": "payment.succeeded", "user_id": uid}, secret="wrong-secret")
    r = client.post("/billing/webhook", content=raw, headers=headers)
    assert r.status_code == 400
    assert _user("buyer3@example.com").role == "public"


def test_webhook_rejects_a_missing_signature(client):
    raw = json.dumps({"event": "payment.succeeded", "user_id": 1}).encode()
    assert client.post("/billing/webhook", content=raw).status_code == 400


def test_webhook_with_a_valid_signature_grants_pro(client):
    _login(client, "buyer4@example.com")
    uid = _user("buyer4@example.com").id
    raw, headers = _signed({"event": "payment.succeeded", "user_id": uid})
    r = client.post("/billing/webhook", content=raw, headers=headers)
    assert r.status_code == 200 and r.json()["action"] == "pro_granted"
    u = _user("buyer4@example.com")
    assert u.role == "pro" and u.pro_expires_at > utcnow()


def test_webhook_ignores_other_events(client):
    _login(client, "buyer5@example.com")
    uid = _user("buyer5@example.com").id
    raw, headers = _signed({"event": "payment.failed", "user_id": uid})
    r = client.post("/billing/webhook", content=raw, headers=headers)
    assert r.status_code == 200 and r.json()["action"] == "ignored"
    assert _user("buyer5@example.com").role == "public"


def test_webhook_unknown_user_and_bad_user_id(client):
    raw, headers = _signed({"event": "payment.succeeded", "user_id": 999999})
    assert client.post("/billing/webhook", content=raw, headers=headers).status_code == 404
    raw, headers = _signed({"event": "payment.succeeded", "user_id": "abc"})
    assert client.post("/billing/webhook", content=raw, headers=headers).status_code == 400


# ---------- admin ----------

def test_admin_endpoints_need_login_and_the_admin_role(client):
    body = {"model_version": "v1.1", "approve": True}
    assert client.post("/admin/models/approve", json=body).status_code == 401
    headers = _login(client, "plain@example.com")
    assert client.post("/admin/models/approve", json=body, headers=headers).status_code == 403
    assert client.get("/admin/models", headers=headers).status_code == 403
    client.post("/billing/checkout", headers=headers)  # pro is still not admin
    assert client.post("/admin/models/approve", json=body, headers=headers).status_code == 403


def test_admin_can_approve_and_reject_and_list(client):
    headers = _login(client, "admin1@example.com")
    _set_role("admin1@example.com", "admin")
    ok = client.post(
        "/admin/models/approve",
        headers=headers,
        json={"model_version": "v1.1", "approve": True, "note": "Looks good"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved" and ok.json()["note"] == "Looks good"
    no = client.post(
        "/admin/models/approve", headers=headers, json={"model_version": "v1.2", "approve": False}
    )
    assert no.status_code == 200 and no.json()["status"] == "rejected"
    listed = client.get("/admin/models", headers=headers).json()
    assert [d["model_version"] for d in listed][:2] == ["v1.2", "v1.1"]


def test_admin_approve_validates_input(client):
    headers = _login(client, "admin2@example.com")
    _set_role("admin2@example.com", "admin")
    assert client.post("/admin/models/approve", headers=headers, json={"approve": True}).status_code == 422
    empty = {"model_version": "", "approve": True}
    assert client.post("/admin/models/approve", headers=headers, json=empty).status_code == 422

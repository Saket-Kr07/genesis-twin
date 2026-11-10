"""Billing in TEST MODE only. No card details are ever stored.

POST /billing/checkout  (logged in)  mock checkout: sets role pro for PRO_DAYS days.
POST /billing/webhook   (provider)   verifies an HMAC-SHA256 signature in the
                                     X-Signature header, then sets role pro.
A real gateway (Razorpay or Stripe test mode) would call the webhook the same way."""
import hashlib
import hmac
import json
import os
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import User, utcnow

router = APIRouter(prefix="/billing", tags=["billing"])

PRO_DAYS = 30
WEBHOOK_SECRET = os.environ.get("BILLING_WEBHOOK_SECRET", "dev-webhook-secret-change-me")
TEST_NOTE = "TEST MODE: no real payment was made. This only simulates a subscription."


class CheckoutRequest(BaseModel):
    plan: str = "pro_monthly"


def _grant_pro(db: Session, user: User) -> None:
    if user.role == "admin":  # never downgrade an admin
        return
    user.role = "pro"
    user.pro_expires_at = utcnow() + timedelta(days=PRO_DAYS)
    db.commit()
    db.refresh(user)


@router.post("/checkout")
def checkout(
    body: Optional[CheckoutRequest] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _grant_pro(db, user)
    return {
        "mode": "test",
        "status": "paid",
        "plan": (body.plan if body else "pro_monthly"),
        "role": user.role,
        "pro_expires_at": user.pro_expires_at.isoformat() if user.pro_expires_at else None,
        "note": TEST_NOTE,
    }


@router.post("/webhook")
async def webhook(
    request: Request,
    x_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    expected = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_signature):
        raise HTTPException(status_code=400, detail="Invalid signature.")
    try:
        data = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="The webhook body is not valid JSON.")
    if data.get("event") != "payment.succeeded":
        return {"received": True, "action": "ignored"}
    try:
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="user_id is missing or not a number.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    _grant_pro(db, user)
    return {"received": True, "action": "pro_granted", "role": user.role}

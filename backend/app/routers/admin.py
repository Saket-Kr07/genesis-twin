"""Admin only. Approve or reject a model version and keep the decision log.

The decision is always logged in model_decisions. If a version with the same name is
registered in model_versions (see model_versions.py), its status and approved_at are
updated too. Approving a version makes it the current one, because the registry picks
the latest approved_at."""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Session

from ..db import Base, get_db
from ..deps import require_role
from ..models import User, utcnow
from .model_versions import ModelVersion

router = APIRouter(prefix="/admin", tags=["admin"])


class ModelDecision(Base):
    __tablename__ = "model_decisions"

    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(String(40), nullable=False, index=True)
    approved = Column(Boolean, nullable=False)
    note = Column(String(500), nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ApproveRequest(BaseModel):
    model_version: str = Field(min_length=1, max_length=40)
    approve: bool
    note: Optional[str] = Field(default=None, max_length=500)


def _out(d: ModelDecision) -> dict:
    return {
        "id": d.id,
        "model_version": d.model_version,
        "status": "approved" if d.approved else "rejected",
        "note": d.note,
        "decided_by": d.decided_by,
        "created_at": d.created_at.isoformat(),
    }


@router.post("/models/approve")
def approve_model(
    body: ApproveRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    version = body.model_version.strip()
    d = ModelDecision(
        model_version=version,
        approved=body.approve,
        note=body.note,
        decided_by=admin.id,
    )
    db.add(d)

    # Update the registry row, if this version was registered. One commit for both.
    row = db.query(ModelVersion).filter(ModelVersion.version == version).first()
    if row is not None:
        if body.approve:
            row.status = "approved"
            row.approved_at = utcnow()
        else:
            row.status = "rejected"
            row.approved_at = None
    db.commit()
    db.refresh(d)

    out = _out(d)
    out["registry_updated"] = row is not None
    out["registry_status"] = row.status if row is not None else None
    return out


@router.get("/models")
def list_decisions(
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    rows = db.query(ModelDecision).order_by(ModelDecision.id.desc()).all()
    return [_out(r) for r in rows]

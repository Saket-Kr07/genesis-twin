
"""Model version registry and history endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import Base, get_db
from ..deps import get_optional_user, is_pro, require_role
from ..models import User, utcnow

router = APIRouter(tags=["model versions"])


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(40), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="candidate", index=True)
    change_log = Column(Text, nullable=False)
    papers = Column(JSON, nullable=False, default=list)
    metrics = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    approved_at = Column(DateTime, nullable=True)


class ModelVersionCreate(BaseModel):
    version: str = Field(min_length=1, max_length=40)
    change_log: str = Field(min_length=1)
    papers: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)


def _out(row: ModelVersion) -> dict:
    return {
        "version": row.version,
        "status": row.status,
        "change_log": row.change_log,
        "papers": row.papers or [],
        "metrics": row.metrics or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
    }


def get_current_approved_version(db: Session) -> Optional[str]:
    """Return the latest approved version, if one exists."""
    row = (
        db.query(ModelVersion)
        .filter(ModelVersion.status == "approved")
        .order_by(ModelVersion.approved_at.desc(), ModelVersion.created_at.desc())
        .first()
    )
    return row.version if row else None


@router.get("/research/model-versions")
def list_model_versions(
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Public: current approved version plus five recent records. Pro: full history."""
    query = db.query(ModelVersion).order_by(
        ModelVersion.created_at.desc(), ModelVersion.id.desc()
    )

    if is_pro(user):
        rows = query.all()
        return [_out(row) for row in rows]

    current = (
        db.query(ModelVersion)
        .filter(ModelVersion.status == "approved")
        .order_by(ModelVersion.approved_at.desc(), ModelVersion.created_at.desc())
        .first()
    )

    recent = query.limit(5).all()
    rows = []
    seen = set()

    if current:
        rows.append(current)
        seen.add(current.id)

    for row in recent:
        if row.id not in seen:
            rows.append(row)
            seen.add(row.id)

    return [_out(row) for row in rows]


@router.post("/admin/model-versions", status_code=201)
def register_model_version(
    body: ModelVersionCreate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Register a new candidate version. Approval is a separate admin action."""
    version = body.version.strip()
    if not version:
        raise HTTPException(status_code=422, detail="Version cannot be blank.")

    row = ModelVersion(
        version=version,
        status="candidate",
        change_log=body.change_log,
        papers=body.papers,
        metrics=body.metrics,
    )
    db.add(row)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This model version is already registered.",
        )

    db.refresh(row)
    return _out(row)

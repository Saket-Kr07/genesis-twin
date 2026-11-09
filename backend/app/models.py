"""Database tables: users, experiments, uploads."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String

from .db import Base


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (works the same on SQLite and PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="public")  # public, pro, admin
    pro_expires_at = Column(DateTime, nullable=True)  # None = no expiry
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Experiment(Base):
    """Stores parameters, seed and model version so a run can be reproduced."""

    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    pathogen_id = Column(String(100), nullable=True)
    parameters = Column(JSON, nullable=False, default=dict)
    seed = Column(Integer, nullable=False)
    model_version = Column(String(40), nullable=False)
    fork_of = Column(Integer, ForeignKey("experiments.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)  # name the user sent (display only)
    stored_name = Column(String(80), nullable=False)  # random name on disk
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)

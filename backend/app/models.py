"""Database tables. Only `users` exists tonight; experiments, subscriptions etc. come on Day 2."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

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

"""Settings read from environment variables or backend/.env (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./genesis.db")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-set-JWT_SECRET-in-your-env-file")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "1440"))
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# Public (not logged in) users see only the latest 5 papers.
PUBLIC_SOURCES_LIMIT = 5

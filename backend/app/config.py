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

# Version string saved with every experiment (bump when the real models change).
MODEL_VERSION = os.getenv("MODEL_VERSION", "v0.1.0")

# Uploads (Pro). Files are stored on disk under UPLOAD_DIR/<user_id>/.
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parent.parent / "uploads")))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5_000_000)))
ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".json", ".txt", ".png", ".jpg", ".jpeg", ".glb"}

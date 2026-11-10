"""File uploads (Pro). Files go to disk under UPLOAD_DIR/<user_id>/ with a random name,
so the name a user sends is never used as a path. Users only see their own files."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..deps import require_role
from ..models import Upload, User

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _out(u: Upload) -> dict:
    return {
        "id": u.id,
        "filename": u.filename,
        "size_bytes": u.size_bytes,
        "content_type": u.content_type,
        "created_at": u.created_at.isoformat() + "Z",
    }


def _get_own(db: Session, user: User, upload_id: int) -> Upload:
    u = db.get(Upload, upload_id)
    if u is None or u.user_id != user.id:
        raise HTTPException(status_code=404, detail="File not found.")
    return u


def _path(u: Upload) -> Path:
    return config.UPLOAD_DIR / str(u.user_id) / u.stored_name


@router.post("", status_code=201)
async def upload(file: UploadFile = File(...), user: User = Depends(require_role("pro")),
                 db: Session = Depends(get_db)):
    display_name = Path(file.filename or "file").name[:255] or "file"
    ext = Path(display_name).suffix.lower()
    if ext not in config.ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(config.ALLOWED_UPLOAD_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"This file type is not allowed. Use: {allowed}.")
    raw = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(raw) > config.MAX_UPLOAD_BYTES:
        mb = config.MAX_UPLOAD_BYTES // 1_000_000
        raise HTTPException(status_code=400, detail=f"The file is too large (limit {mb} MB).")
    if not raw:
        raise HTTPException(status_code=400, detail="The file is empty.")

    stored = f"{uuid.uuid4().hex}{ext}"
    folder = config.UPLOAD_DIR / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / stored).write_bytes(raw)
    row = Upload(user_id=user.id, filename=display_name, stored_name=stored,
                 content_type=file.content_type, size_bytes=len(raw))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get("")
def list_mine(user: User = Depends(require_role("pro")), db: Session = Depends(get_db)):
    rows = db.query(Upload).filter(Upload.user_id == user.id).order_by(Upload.id.desc()).all()
    return [_out(u) for u in rows]


@router.get("/{upload_id}")
def download(upload_id: int, user: User = Depends(require_role("pro")),
             db: Session = Depends(get_db)):
    u = _get_own(db, user, upload_id)
    path = _path(u)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path, filename=u.filename, media_type=u.content_type or "application/octet-stream")


@router.delete("/{upload_id}", status_code=204)
def delete(upload_id: int, user: User = Depends(require_role("pro")),
           db: Session = Depends(get_db)):
    u = _get_own(db, user, upload_id)
    _path(u).unlink(missing_ok=True)
    db.delete(u)
    db.commit()

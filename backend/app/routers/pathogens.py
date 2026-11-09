from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from .. import functions
from ..deps import get_optional_user, is_pro, require_role
from ..schemas import SimulateRequest

router = APIRouter(prefix="/pathogens", tags=["pathogens"])

MAX_UPLOAD_BYTES = 1_000_000


def _authorise(pathogen_id, user):
    """404 for an unknown id. Presets are public; everything else needs Pro."""
    info = functions.get_pathogen(pathogen_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Pathogen not found.")
    if not info["preset"] and not is_pro(user):
        if user is None:
            raise HTTPException(status_code=401, detail="Please log in to use this feature.")
        raise HTTPException(status_code=403, detail="This feature needs a Professional subscription.")


def _run(call, *args):
    """Plain-language errors from the simulation (bad profile, bad input) become 400."""
    try:
        return call(*args)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err))


@router.get("")
def list_pathogens(user=Depends(get_optional_user)):
    """Public: the 3 presets. Pro: the full library."""
    return functions.list_pathogens(include_all=is_pro(user))


@router.post("/upload")
async def upload(file: UploadFile = File(...), user=Depends(require_role("pro"))):
    """Pro. Upload a CSV (columns: day, load). Bad files return parameters = null
    and a list of plain-language validation_errors (still status 200)."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="The file is too large (limit 1 MB).")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="The file could not be read as text. Please save it as a CSV (UTF-8) and try again.",
        )
    result = functions.fit_pathogen(text)
    result["pathogen_id"] = "uploaded_demo" if result["parameters"] is not None else None
    return result


@router.post("/simulate")
def simulate(body: SimulateRequest, user=Depends(get_optional_user)):
    """Public for presets, Pro for everything else. Optional: treatment_start, profile."""
    _authorise(body.pathogen_id, user)
    return _run(
        functions.simulate_pathogen,
        body.pathogen_id,
        body.day,
        body.treatment,
        getattr(body, "treatment_start", 0),
        getattr(body, "profile", None),
    )


@router.post("/timeline")
def timeline(body: SimulateRequest, user=Depends(get_optional_user)):
    """All days in one call, for the day slider. Same access rules as /simulate."""
    _authorise(body.pathogen_id, user)
    return _run(
        functions.simulate_timeline,
        body.pathogen_id,
        body.treatment,
        getattr(body, "treatment_start", 0),
        getattr(body, "profile", None),
    )

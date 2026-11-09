"""Experiments (Pro). Each record stores parameters, seed and model version so a run
can be reproduced. Users only ever see their own experiments."""
import random

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..deps import require_role
from ..models import Experiment, User
from ..schemas import ExperimentCreate, ExperimentFork

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _out(e: Experiment) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "pathogen_id": e.pathogen_id,
        "parameters": e.parameters,
        "seed": e.seed,
        "model_version": e.model_version,
        "fork_of": e.fork_of,
        "created_at": e.created_at.isoformat() + "Z",
    }


def _get_own(db: Session, user: User, experiment_id: int) -> Experiment:
    e = db.get(Experiment, experiment_id)
    if e is None or e.user_id != user.id:  # same answer for "missing" and "not yours"
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return e


def _save(db: Session, user: User, **fields) -> Experiment:
    e = Experiment(user_id=user.id, model_version=config.MODEL_VERSION, **fields)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.post("", status_code=201)
def create(body: ExperimentCreate, user: User = Depends(require_role("pro")),
           db: Session = Depends(get_db)):
    if body.fork_of is not None:
        _get_own(db, user, body.fork_of)
    seed = body.seed if body.seed is not None else random.randint(0, 2_147_483_647)
    e = _save(db, user, name=body.name, pathogen_id=body.pathogen_id,
              parameters=body.parameters, seed=seed, fork_of=body.fork_of)
    return _out(e)


@router.get("")
def list_mine(user: User = Depends(require_role("pro")), db: Session = Depends(get_db)):
    rows = (db.query(Experiment).filter(Experiment.user_id == user.id)
            .order_by(Experiment.id.desc()).all())
    return [_out(e) for e in rows]


@router.get("/{experiment_id}")
def get_one(experiment_id: int, user: User = Depends(require_role("pro")),
            db: Session = Depends(get_db)):
    return _out(_get_own(db, user, experiment_id))


@router.post("/{experiment_id}/fork", status_code=201)
def fork(experiment_id: int, body: ExperimentFork = ExperimentFork(),
         user: User = Depends(require_role("pro")), db: Session = Depends(get_db)):
    """Copy an experiment, optionally changing the name, parameters or seed."""
    src = _get_own(db, user, experiment_id)
    e = _save(
        db, user,
        name=body.name or f"{src.name} (fork)",
        pathogen_id=src.pathogen_id,
        parameters=body.parameters if body.parameters is not None else src.parameters,
        seed=body.seed if body.seed is not None else src.seed,
        fork_of=src.id,
    )
    return _out(e)


@router.get("/{experiment_id}/export")
def export(experiment_id: int, user: User = Depends(require_role("pro")),
           db: Session = Depends(get_db)):
    """Download one experiment as a JSON file (everything needed to reproduce it)."""
    data = _out(_get_own(db, user, experiment_id))
    data["note"] = "Simulation for research and education. Not medical advice."
    return JSONResponse(
        data,
        headers={"Content-Disposition": f'attachment; filename="experiment-{experiment_id}.json"'},
    )

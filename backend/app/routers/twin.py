import importlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from .. import functions
from ..deps import require_role
from ..schemas import PersonalTwinRequest, PredictRequest, Sex

router = APIRouter(prefix="/twin", tags=["twin"])


class TimelineRequest(BaseModel):
    """Time machine: the same lifestyle, aged from start_age to end_age."""

    sex: Sex
    sleep: float = Field(ge=0, le=24)
    exercise: float = Field(ge=0, le=7)
    smoking: float = Field(ge=0, le=100)
    diet: float = Field(ge=1, le=5)
    start_age: int = Field(default=20, ge=18, le=100)
    end_age: int = Field(default=80, ge=18, le=100)
    step: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def _check_order(self):
        if self.end_age < self.start_age:
            raise ValueError("end_age must not be smaller than start_age.")
        return self


class CompareRequest(BaseModel):
    """Twin versus twin: two lifestyle profiles side by side."""

    profile_a: PredictRequest
    profile_b: PredictRequest
    name_a: str = Field(default="Twin A", max_length=40)
    name_b: str = Field(default="Twin B", max_length=40)


def _load(module: str, attr: str):
    try:
        return getattr(importlib.import_module(module), attr)
    except Exception as err:  # the ml code could not be imported (missing package, etc.)
        raise HTTPException(status_code=503, detail=f"{attr} is not available right now: {err}")


@router.post("/predict")
def predict(body: PredictRequest):
    """Public. Vitals and a 0 to 100 score for each of the 12 organ ids."""
    return functions.predict_health(**body.model_dump())


@router.post("/timeline")
def timeline(body: TimelineRequest):
    """Public. Organ scores and vitals for each age step (the time machine)."""
    age_progression = _load("ml.age_progression", "age_progression")
    try:
        return age_progression(
            body.sex, body.sleep, body.exercise, body.smoking, body.diet,
            body.start_age, body.end_age, body.step,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/compare")
def compare(body: CompareRequest):
    """Public. Two profiles compared organ by organ (twin versus twin)."""
    compare_twins = _load("ml.twin_comparison", "compare_twins")
    try:
        return compare_twins(
            body.profile_a.model_dump(), body.profile_b.model_dump(), body.name_a, body.name_b
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/personal")
def personal(body: PersonalTwinRequest, user=Depends(require_role("pro"))):
    """Pro. Organ ids with score and vitals, plus a `morph` key for the viewer.
    Dummy: only the measurements path exists; scan upload comes later."""
    vitals = functions.predict_health(
        body.age, body.sex, body.sleep, body.exercise, body.smoking, body.diet
    )
    reference_height = 176.0 if body.sex == "male" else 163.0
    bmi = body.weight_kg / ((body.height_cm / 100.0) ** 2)
    vitals["morph"] = {
        "height_scale": round(body.height_cm / reference_height, 3),
        "weight_scale": round(bmi / 23.0, 3),
        "bmi": round(bmi, 1),
        "measurements": body.measurements,
    }
    return vitals

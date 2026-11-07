from fastapi import APIRouter, Depends

from .. import dummy
from ..deps import require_role
from ..schemas import PersonalTwinRequest, PredictRequest

router = APIRouter(prefix="/twin", tags=["twin"])


@router.post("/predict")
def predict(body: PredictRequest):
    """Public. Vitals and a 0 to 100 score for each of the 12 organ ids."""
    return dummy.predict_health(**body.model_dump())


@router.post("/personal")
def personal(body: PersonalTwinRequest, user=Depends(require_role("pro"))):
    """Pro. Organ ids with score and vitals, plus a `morph` key for the viewer.
    Dummy: only the measurements path exists; scan upload comes later."""
    vitals = dummy.predict_health(
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

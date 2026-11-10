"""Request and response shapes. They follow backend/api-contract.md exactly."""
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Sex = Literal["male", "female"]


class RegisterRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class PredictRequest(BaseModel):
    age: int = Field(ge=20, le=80)
    sex: Sex
    sleep: float = Field(ge=0, le=24, description="hours per night")
    exercise: int = Field(ge=0, le=7, description="days per week")
    smoking: int = Field(ge=0, le=100, description="cigarettes per day")
    diet: int = Field(ge=1, le=5)


class SimulateRequest(BaseModel):
    pathogen_id: str
    day: int = Field(ge=0, le=30)
    treatment: float = Field(ge=0, le=1)
    treatment_start: int = 0
    profile: Optional[dict] = None


class PersonalTwinRequest(BaseModel):
    age: int = Field(ge=20, le=80)
    sex: Sex
    height_cm: float = Field(ge=100, le=230)
    weight_kg: float = Field(ge=30, le=250)
    measurements: Dict[str, float] = Field(default_factory=dict)
    # Optional lifestyle inputs so the same vitals model can be used.
    sleep: float = Field(default=7, ge=0, le=24)
    exercise: int = Field(default=3, ge=0, le=7)
    smoking: int = Field(default=0, ge=0, le=100)
    diet: int = Field(default=3, ge=1, le=5)


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    pathogen_id: Optional[str] = Field(default=None, max_length=100)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    seed: Optional[int] = Field(default=None, ge=0, le=2_147_483_647)
    fork_of: Optional[int] = None


class ExperimentFork(BaseModel):
    """Everything is optional: a fork copies the original unless you override it."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    parameters: Optional[Dict[str, Any]] = None
    seed: Optional[int] = Field(default=None, ge=0, le=2_147_483_647)

from fastapi import APIRouter

from .. import functions
from ..schemas import Sex

router = APIRouter(prefix="/body", tags=["body"])


@router.get("/{sex}")
def get_body(sex: Sex):
    """Avatar file list and organ list for the viewer."""
    return functions.get_body(sex)

from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import config, dummy
from ..deps import get_optional_user, is_pro

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/sources")
def sources(
    limit: Optional[int] = Query(None, ge=1, le=100),
    user=Depends(get_optional_user),
):
    """Public: latest 5 papers. Pro: the full list."""
    if is_pro(user):
        count = limit or 100
    else:
        count = min(limit or config.PUBLIC_SOURCES_LIMIT, config.PUBLIC_SOURCES_LIMIT)
    return dummy.get_sources(count)

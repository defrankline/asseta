from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from asseta.core.clock import get_now, get_today
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.modules.identity.dependencies import get_claims
from asseta.modules.identity.dto import MeDto
from asseta.modules.identity.principal import TokenClaims
from asseta.modules.identity.service import IdentityService

router = APIRouter(prefix="/api/v1", tags=["identity"], responses=ERROR_RESPONSES)


@router.get("/me", response_model=MeDto, operation_id="getMe")
def get_me(
    claims: Annotated[TokenClaims, Depends(get_claims)],
    session: Annotated[Session, Depends(get_session)],
    today: Annotated[date, Depends(get_today)],
    now: Annotated[datetime, Depends(get_now)],
) -> MeDto:
    """Authenticated user's effective platform and tenant access (from Keycloak groups + synced mirror)."""
    return IdentityService(session).me(claims, today, now)

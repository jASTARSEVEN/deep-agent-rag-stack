"""Area 授權檢查路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.auth.verifier import CurrentPrincipal
from app.db.session import get_database_session
from app.schemas.access import AreaAccessResponse
from app.services.access import require_area_access


# Area 相關最小授權路由集合。
router = APIRouter(prefix="/areas", tags=["areas"])


@router.get("/{area_id}/access-check", response_model=AreaAccessResponse)
def read_area_access_check(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaAccessResponse:
    """檢查目前使用者是否對指定 area 擁有有效角色。"""

    effective_role = require_area_access(session=session, principal=principal, area_id=area_id)
    return AreaAccessResponse(area_id=area_id, effective_role=effective_role)

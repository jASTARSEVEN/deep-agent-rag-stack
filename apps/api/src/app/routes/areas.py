"""Knowledge Area 與 access management 路由。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.auth.verifier import CurrentPrincipal
from app.db.session import get_database_session
from app.schemas.access import AreaAccessResponse
from app.schemas.areas import (
    AreaAccessManagementResponse,
    AreaListResponse,
    AreaSummaryResponse,
    CreateAreaRequest,
    ReplaceAreaAccessRequest,
)
from app.services.access import require_area_access
from app.services.areas import (
    create_area,
    get_area_access_management,
    get_area_detail,
    list_accessible_areas,
    replace_area_access_management,
)


# Area 相關最小授權路由集合。
router = APIRouter(prefix="/areas", tags=["areas"])


@router.post("", response_model=AreaSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_area_route(
    payload: CreateAreaRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaSummaryResponse:
    """建立新的 Knowledge Area。"""

    return create_area(
        session=session,
        principal=principal,
        name=payload.name,
        description=payload.description,
    )


@router.get("", response_model=AreaListResponse)
def list_areas_route(
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaListResponse:
    """列出目前使用者可存取的 areas。"""

    return AreaListResponse(items=list_accessible_areas(session=session, principal=principal))


@router.get("/{area_id}", response_model=AreaSummaryResponse)
def read_area_route(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaSummaryResponse:
    """讀取單一 area 詳細資料。"""

    return get_area_detail(session=session, principal=principal, area_id=area_id)


@router.get("/{area_id}/access-check", response_model=AreaAccessResponse)
def read_area_access_check(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaAccessResponse:
    """檢查目前使用者是否對指定 area 擁有有效角色。"""

    effective_role = require_area_access(session=session, principal=principal, area_id=area_id)
    return AreaAccessResponse(area_id=area_id, effective_role=effective_role)


@router.get("/{area_id}/access", response_model=AreaAccessManagementResponse)
def read_area_access_route(
    area_id: str,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaAccessManagementResponse:
    """讀取指定 area 的 access 管理資料。"""

    return get_area_access_management(session=session, principal=principal, area_id=area_id)


@router.put("/{area_id}/access", response_model=AreaAccessManagementResponse)
def replace_area_access_route(
    area_id: str,
    payload: ReplaceAreaAccessRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_database_session),
) -> AreaAccessManagementResponse:
    """整體替換指定 area 的 access 規則。"""

    return replace_area_access_management(
        session=session,
        principal=principal,
        area_id=area_id,
        payload=payload,
    )

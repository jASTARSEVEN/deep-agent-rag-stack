"""Area access 與 effective role 計算 service。"""

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.db.models import AreaGroupRole, AreaUserRole, Role


# 角色強度排序，數值越大代表權限越高。
ROLE_PRIORITY = {
    Role.reader: 1,
    Role.maintainer: 2,
    Role.admin: 3,
}


def resolve_highest_role(roles: Iterable[Role]) -> Role | None:
    """從多個角色中取出權限最大的角色。"""

    resolved_roles = list(roles)
    if not resolved_roles:
        return None
    return max(resolved_roles, key=lambda role: ROLE_PRIORITY[role])


def resolve_effective_role_for_area(
    session: Session,
    principal: CurrentPrincipal,
    area_id: str,
) -> Role | None:
    """計算使用者在指定 area 的 effective role。

    前置條件：
    - `principal` 必須已完成 JWT 驗證。
    - 所有 access 資料都必須透過 SQL 查詢取得，不可先取全量再在記憶體過濾。

    風險：
    - 若將授權查詢移到 route handler 或前端，會破壞 deny-by-default 與資訊洩漏保護。
    """

    user_roles = session.scalars(
        select(AreaUserRole.role).where(AreaUserRole.area_id == area_id, AreaUserRole.user_sub == principal.sub)
    ).all()
    group_roles = session.scalars(
        select(AreaGroupRole.role).where(
            AreaGroupRole.area_id == area_id,
            AreaGroupRole.group_path.in_(principal.groups or ("__no_groups__",)),
        )
    ).all()
    return resolve_highest_role([*user_roles, *group_roles])


def require_area_access(session: Session, principal: CurrentPrincipal, area_id: str) -> Role:
    """要求使用者必須對 area 具有有效角色，否則回傳不暴露存在性的 404。"""

    effective_role = resolve_effective_role_for_area(session=session, principal=principal, area_id=area_id)
    if effective_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的 area。")
    return effective_role

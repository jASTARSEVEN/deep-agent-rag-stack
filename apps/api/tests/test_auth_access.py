"""授權與 access-check API 測試。"""

from app.auth.verifier import CurrentPrincipal
from app.auth.verifier import InvalidTokenError
from app.auth.verifier import _build_principal_from_payload
from app.db.models import Area, AreaGroupRole, AreaUserRole, Role
from app.services.access import resolve_effective_role_for_area, resolve_highest_role


# 測試模式使用的 Bearer token，格式由 TestModeTokenVerifier 定義。
READER_TOKEN = "Bearer test::user-reader::/group/reader"


def test_resolve_highest_role_prefers_stronger_role() -> None:
    """應回傳權限最高的角色。"""

    assert resolve_highest_role([Role.reader, Role.admin, Role.maintainer]) == Role.admin


def test_resolve_highest_role_returns_none_when_empty() -> None:
    """沒有角色時應回傳 None。"""

    assert resolve_highest_role([]) is None


def test_effective_role_uses_direct_role(db_session) -> None:
    """只有 direct role 時應正確回傳。"""

    area = Area(id="area-direct", name="Direct Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-direct", role=Role.maintainer))
    db_session.commit()

    principal = CurrentPrincipal(sub="user-direct", groups=tuple())
    assert resolve_effective_role_for_area(db_session, principal, area.id) == Role.maintainer


def test_effective_role_uses_group_role(db_session) -> None:
    """只有 group role 時應正確回傳。"""

    area = Area(id="area-group", name="Group Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    principal = CurrentPrincipal(sub="user-group", groups=("/group/reader",))
    assert resolve_effective_role_for_area(db_session, principal, area.id) == Role.reader


def test_effective_role_uses_maximum_of_direct_and_group_roles(db_session) -> None:
    """direct 與 group 同時存在時應取最大值。"""

    area = Area(id="area-max", name="Max Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-max", role=Role.reader))
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/admin", role=Role.admin))
    db_session.commit()

    principal = CurrentPrincipal(sub="user-max", groups=("/group/admin",))
    assert resolve_effective_role_for_area(db_session, principal, area.id) == Role.admin


def test_claim_parser_treats_missing_groups_as_empty_tuple() -> None:
    """缺少 groups claim 時應視為空集合。"""

    principal = _build_principal_from_payload(payload={"sub": "user-no-groups"}, groups_claim="groups")
    assert principal == CurrentPrincipal(sub="user-no-groups", groups=tuple())


def test_claim_parser_rejects_invalid_groups_shape() -> None:
    """groups claim 不是字串陣列時應拒絕。"""

    try:
        _build_principal_from_payload(payload={"sub": "user-bad-groups", "groups": "not-a-list"}, groups_claim="groups")
    except InvalidTokenError:
        pass
    else:
        raise AssertionError("預期應拒絕非法的 groups claim 格式。")


def test_auth_context_requires_valid_bearer_token(client) -> None:
    """沒有 Bearer token 時應回 401。"""

    response = client.get("/auth/context")
    assert response.status_code == 401


def test_auth_context_returns_principal(client) -> None:
    """測試模式 token 應可回傳 principal。"""

    response = client.get("/auth/context", headers={"Authorization": "Bearer test::user-1::/group/a,/group/b"})

    assert response.status_code == 200
    assert response.json() == {
        "sub": "user-1",
        "groups": ["/group/a", "/group/b"],
        "authenticated": True,
    }


def test_auth_context_rejects_invalid_groups_claim_shape(client) -> None:
    """格式錯誤的測試 token 應被視為無效。"""

    response = client.get("/auth/context", headers={"Authorization": "Bearer malformed-token"})
    assert response.status_code == 401


def test_access_check_returns_effective_role_for_authorized_user(client, db_session) -> None:
    """已授權使用者應取得 effective role。"""

    area = Area(id="area-access", name="Access Area")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/reader", role=Role.reader))
    db_session.commit()

    response = client.get(
        f"/areas/{area.id}/access-check",
        headers={"Authorization": READER_TOKEN},
    )

    assert response.status_code == 200
    assert response.json() == {"area_id": area.id, "effective_role": "reader"}


def test_access_check_returns_404_for_unauthorized_area(client, db_session) -> None:
    """沒有有效角色時應以 404 隱藏 area。"""

    area = Area(id="area-hidden", name="Hidden Area")
    db_session.add(area)
    db_session.commit()

    response = client.get(
        f"/areas/{area.id}/access-check",
        headers={"Authorization": READER_TOKEN},
    )

    assert response.status_code == 404


def test_access_check_returns_same_404_for_missing_area(client) -> None:
    """不存在的 area 也應回相同 404，避免資訊洩漏。"""

    response = client.get(
        "/areas/missing-area/access-check",
        headers={"Authorization": READER_TOKEN},
    )

    assert response.status_code == 404

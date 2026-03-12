"""Knowledge Area CRUD 與 access management API 測試。"""

from app.db.models import Area, AreaGroupRole, AreaUserRole, Role


# 管理者測試 token。
ADMIN_TOKEN = "Bearer test::user-admin::/group/admin"

# 維護者測試 token。
MAINTAINER_TOKEN = "Bearer test::user-maintainer::/group/maintainer"

# 無授權測試 token。
OUTSIDER_TOKEN = "Bearer test::user-outsider::/group/outsider"


def test_create_area_assigns_creator_as_admin(client, db_session) -> None:
    """建立 area 後，建立者應自動成為 admin。"""

    response = client.post(
        "/areas",
        headers={"Authorization": ADMIN_TOKEN},
        json={"name": "  平台文件區  ", "description": "  MVP area  "},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "平台文件區"
    assert payload["description"] == "MVP area"
    assert payload["effective_role"] == "admin"

    area_role = db_session.query(AreaUserRole).filter(AreaUserRole.area_id == payload["id"]).one()
    assert area_role.user_sub == "user-admin"
    assert area_role.role == Role.admin


def test_list_areas_returns_only_accessible_areas_with_highest_role(client, db_session) -> None:
    """area list 只應回傳有權限的 area，且 role 應取最大值。"""

    accessible_area = Area(id="area-visible", name="Visible Area")
    stronger_area = Area(id="area-strong", name="Strong Area")
    hidden_area = Area(id="area-hidden", name="Hidden Area")
    db_session.add_all([accessible_area, stronger_area, hidden_area])
    db_session.add_all(
        [
            AreaGroupRole(area_id=accessible_area.id, group_path="/group/admin", role=Role.reader),
            AreaUserRole(area_id=stronger_area.id, user_sub="user-admin", role=Role.reader),
            AreaGroupRole(area_id=stronger_area.id, group_path="/group/admin", role=Role.admin),
            AreaGroupRole(area_id=hidden_area.id, group_path="/group/other", role=Role.reader),
        ]
    )
    db_session.commit()

    response = client.get("/areas", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == ["area-strong", "area-visible"]
    assert payload["items"][0]["effective_role"] == "admin"
    assert payload["items"][1]["effective_role"] == "reader"


def test_read_area_returns_404_for_unauthorized_and_missing_area(client, db_session) -> None:
    """未授權與不存在的 area 都應回相同 404。"""

    area = Area(id="area-secret", name="Secret Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/areas/{area.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/areas/missing-area", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_read_area_returns_detail_for_authorized_user(client, db_session) -> None:
    """有權限的使用者應可讀取 area 詳細資料。"""

    area = Area(id="area-detail", name="Detail Area", description="Area Description")
    db_session.add(area)
    db_session.add(AreaGroupRole(area_id=area.id, group_path="/group/admin", role=Role.maintainer))
    db_session.commit()

    response = client.get(f"/areas/{area.id}", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 200
    assert response.json()["effective_role"] == "maintainer"
    assert response.json()["description"] == "Area Description"


def test_get_area_access_requires_admin_role(client, db_session) -> None:
    """maintainer 不可讀取 area access 管理內容。"""

    area = Area(id="area-access", name="Access Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.get(f"/areas/{area.id}/access", headers={"Authorization": MAINTAINER_TOKEN})

    assert response.status_code == 403


def test_get_area_access_returns_same_404_for_unauthorized_and_missing_area(client, db_session) -> None:
    """未授權與不存在的 access API 都應回相同 404。"""

    area = Area(id="area-hidden-access", name="Hidden Access Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/areas/{area.id}/access", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/areas/missing-area/access", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_get_area_access_returns_users_and_groups_for_admin(client, db_session) -> None:
    """admin 應可讀取完整 access 規則。"""

    area = Area(id="area-admin-access", name="Admin Access Area")
    db_session.add(area)
    db_session.add_all(
        [
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            AreaGroupRole(area_id=area.id, group_path="/group/editor", role=Role.maintainer),
        ]
    )
    db_session.commit()

    response = client.get(f"/areas/{area.id}/access", headers={"Authorization": ADMIN_TOKEN})

    assert response.status_code == 200
    assert response.json() == {
        "area_id": area.id,
        "users": [
            {"user_sub": "user-admin", "role": "admin"},
            {"user_sub": "user-reader", "role": "reader"},
        ],
        "groups": [{"group_path": "/group/editor", "role": "maintainer"}],
    }


def test_replace_area_access_requires_admin_role(client, db_session) -> None:
    """maintainer 不可更新 area access。"""

    area = Area(id="area-maintainer-update", name="Maintainer Update Area")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.put(
        f"/areas/{area.id}/access",
        headers={"Authorization": MAINTAINER_TOKEN},
        json={"users": [{"user_sub": "user-maintainer", "role": "admin"}], "groups": []},
    )

    assert response.status_code == 403


def test_replace_area_access_replaces_existing_rules_for_admin(client, db_session) -> None:
    """admin 應可整體替換 area access 規則。"""

    area = Area(id="area-replace", name="Replace Area")
    db_session.add(area)
    db_session.add_all(
        [
            AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin),
            AreaUserRole(area_id=area.id, user_sub="user-legacy", role=Role.reader),
            AreaGroupRole(area_id=area.id, group_path="/group/legacy", role=Role.reader),
        ]
    )
    db_session.commit()

    response = client.put(
        f"/areas/{area.id}/access",
        headers={"Authorization": ADMIN_TOKEN},
        json={
            "users": [
                {"user_sub": "user-admin", "role": "admin"},
                {"user_sub": "user-next", "role": "maintainer"},
            ],
            "groups": [{"group_path": "/group/new", "role": "reader"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "area_id": area.id,
        "users": [
            {"user_sub": "user-admin", "role": "admin"},
            {"user_sub": "user-next", "role": "maintainer"},
        ],
        "groups": [{"group_path": "/group/new", "role": "reader"}],
    }

    stored_user_roles = db_session.query(AreaUserRole).filter(AreaUserRole.area_id == area.id).all()
    stored_group_roles = db_session.query(AreaGroupRole).filter(AreaGroupRole.area_id == area.id).all()
    assert {(item.user_sub, item.role.value) for item in stored_user_roles} == {
        ("user-admin", "admin"),
        ("user-next", "maintainer"),
    }
    assert {(item.group_path, item.role.value) for item in stored_group_roles} == {("/group/new", "reader")}

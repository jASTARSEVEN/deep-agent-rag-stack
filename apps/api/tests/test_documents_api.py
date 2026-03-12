"""Documents 與 ingest jobs API 測試。"""

from pathlib import Path

from app.db.models import Area, AreaUserRole, Document, DocumentStatus, IngestJob, IngestJobStatus, Role


# 管理者測試 token。
ADMIN_TOKEN = "Bearer test::user-admin::/group/admin"

# 維護者測試 token。
MAINTAINER_TOKEN = "Bearer test::user-maintainer::/group/maintainer"

# 讀者測試 token。
READER_TOKEN = "Bearer test::user-reader::/group/reader"

# 無授權測試 token。
OUTSIDER_TOKEN = "Bearer test::user-outsider::/group/outsider"


def test_upload_document_creates_document_job_and_inline_ready(client, db_session, app_settings) -> None:
    """maintainer 上傳 md 後應建立 document/job，並在 inline ingest 下轉為 ready。"""

    area = Area(id="area-maintainer-docs", name="Maintainer Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-maintainer", role=Role.maintainer))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": MAINTAINER_TOKEN},
        files={"file": ("notes.md", b"# Title\ncontent\n", "text/markdown")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["file_name"] == "notes.md"
    assert payload["document"]["status"] == "ready"
    assert payload["job"]["status"] == "succeeded"

    stored_document = db_session.get(Document, payload["document"]["id"])
    stored_job = db_session.get(IngestJob, payload["job"]["id"])
    assert stored_document is not None
    assert stored_document.status == DocumentStatus.ready
    assert stored_document.file_size == len(b"# Title\ncontent\n")
    assert stored_job is not None
    assert stored_job.status == IngestJobStatus.succeeded
    assert (Path(app_settings.local_storage_path) / stored_document.storage_key).exists()


def test_upload_document_rejects_reader(client, db_session) -> None:
    """reader 不可上傳文件。"""

    area = Area(id="area-reader-docs", name="Reader Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": READER_TOKEN},
        files={"file": ("notes.md", b"content", "text/markdown")},
    )

    assert response.status_code == 403


def test_upload_document_returns_same_404_for_unauthorized_and_missing_area(client, db_session) -> None:
    """outsider 對既有與不存在 area 上傳都應回相同 404。"""

    area = Area(id="area-secret-docs", name="Secret Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": OUTSIDER_TOKEN},
        files={"file": ("notes.md", b"content", "text/markdown")},
    )
    missing_response = client.post(
        "/areas/missing-area/documents",
        headers={"Authorization": OUTSIDER_TOKEN},
        files={"file": ("notes.md", b"content", "text/markdown")},
    )

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_upload_document_rejects_empty_file(client, db_session) -> None:
    """空檔案應被 upload validator 擋下。"""

    area = Area(id="area-empty-docs", name="Empty Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("empty.md", b"", "text/markdown")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "上傳檔案不可為空。"


def test_upload_document_rejects_oversized_file(client, db_session) -> None:
    """超過大小限制的檔案應被拒絕。"""

    area = Area(id="area-large-docs", name="Large Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("large.md", b"x" * 2048, "text/markdown")},
    )

    assert response.status_code == 413


def test_upload_document_rejects_unknown_extension(client, db_session) -> None:
    """未知副檔名應在 API 驗證階段被拒絕。"""

    area = Area(id="area-unknown-docs", name="Unknown Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("archive.zip", b"fake", "application/zip")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "目前不支援此檔案類型。"


def test_upload_document_marks_unimplemented_supported_type_as_failed(client, db_session) -> None:
    """產品範圍內但本 phase 未支援的副檔名應進入 failed。"""

    area = Area(id="area-pdf-docs", name="PDF Docs")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    response = client.post(
        f"/areas/{area.id}/documents",
        headers={"Authorization": ADMIN_TOKEN},
        files={"file": ("deck.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "failed"
    assert payload["job"]["status"] == "failed"
    assert payload["job"]["error_message"] == "目前尚未支援此檔案類型的解析。"


def test_list_documents_returns_only_area_documents(client, db_session) -> None:
    """area 文件列表只應回傳指定 area 內的文件。"""

    visible_area = Area(id="area-doc-visible", name="Visible")
    hidden_area = Area(id="area-doc-hidden", name="Hidden")
    db_session.add_all([visible_area, hidden_area])
    db_session.add_all(
        [
            AreaUserRole(area_id=visible_area.id, user_sub="user-reader", role=Role.reader),
            AreaUserRole(area_id=hidden_area.id, user_sub="user-admin", role=Role.admin),
            Document(
                id="document-visible",
                area_id=visible_area.id,
                file_name="visible.md",
                content_type="text/markdown",
                file_size=10,
                storage_key="visible",
                status=DocumentStatus.ready,
            ),
            Document(
                id="document-hidden",
                area_id=hidden_area.id,
                file_name="hidden.md",
                content_type="text/markdown",
                file_size=12,
                storage_key="hidden",
                status=DocumentStatus.ready,
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/areas/{visible_area.id}/documents", headers={"Authorization": READER_TOKEN})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["document-visible"]


def test_document_detail_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 document 都應回相同 404。"""

    area = Area(id="area-document-secret", name="Secret")
    document = Document(
        id="document-secret",
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    db_session.add(area)
    db_session.add(document)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/documents/{document.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/documents/missing-document", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()


def test_ingest_job_detail_returns_same_404_for_unauthorized_and_missing(client, db_session) -> None:
    """未授權與不存在的 ingest job 都應回相同 404。"""

    area = Area(id="area-job-secret", name="Secret Job")
    document = Document(
        id="document-job-secret",
        area_id=area.id,
        file_name="secret.md",
        content_type="text/markdown",
        file_size=9,
        storage_key="secret",
        status=DocumentStatus.ready,
    )
    job = IngestJob(id="job-secret", document_id=document.id, status=IngestJobStatus.succeeded)
    db_session.add_all([area, document, job])
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    unauthorized_response = client.get(f"/ingest-jobs/{job.id}", headers={"Authorization": OUTSIDER_TOKEN})
    missing_response = client.get("/ingest-jobs/missing-job", headers={"Authorization": OUTSIDER_TOKEN})

    assert unauthorized_response.status_code == 404
    assert missing_response.status_code == 404
    assert unauthorized_response.json() == missing_response.json()

"""外部 benchmark curation pipeline 測試。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.db.models import Area, Document, DocumentStatus
from app.scripts.import_benchmark_snapshot import import_snapshot
from app.scripts.prepare_external_benchmark import (
    ALIGNMENT_CANDIDATES_FILE,
    ALIGNMENT_REVIEW_QUEUE_FILE,
    FILTER_REPORT_FILE,
    OPTIONAL_SNAPSHOT_AUXILIARY_FILES,
    PREPARED_DOCUMENTS_FILE,
    PREPARED_ITEMS_FILE,
    REVIEW_OVERRIDES_FILE,
    build_report,
    build_snapshot,
    filter_items,
    prepare_source,
    align_spans,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def test_prepare_qasper_source_and_filter(tmp_path: Path) -> None:
    """QASPER prepare/filter 應只保留 extractive fact lookup 題目。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出。
    """

    workspace_dir = tmp_path / "qasper-workspace"
    input_path = tmp_path / "qasper.json"
    input_path.write_text(
        json.dumps(
            {
                "paper-1": {
                    "paper_id": "paper-1",
                    "title": "Paper One",
                    "abstract": "A short abstract.",
                    "full_text": [
                        {"section_name": "Introduction", "paragraphs": ["Alpha evidence sentence."]},
                    ],
                    "qas": [
                        {
                            "question": "What sentence is important?",
                            "answers": [
                                {
                                    "answer": {
                                        "extractive_spans": ["Alpha evidence sentence."],
                                        "free_form_answer": "Alpha evidence sentence.",
                                        "unanswerable": False,
                                    }
                                }
                            ],
                        },
                        {
                            "question": "Is the result good?",
                            "answers": [
                                {
                                    "answer": {
                                        "yes_no": True,
                                        "free_form_answer": "yes",
                                        "unanswerable": False,
                                    }
                                }
                            ],
                        },
                    ],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    prepare_summary = prepare_source(
        dataset="qasper",
        input_path=input_path,
        workspace_dir=workspace_dir,
        limit_documents=None,
        limit_items=None,
    )
    assert prepare_summary["document_count"] == 1
    assert prepare_summary["item_count"] == 2

    filter_summary = filter_items(workspace_dir=workspace_dir)
    assert filter_summary["kept_item_count"] == 1
    filtered_rows = [
        json.loads(line)
        for line in (workspace_dir / "filtered_items.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert filtered_rows[0]["query_text"] == "What sentence is important?"


def test_align_build_snapshot_and_import_round_trip(app, db_session, app_settings, tmp_path: Path, monkeypatch) -> None:
    """alignment/build-snapshot 應可產出現有 import snapshot 可接受的 package。

    參數：
    - `app`：測試用 FastAPI app。
    - `db_session`：測試資料庫 session。
    - `app_settings`：測試設定。
    - `tmp_path`：pytest 暫存目錄。
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 pipeline 正常。
    """

    area = Area(id=_uuid(), name="Benchmark Area")
    import_area = Area(id=_uuid(), name="Import Area")
    db_session.add_all([area, import_area])

    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="paper-1.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="benchmark/paper-1.md",
        display_text="Alpha unique evidence sentence.\n\nAlpha review sentence.\n\nAlpha review sentence.\n\nUnique fuzzy evidence text.",
        normalized_text="Alpha unique evidence sentence.\n\nAlpha review sentence.\n\nAlpha review sentence.\n\nUnique fuzzy evidence text.",
        status=DocumentStatus.ready,
    )
    import_document = Document(
        id=_uuid(),
        area_id=import_area.id,
        file_name="paper-1.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="benchmark/import-paper-1.md",
        display_text=document.display_text,
        normalized_text=document.normalized_text,
        status=DocumentStatus.ready,
    )
    db_session.add_all([document, import_document])
    db_session.commit()

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    source_dir = workspace_dir / "source_documents"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "paper-1.md"
    source_file.write_text(document.display_text or "", encoding="utf-8")

    (workspace_dir / PREPARED_DOCUMENTS_FILE).write_text(
        json.dumps(
            {
                "dataset": "qasper",
                "source_document_id": "paper-1",
                "file_name": "paper-1.md",
                "title": "Paper One",
                "source_path": str(source_file),
                "content_type": "text/markdown",
                "created_at": "2026-04-02T00:00:00+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    prepared_rows = [
        {
            "item_id": "item-exact",
            "dataset": "qasper",
            "source_document_id": "paper-1",
            "file_name": "paper-1.md",
            "query_text": "What is the alpha evidence?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Alpha unique evidence sentence.",
            "evidence_texts": ["Alpha unique evidence sentence."],
            "answer_type": "extractive",
            "source_question_index": 0,
            "source_metadata": {"paper_id": "paper-1"},
            "created_at": "2026-04-02T00:00:00+00:00",
        },
        {
            "item_id": "item-fuzzy",
            "dataset": "qasper",
            "source_document_id": "paper-1",
            "file_name": "paper-1.md",
            "query_text": "What is the unique fuzzy evidence?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Unique fuzzy evidence text.",
            "evidence_texts": ["Unique fuzzy evidence tex"],
            "answer_type": "extractive",
            "source_question_index": 1,
            "source_metadata": {"paper_id": "paper-1"},
            "created_at": "2026-04-02T00:00:00+00:00",
        },
        {
            "item_id": "item-review",
            "dataset": "qasper",
            "source_document_id": "paper-1",
            "file_name": "paper-1.md",
            "query_text": "Which alpha mention is near the duplicate context?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Alpha review sentence.",
            "evidence_texts": ["Alpha review sentence."],
            "answer_type": "extractive",
            "source_question_index": 2,
            "source_metadata": {"paper_id": "paper-1"},
            "created_at": "2026-04-02T00:00:00+00:00",
        },
    ]
    (workspace_dir / PREPARED_ITEMS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_rows) + "\n",
        encoding="utf-8",
    )

    filter_summary = filter_items(workspace_dir=workspace_dir)
    assert filter_summary["kept_item_count"] == 3

    monkeypatch.setattr("app.scripts.prepare_external_benchmark.get_settings", lambda: app_settings)
    monkeypatch.setattr("app.scripts.import_benchmark_snapshot.get_settings", lambda: app_settings)
    align_summary = align_spans(workspace_dir=workspace_dir, area_id=area.id)
    assert align_summary["status_counts"]["auto_matched"] == 2
    assert align_summary["status_counts"]["needs_review"] == 1

    review_overrides = [
        {
            "item_id": "item-review",
            "decision": "approved",
            "spans": [
                {
                    "start_offset": len("Alpha unique evidence sentence.\n\n"),
                    "end_offset": len("Alpha unique evidence sentence.\n\n") + len("Alpha review sentence."),
                }
            ],
        }
    ]
    (workspace_dir / REVIEW_OVERRIDES_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in review_overrides) + "\n",
        encoding="utf-8",
    )

    snapshot_dir = tmp_path / "snapshot"
    snapshot_summary = build_snapshot(
        workspace_dir=workspace_dir,
        output_dir=snapshot_dir,
        benchmark_name="qasper-curated-v1",
        include_review_items=False,
    )
    assert snapshot_summary["question_count"] == 3
    assert snapshot_summary["question_with_gold_span_count"] == 3
    assert (snapshot_dir / "manifest.json").exists()
    assert (snapshot_dir / ALIGNMENT_CANDIDATES_FILE).exists()
    assert (snapshot_dir / ALIGNMENT_REVIEW_QUEUE_FILE).exists()
    assert (snapshot_dir / FILTER_REPORT_FILE).exists()

    import_summary = import_snapshot(
        snapshot_dir=snapshot_dir,
        area_id=import_area.id,
        dataset_name_override="qasper-curated-import",
        actor_sub="user-admin",
        replace=True,
    )
    assert import_summary["question_count"] == 3
    assert import_summary["span_count"] == 3

    report = build_report(workspace_dir=workspace_dir)
    assert report["approved_override_count"] == 1
    assert report["status_counts"]["needs_review"] == 1


def test_build_snapshot_can_include_reviewed_item_not_in_filtered_set(tmp_path: Path) -> None:
    """build_snapshot 應可納入僅存在 prepared_items 的 reviewed item。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證 snapshot 可正常建立。
    """

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    source_dir = workspace_dir / "source_documents"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "paper-2.md"
    source_file.write_text("Alpha answer evidence.", encoding="utf-8")

    prepared_documents = [
        {
            "dataset": "uda",
            "source_document_id": "paper-2",
            "file_name": "paper-2.md",
            "title": "Paper Two",
            "source_path": str(source_file),
            "content_type": "text/markdown",
            "created_at": "2026-04-04T00:00:00+00:00",
        }
    ]
    prepared_items = [
        {
            "item_id": "item-prepared-only",
            "dataset": "uda",
            "source_document_id": "paper-2",
            "file_name": "paper-2.md",
            "query_text": "What is the alpha answer?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Alpha answer evidence.",
            "evidence_texts": [],
            "answer_type": "short_answer",
            "source_question_index": 0,
            "source_metadata": {"row_index": 0},
            "created_at": "2026-04-04T00:00:00+00:00",
        }
    ]

    (workspace_dir / PREPARED_DOCUMENTS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_documents) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / PREPARED_ITEMS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_items) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "filtered_items.jsonl").write_text("", encoding="utf-8")
    (workspace_dir / ALIGNMENT_CANDIDATES_FILE).write_text(
        json.dumps(
            {
                "item_id": "item-prepared-only",
                "dataset": "uda",
                "file_name": "paper-2.md",
                "query_text": "What is the alpha answer?",
                "answer_text": "Alpha answer evidence.",
                "language": "en",
                "query_type": "fact_lookup",
                "status": "needs_review",
                "accepted_spans": [],
                "review_candidates": [],
                "rejected_evidences": [],
                "source_metadata": {"row_index": 0},
                "generated_at": "2026-04-04T00:00:00+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace_dir / REVIEW_OVERRIDES_FILE).write_text(
        json.dumps(
            {
                "item_id": "item-prepared-only",
                "decision": "approved",
                "spans": [{"start_offset": 0, "end_offset": len("Alpha answer evidence.")}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "snapshot"
    summary = build_snapshot(
        workspace_dir=workspace_dir,
        output_dir=output_dir,
        benchmark_name="prepared-only-reviewed",
        include_review_items=False,
    )

    assert summary["question_count"] == 1
    assert summary["span_count"] == 1
    questions = [
        json.loads(line)
        for line in (output_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert questions[0]["question"] == "What is the alpha answer?"


def test_build_snapshot_can_limit_question_count_and_copy_optional_review_files(tmp_path: Path) -> None:
    """build_snapshot 應可限制題數並複製可選 review 證據檔。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證 manifest 與輸出檔案正確。
    """

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    source_dir = workspace_dir / "source_documents"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "paper-3.md"
    source_file.write_text("Alpha one.\n\nBeta two.\n", encoding="utf-8")

    prepared_documents = [
        {
            "dataset": "qasper",
            "source_document_id": "paper-3",
            "file_name": "paper-3.md",
            "title": "Paper Three",
            "source_path": str(source_file),
            "content_type": "text/markdown",
            "created_at": "2026-04-04T00:00:00+00:00",
        }
    ]
    prepared_items = [
        {
            "item_id": "item-1",
            "dataset": "qasper",
            "source_document_id": "paper-3",
            "file_name": "paper-3.md",
            "query_text": "What is alpha?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Alpha one.",
            "evidence_texts": ["Alpha one."],
            "answer_type": "extractive",
            "source_question_index": 0,
            "source_metadata": {"paper_id": "paper-3"},
            "created_at": "2026-04-04T00:00:00+00:00",
        },
        {
            "item_id": "item-2",
            "dataset": "qasper",
            "source_document_id": "paper-3",
            "file_name": "paper-3.md",
            "query_text": "What is beta?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Beta two.",
            "evidence_texts": ["Beta two."],
            "answer_type": "extractive",
            "source_question_index": 1,
            "source_metadata": {"paper_id": "paper-3"},
            "created_at": "2026-04-04T00:00:00+00:00",
        },
    ]

    (workspace_dir / PREPARED_DOCUMENTS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_documents) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / PREPARED_ITEMS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_items) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "filtered_items.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_items) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / ALIGNMENT_CANDIDATES_FILE).write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "item_id": "item-1",
                        "dataset": "qasper",
                        "file_name": "paper-3.md",
                        "query_text": "What is alpha?",
                        "answer_text": "Alpha one.",
                        "language": "en",
                        "query_type": "fact_lookup",
                        "status": "auto_matched",
                        "accepted_spans": [{"start_offset": 0, "end_offset": len("Alpha one.")}],
                        "review_candidates": [],
                        "rejected_evidences": [],
                        "source_metadata": {"paper_id": "paper-3"},
                        "generated_at": "2026-04-04T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "item_id": "item-2",
                        "dataset": "qasper",
                        "file_name": "paper-3.md",
                        "query_text": "What is beta?",
                        "answer_text": "Beta two.",
                        "language": "en",
                        "query_type": "fact_lookup",
                        "status": "needs_review",
                        "accepted_spans": [],
                        "review_candidates": [],
                        "rejected_evidences": [],
                        "source_metadata": {"paper_id": "paper-3"},
                        "generated_at": "2026-04-04T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace_dir / ALIGNMENT_REVIEW_QUEUE_FILE).write_text(
        json.dumps({"item_id": "item-2"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / FILTER_REPORT_FILE).write_text(
        json.dumps({"kept_item_count": 2}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / REVIEW_OVERRIDES_FILE).write_text(
        json.dumps(
            {
                "item_id": "item-2",
                "decision": "approved",
                "spans": [{"start_offset": len("Alpha one.\n\n"), "end_offset": len("Alpha one.\n\nBeta two.")}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    openai_log_file = workspace_dir / OPTIONAL_SNAPSHOT_AUXILIARY_FILES[1]
    openai_log_file.write_text(
        json.dumps({"item_id": "item-2", "decision": "approved"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "snapshot"
    summary = build_snapshot(
        workspace_dir=workspace_dir,
        output_dir=output_dir,
        benchmark_name="limited-reviewed",
        include_review_items=False,
        target_question_count=1,
        reference_evaluation_profile="qasper_guarded_query_focus_v1",
    )

    assert summary["question_count"] == 1
    assert summary["reference_evaluation_profile"] == "qasper_guarded_query_focus_v1"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reference"]["evaluation_profile"] == "qasper_guarded_query_focus_v1"
    assert manifest["stats"]["question_count"] == 1
    assert REVIEW_OVERRIDES_FILE in manifest["snapshot_files"]
    assert OPTIONAL_SNAPSHOT_AUXILIARY_FILES[1] in manifest["snapshot_files"]
    assert (output_dir / REVIEW_OVERRIDES_FILE).exists()
    assert (output_dir / OPTIONAL_SNAPSHOT_AUXILIARY_FILES[1]).exists()

"""API 設定物件測試。"""

from app.core.settings import AppSettings


def test_app_settings_uses_defaults_for_empty_string_env_values(monkeypatch) -> None:
    """空字串環境變數應回退為 API 設定預設值。"""

    monkeypatch.delenv("RERANK_PROVIDER", raising=False)
    monkeypatch.delenv("RERANK_MODEL", raising=False)

    settings = AppSettings(
        _env_file=None,
        MINIO_SECURE="",
        MAX_UPLOAD_SIZE_BYTES="",
        CHUNK_MIN_PARENT_SECTION_LENGTH="",
        CHUNK_TARGET_CHILD_SIZE="",
        CHUNK_CHILD_OVERLAP="",
        CHUNK_CONTENT_PREVIEW_LENGTH="",
        CHUNK_TXT_PARENT_GROUP_SIZE="",
        CHUNK_TABLE_PRESERVE_MAX_CHARS="",
        CHUNK_TABLE_MAX_ROWS_PER_CHILD="",
        RETRIEVAL_EVIDENCE_SYNOPSIS_ENABLED="",
        RETRIEVAL_EVIDENCE_SYNOPSIS_VARIANT="",
        EASYPINEX_HOST_RERANK_BASE_URL="",
        EASYPINEX_HOST_RERANK_API_KEY="",
        EASYPINEX_HOST_RERANK_TIMEOUT_SECONDS="",
        RERANK_TOP_N="",
        RERANK_MAX_CHARS_PER_DOC="",
        ASSEMBLER_MAX_CONTEXTS="",
        ASSEMBLER_MAX_CHARS_PER_CONTEXT="",
        ASSEMBLER_MAX_CHILDREN_PER_PARENT="",
    )

    assert settings.minio_secure is False
    assert settings.max_upload_size_bytes == 5 * 1024 * 1024
    assert settings.chunk_min_parent_section_length == 300
    assert settings.chunk_target_child_size == 800
    assert settings.chunk_child_overlap == 120
    assert settings.chunk_content_preview_length == 120
    assert settings.chunk_txt_parent_group_size == 4
    assert settings.chunk_table_preserve_max_chars == 4000
    assert settings.chunk_table_max_rows_per_child == 20
    assert settings.retrieval_evidence_synopsis_enabled is True
    assert settings.retrieval_evidence_synopsis_variant == "qasper_v3"
    assert settings.rerank_provider == "easypinex-host"
    assert settings.rerank_model == "BAAI/bge-reranker-v2-m3"
    assert settings.easypinex_host_rerank_base_url == "http://easypinex.duckdns.org:8000"
    assert settings.easypinex_host_rerank_api_key is None
    assert settings.easypinex_host_rerank_timeout_seconds == 60.0
    assert settings.rerank_top_n == 30
    assert settings.rerank_max_chars_per_doc == 2000
    assert settings.assembler_max_contexts == 10
    assert settings.assembler_max_chars_per_context == 3600
    assert settings.assembler_max_children_per_parent == 7

"""API 設定物件測試。"""

from app.core.settings import AppSettings


def test_app_settings_uses_defaults_for_empty_string_env_values() -> None:
    """空字串環境變數應回退為 API 設定預設值。"""

    settings = AppSettings(
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
    assert settings.retrieval_evidence_synopsis_enabled is False
    assert settings.retrieval_evidence_synopsis_variant == "generic_v1"
    assert settings.rerank_top_n == 6
    assert settings.rerank_max_chars_per_doc == 2000
    assert settings.assembler_max_contexts == 6
    assert settings.assembler_max_chars_per_context == 2500
    assert settings.assembler_max_children_per_parent == 3

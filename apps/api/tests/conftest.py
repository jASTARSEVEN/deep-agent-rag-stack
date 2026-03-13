"""API 測試共用 fixtures。"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.settings import AppSettings
from app.db.base import Base
from app.main import create_app


@pytest.fixture()
def app_settings(tmp_path: Path) -> AppSettings:
    """建立測試專用設定。

    參數：
    - `tmp_path`：pytest 提供的暫存目錄。

    回傳：
    - `AppSettings`：供 API 測試使用的設定物件。
    """

    database_path = tmp_path / "test.db"
    return AppSettings(
        API_SERVICE_NAME="deep-agent-api-test",
        API_VERSION="0.1.0-test",
        API_HOST="127.0.0.1",
        API_PORT=18000,
        API_CORS_ORIGINS="http://localhost:13000",
        DATABASE_URL=f"sqlite+pysqlite:///{database_path}",
        DATABASE_ECHO=False,
        REDIS_URL="redis://redis:6379/0",
        STORAGE_BACKEND="filesystem",
        MINIO_ENDPOINT="http://minio:9000",
        MINIO_ACCESS_KEY="minio",
        MINIO_SECRET_KEY="minio123",
        MINIO_BUCKET="documents",
        LOCAL_STORAGE_PATH=tmp_path / "storage",
        MAX_UPLOAD_SIZE_BYTES=1024,
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://redis:6379/1",
        INGEST_INLINE_MODE=True,
        EMBEDDING_PROVIDER="deterministic",
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSIONS=1536,
        TEXT_SEARCH_CONFIG="deep_agent_jieba",
        RETRIEVAL_VECTOR_TOP_K=8,
        RETRIEVAL_FTS_TOP_K=8,
        RETRIEVAL_MAX_CANDIDATES=12,
        RETRIEVAL_RRF_K=60,
        RETRIEVAL_HNSW_EF_SEARCH=100,
        KEYCLOAK_URL="http://keycloak:8080",
        KEYCLOAK_ISSUER="http://localhost:18080/realms/deep-agent-dev",
        KEYCLOAK_JWKS_URL="http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs",
        KEYCLOAK_GROUPS_CLAIM="groups",
        AUTH_TEST_MODE=True,
    )


@pytest.fixture()
def app(app_settings: AppSettings):
    """建立測試用 FastAPI 應用程式並初始化資料表。

    參數：
    - `app_settings`：測試專用應用程式設定。

    回傳：
    - 測試用 `FastAPI` 應用程式 fixture。
    """

    application = create_app(app_settings)
    Base.metadata.create_all(bind=application.state.engine)
    try:
        yield application
    finally:
        Base.metadata.drop_all(bind=application.state.engine)
        application.state.engine.dispose()


@pytest.fixture()
def client(app) -> Iterator[TestClient]:
    """建立測試用 TestClient。

    參數：
    - `app`：測試用 FastAPI 應用程式。

    回傳：
    - `Iterator[TestClient]`：供測試發送 HTTP 請求的 client fixture。
    """

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(app) -> Iterator[Session]:
    """提供測試用資料庫 session。

    參數：
    - `app`：測試用 FastAPI 應用程式。

    回傳：
    - `Iterator[Session]`：供測試直接操作資料庫的 session fixture。
    """

    session_factory = app.state.session_factory
    session = session_factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()

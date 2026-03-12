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
    """建立測試專用設定。"""

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
        MINIO_ENDPOINT="http://minio:9000",
        MINIO_BUCKET="documents",
        KEYCLOAK_URL="http://keycloak:8080",
        KEYCLOAK_ISSUER="http://localhost:18080/realms/deep-agent-dev",
        KEYCLOAK_JWKS_URL="http://keycloak:8080/realms/deep-agent-dev/protocol/openid-connect/certs",
        KEYCLOAK_GROUPS_CLAIM="groups",
        AUTH_TEST_MODE=True,
    )


@pytest.fixture()
def app(app_settings: AppSettings):
    """建立測試用 FastAPI 應用程式並初始化資料表。"""

    application = create_app(app_settings)
    Base.metadata.create_all(bind=application.state.engine)
    try:
        yield application
    finally:
        Base.metadata.drop_all(bind=application.state.engine)
        application.state.engine.dispose()


@pytest.fixture()
def client(app) -> Iterator[TestClient]:
    """建立測試用 TestClient。"""

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(app) -> Iterator[Session]:
    """提供測試用資料庫 session。"""

    session_factory = app.state.session_factory
    session = session_factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()

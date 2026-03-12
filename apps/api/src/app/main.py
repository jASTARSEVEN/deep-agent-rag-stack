"""API 骨架的 FastAPI 應用程式進入點。"""

from fastapi import FastAPI

from app.core.settings import AppSettings, get_settings
from app.routes.root import router as root_router


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """建立並設定 FastAPI 應用程式實例。"""

    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.service_name,
        version=resolved_settings.version,
        summary="MVP skeleton API for the Deep Agent RAG Stack.",
    )
    application.include_router(root_router)
    application.state.settings = resolved_settings
    return application


app = create_app()

"""API 骨架的根路由與健康檢查路由。"""

from fastapi import APIRouter

from app.core.settings import get_settings
from app.schemas.health import HealthResponse
from app.services.runtime import build_dependency_snapshot


# 骨架服務對外提供的最小 API 路由集合。
router = APIRouter()


@router.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    """回傳最小 landing payload，明確說明此 API 仍是骨架。"""

    settings = get_settings()
    return {
        "service": settings.service_name,
        "message": "API 骨架已啟動；正式業務路由目前刻意尚未實作。",
    }


@router.get("/health", response_model=HealthResponse, tags=["health"])
def read_health() -> HealthResponse:
    """回傳程序健康狀態與設定層級的依賴快照，供本機接線驗證使用。"""

    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.version,
        dependencies=build_dependency_snapshot(),
    )

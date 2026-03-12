"""API 骨架健康檢查端點使用的回應模型。"""

from pydantic import BaseModel


class DependencySnapshot(BaseModel):
    """本機接線檢查時使用的依賴服務設定快照。"""

    name: str
    target: str


class HealthResponse(BaseModel):
    """API 骨架健康檢查的回應模型。"""

    status: str
    service: str
    version: str
    dependencies: list[DependencySnapshot]

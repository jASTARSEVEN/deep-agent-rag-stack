"""Area access-check API schema。"""

from pydantic import BaseModel

from app.db.models import Role


class AreaAccessResponse(BaseModel):
    """Area access-check 的成功回應。"""

    area_id: str
    effective_role: Role

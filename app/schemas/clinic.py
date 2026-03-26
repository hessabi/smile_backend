import uuid
from datetime import datetime

from pydantic import BaseModel


class ClinicResponse(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    settings: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClinicUpdateRequest(BaseModel):
    name: str | None = None
    settings: dict | None = None

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

InetStr = Annotated[str | None, BeforeValidator(lambda v: str(v) if v is not None else None)]


class ConsentCreate(BaseModel):
    patient_id: uuid.UUID
    consent_type: str
    granted: bool
    granted_by: str | None = None


class ConsentResponse(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    patient_id: uuid.UUID
    consent_type: str
    granted: bool
    granted_by: str | None
    recorded_by: uuid.UUID
    ip_address: InetStr = None
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}

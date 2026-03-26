import uuid
from datetime import datetime

from pydantic import BaseModel


class PatientCreate(BaseModel):
    display_name: str
    external_id: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class PatientUpdate(BaseModel):
    display_name: str | None = None
    external_id: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class PatientResponse(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    display_name: str
    external_id: str | None
    email: str | None
    phone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientListResponse(BaseModel):
    patients: list[PatientResponse]
    total: int

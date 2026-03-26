import uuid
from datetime import date, datetime

from pydantic import BaseModel


class PostProcedureCreate(BaseModel):
    image_key: str
    simulation_id: uuid.UUID | None = None
    procedure_date: date | None = None
    notes: str | None = None


class PostProcedureResponse(BaseModel):
    id: uuid.UUID
    clinic_id: uuid.UUID
    patient_id: uuid.UUID
    simulation_id: uuid.UUID | None
    uploaded_by: uuid.UUID
    image_key: str
    procedure_date: date | None
    notes: str | None
    created_at: datetime
    image_url: str | None = None

    model_config = {"from_attributes": True}
